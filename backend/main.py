
"""Smart AI Traffic Violation API.
Run: uvicorn backend.main:app --reload
"""

import io
import os
import logging
import bcrypt
import jwt
import cloudinary
import cloudinary.uploader

from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.db import db, violations, users
from backend.extras import build_router
from backend.jobs import build_router as jobs_router


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUD_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUD_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not all([CLOUD_NAME, CLOUD_API_KEY, CLOUD_API_SECRET]):
    raise RuntimeError("Cloudinary environment variables are missing")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=CLOUD_API_KEY,
    api_secret=CLOUD_API_SECRET,
    secure=True,
)

app = FastAPI(title="Smart Traffic AI")

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "evidence"

# Ensure the directory exists before mounting StaticFiles.
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/evidence",
    StaticFiles(directory=str(EVIDENCE_DIR)),
    name="evidence",
)

bearer = HTTPBearer()

raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
)
origins = [
    origin.strip()
    for origin in raw_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

class Login(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=100)


@app.on_event("startup")
def seed_admin():
    username = os.getenv("ADMIN_USER")
    password = os.getenv("ADMIN_PASS")

    if not username or not password:
        logger.warning(
            "ADMIN_USER/ADMIN_PASS missing; admin seeding skipped"
        )
        return

    if not users.find_one({"username": username}):
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        )

        users.insert_one({
            "username": username,
            "password": hashed_password,
            "role": "admin",
        })


def auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    try:
        return jwt.decode(
            credentials.credentials,
            SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


@app.post("/api/auth/login")
def login(body: Login):
    user = users.find_one({"username": body.username})

    if not user or not bcrypt.checkpw(
        body.password.encode("utf-8"),
        user["password"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Wrong credentials",
        )

    token = jwt.encode(
        {
            "sub": body.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=8),
        },
        SECRET,
        algorithm="HS256",
    )

    return {"token": token}


# --------------------------------------------------
# CLOUDINARY EVIDENCE UPLOAD
# --------------------------------------------------

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def upload_violation_evidence(image_path: str) -> dict:
    """Upload an existing local image to Cloudinary."""

    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Evidence image not found: {path}"
        )

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    if path.suffix.lower() not in allowed_extensions:
        raise ValueError("Unsupported evidence image format")

    result = cloudinary.uploader.upload(
        str(path),
        folder="traffic-violations",
        resource_type="image",
        allowed_formats=["jpg", "jpeg", "png", "webp"],
        overwrite=False,
    )

    return {
        "evidence_url": result["secure_url"],
        "public_id": result["public_id"],
    }


def save_violation(
    image_path: str,
    violation_type: str,
    vehicle_id: str | None = None,
    plate_number: str | None = None,
    confidence: float | None = None,
    location: str | None = None,
):
    """Upload evidence and save its Cloudinary ID in MongoDB."""

    cloud = upload_violation_evidence(image_path)

    document = {
        "type": violation_type,
        "timestamp": datetime.now(timezone.utc),
        "evidence_url": cloud["evidence_url"],
        "evidence_public_id": cloud["public_id"],
        "vehicleId": vehicle_id,
        "plate_number": plate_number,
        "confidence": confidence,
        "location": location,
    }

    try:
        result = violations.insert_one(document)
    except Exception:
        # Avoid leaving an orphaned image if the database insert fails.
        try:
            cloudinary.uploader.destroy(
                cloud["public_id"],
                resource_type="image",
                invalidate=True,
            )
        except Exception:
            logger.exception(
                "Cloudinary cleanup failed after MongoDB insert error"
            )
        raise

    document["id"] = str(result.inserted_id)
    document.pop("_id", None)

    return document


