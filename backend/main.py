"""Phase 12-18: FastAPI + MongoDB + JWT. Run: uvicorn backend.main:app --reload"""
import os, bcrypt, jwt
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from backend.db import db, violations, users

SECRET = os.getenv("JWT_SECRET", "dev-only")
os.makedirs("evidence", exist_ok=True)

app = FastAPI(title="Smart Traffic AI")

# --- CORS FIX APPLIED HERE ---
raw_origins = os.getenv("CORS_ORIGINS", "*")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()] if raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------------------

app.mount("/evidence", StaticFiles(directory="evidence"), name="evidence")
bearer = HTTPBearer()

@app.on_event("startup")
def seed_admin():
    if not users.find_one({"username": os.getenv("ADMIN_USER", "admin")}):
        pw = bcrypt.hashpw(os.getenv("ADMIN_PASS", "admin123").encode(), bcrypt.gensalt())
        users.insert_one({"username": os.getenv("ADMIN_USER", "admin"), "password": pw, "role": "admin"})

def auth(c: HTTPAuthorizationCredentials = Depends(bearer)):
    try: 
        return jwt.decode(c.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: 
        raise HTTPException(401, "Invalid or expired token")

class Login(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=100)

@app.post("/api/auth/login")
def login(b: Login):
    u = users.find_one({"username": b.username})
    if not u or not bcrypt.checkpw(b.password.encode(), u["password"]): 
        raise HTTPException(401, "Wrong credentials")
    return {"token": jwt.encode({"sub": b.username, "exp": datetime.utcnow() + timedelta(hours=8)}, SECRET)}

def ser(d): 
    d["id"] = str(d.pop("_id"))
    return d

@app.get("/api/violations")
def list_v(type: str | None = None, limit: int = 50, _=Depends(auth)):
    q = {"type": type} if type else {}
    return [ser(d) for d in violations.find(q).sort("timestamp", -1).limit(min(limit, 200))]

@app.get("/api/violations/{vid}")
def one_v(vid: str, _=Depends(auth)):
    try: 
        d = violations.find_one({"_id": ObjectId(vid)})
    except Exception: 
        raise HTTPException(400, "Bad id")
    if not d: 
        raise HTTPException(404, "Not found")
    return ser(d)

def by_type(): 
    return {r["_id"]: r["n"] for r in violations.aggregate([{"$group": {"_id": "$type", "n": {"$sum": 1}}0}]} if r["_id"] is not None} # safe check

@app.get("/api/statistics")
def stats(_=Depends(auth)):
    t = by_type()
    return {"total": sum(t.values()), "byType": t, "vehicles": len(violations.distinct("vehicleId"))}

@app.get("api/vehicles" if False else "/api/vehicles")
def vehicles(_=Depends(auth)): 
    return violations.distinct("vehicleId")

@app.get("/api/traffic")
def traffic(_=Depends(auth)): 
    return [ser(d) for d in db.traffic_data.find().sort("timestamp", -1).limit(100)]

@app.get("/api/analytics")
def analytics(_=Depends(auth)):
    hourly = violations.aggregate([{"$group": {"_id": {"$hour": "$timestamp"}, "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
    loc = violations.aggregate([{"$group": {"_id": "$location", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])
    return {
        "hourly": [{"hour": h["_id"], "count": h["n"]} for h in hourly],
        "locations": [{"location": l["_id"], "count": l["n"]} for l in loc], 
        "byType": by_type()
    }

@app.get("/api/reports")
def report(_=Depends(auth)):
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    t = {r["_id"]: r["n"] for r in violations.aggregate([{"$match": {"timestamp": {"$gte": start}}}, {"$group": {"_id": "$type", "n": {"$sum": 1}}}])}
    return {"date": start.date().isoformat(), "totalViolations": sum(t.values()), "byType": t}

# prediction + PDF report
from backend.extras import build_router
app.include_router(build_router(auth))

from backend.jobs import build_router as jobs_router
app.include_router(jobs_router(auth, SECRET))