@app.post("/api/violations/upload")
def upload_evidence_endpoint(
    file: UploadFile = File(...),
    violation_type: str = Form(...),
    vehicle_id: str | None = Form(None),
    plate_number: str | None = Form(None),
    confidence: float | None = Form(None),
    location: str | None = Form(None),
    _=Depends(auth),
):
    """Upload evidence to Cloudinary and store its metadata."""

    allowed_extensions = ALLOWED_CONTENT_TYPES.get(file.content_type)

    if not allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG and WebP images are allowed",
        )

    image_bytes = file.file.read(MAX_UPLOAD_SIZE + 1)

    if len(image_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds 10 MB",
        )

    uploaded_public_id = None

    try:
        # Basic signature checks help reject files that only spoof MIME type.
        signatures = {
            "image/jpeg": image_bytes.startswith(b"\xff\xd8\xff"),
            "image/png": image_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": (
                len(image_bytes) >= 12
                and image_bytes[:4] == b"RIFF"
                and image_bytes[8:12] == b"WEBP"
            ),
        }

        if not signatures.get(file.content_type, False):
            raise HTTPException(
                status_code=415,
                detail="File contents do not match the image type",
            )

        result = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder="traffic-violations",
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png", "webp"],
            overwrite=False,
        )

        uploaded_public_id = result.get("public_id")
        image_url = result.get("secure_url")

        if not uploaded_public_id or not image_url:
            raise RuntimeError(
                "Cloudinary did not return the image URL and public ID"
            )

        document = {
            "type": violation_type,
            "timestamp": datetime.now(timezone.utc),
            "evidence_url": image_url,
            "evidence_public_id": uploaded_public_id,
            "vehicleId": vehicle_id,
            "plate_number": plate_number,
            "confidence": confidence,
            "location": location,
        }

        saved = violations.insert_one(document)

        return {
            "message": "Evidence uploaded successfully",
            "id": str(saved.inserted_id),
            "evidence_url": image_url,
            "public_id": uploaded_public_id,
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Evidence upload or database save failed")

        # If Cloudinary upload succeeded but MongoDB save failed, clean up.
        if uploaded_public_id:
            try:
                cloudinary.uploader.destroy(
                    uploaded_public_id,
                    resource_type="image",
                    invalidate=True,
                )
            except Exception:
                logger.exception(
                    "Cloudinary cleanup failed after upload error"
                )

        raise HTTPException(
            status_code=502,
            detail="Evidence upload or database save failed",
        ) from exc

    finally:
        file.file.close()


# --------------------------------------------------
# VIOLATION APIs
# --------------------------------------------------

def ser(document):
    document["id"] = str(document.pop("_id"))
    return document


@app.get("/api/violations")
def list_violations(
    type: str | None = None,
    limit: int = 50,
    _=Depends(auth),
):
    query = {"type": type} if type else {}
    limit = max(1, min(limit, 200))

    return [
        ser(document)
        for document in violations.find(query)
        .sort("timestamp", -1)
        .limit(limit)
    ]


@app.get("/api/violations/{vid}")
def get_violation(vid: str, _=Depends(auth)):
    try:
        document = violations.find_one({
            "_id": ObjectId(vid)
        })
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Bad id",
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    return ser(document)


# IMPORTANT:
# Single-delete and Delete All are registered in backend/extras.py.
# Do not define another DELETE /api/violations/{vid} here.


def by_type():
    pipeline = [
        {
            "$group": {
                "_id": "$type",
                "n": {"$sum": 1},
            }
        }
    ]

    return {
        row["_id"]: row["n"]
        for row in violations.aggregate(pipeline)
        if row["_id"] is not None
    }


@app.get("/api/statistics")
def stats(_=Depends(auth)):
    types = by_type()

    return {
        "total": sum(types.values()),
        "byType": types,
        "vehicles": len(violations.distinct("vehicleId")),
    }


@app.get("/api/vehicles")
def list_vehicles(_=Depends(auth)):
    return violations.distinct("vehicleId")


@app.get("/api/traffic")
def traffic(_=Depends(auth)):
    return [
        ser(document)
        for document in db.traffic_data.find()
        .sort("timestamp", -1)
        .limit(100)
    ]


@app.get("/api/analytics")
def analytics(_=Depends(auth)):
    hourly = list(violations.aggregate([
        {
            "$group": {
                "_id": {"$hour": "$timestamp"},
                "n": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]))

    locations = list(violations.aggregate([
        {
            "$group": {
                "_id": "$location",
                "n": {"$sum": 1},
            }
        },
        {"$sort": {"n": -1}},
    ]))

    return {
        "hourly": [
            {"hour": row["_id"], "count": row["n"]}
            for row in hourly
        ],
        "locations": [
            {"location": row["_id"], "count": row["n"]}
            for row in locations
        ],
        "byType": by_type(),
    }


@app.get("/api/reports")
def report(_=Depends(auth)):
    start = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    counts = {
        row["_id"]: row["n"]
        for row in violations.aggregate([
            {"$match": {"timestamp": {"$gte": start}}},
            {
                "$group": {
                    "_id": "$type",
                    "n": {"$sum": 1},
                }
            },
        ])
    }

    return {
        "date": start.date().isoformat(),
        "totalViolations": sum(counts.values()),
        "byType": counts,
    }


# --------------------------------------------------
# EXISTING ROUTERS
# --------------------------------------------------

app.include_router(build_router(auth))
app.include_router(jobs_router(auth, SECRET))
