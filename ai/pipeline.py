
"""Smart AI Traffic Violation pipeline with Cloudinary evidence storage.

Run from project root:
    python -m ai.pipeline --video data/traffic.mp4 --dry --save-img --show
    python -m ai.pipeline --video data/traffic.mp4 --location "Main Road"
    python -m ai.pipeline --video 0 --location "Main Road"

Cloudinary stores violation evidence images.
MongoDB stores violation records and Cloudinary URLs.
"""

import argparse
import os
import sys
import time
import pathlib
import cv2

from collections import deque
from datetime import datetime
from ultralytics import YOLO

from ai.evidence import render_evidence
from ai.overlay import draw_frame
from ai.plates import PlateBook
from ai.violations.engine import (
    NoHelmet,
    WrongWay,
    RedLight,
    NoSeatBelt,
)
from backend.cloud_storage import upload_evidence


ROOT = pathlib.Path(__file__).resolve().parents[1]
M = ROOT / "Models"

ap = argparse.ArgumentParser()

ap.add_argument(
    "--video",
    required=True,
    help="Video file, 0 = laptop camera, or rtsp/http URL",
)
ap.add_argument("--location", default="Main Road")
ap.add_argument(
    "--vehicle",
    default=str(M / "Pakistan_vehicle" / "best.pt"),
)
ap.add_argument("--helmet", default=str(M / "Helmet" / "best.pt"))
ap.add_argument("--light", default=str(M / "Light" / "best.pt"))
ap.add_argument(
    "--plate",
    default=str(M / "LicennsePlate" / "best.pt"),
    help="Number-plate model; skipped if missing",
)
ap.add_argument(
    "--seatbelt",
    default=str(M / "SeatBelt" / "best.pt"),
)
ap.add_argument(
    "--ocr",
    action="store_true",
    help="Read plate text with easyocr",
)
ap.add_argument(
    "--no-plate-track",
    action="store_true",
    help="Do not detect plates on every frame",
)
ap.add_argument(
    "--rules",
    default="helmet",
    help="Comma-separated: helmet,redlight,wrongway,seatbelt",
)
ap.add_argument(
    "--display",
    default="helmets,plates",
    help="Comma-separated: vehicles,ids,helmets,belts,plates",
)
ap.add_argument(
    "--allowed-dir",
    default="1,0",
    help="Legal traffic direction dx,dy",
)
ap.add_argument(
    "--stop-line",
    default="0,400,1280,400",
    help="Stop line x1,y1,x2,y2",
)
ap.add_argument("--helmet-conf", type=float, default=0.65)
ap.add_argument("--confirm", type=int, default=4)
ap.add_argument("--min-bike-h", type=float, default=0.12)
ap.add_argument("--vconf", type=float, default=0.3)
ap.add_argument("--stride", type=int, default=2)
ap.add_argument(
    "--job",
    default="",
    help="Job ID for live preview frames",
)
ap.add_argument("--dry", action="store_true")
ap.add_argument("--save-img", action="store_true")
ap.add_argument("--show", action="store_true")

# Handle negative direction values such as --allowed-dir -1,0.
argv = sys.argv[1:]
for i, tok in enumerate(argv[:-1]):
    if tok in ("--allowed-dir", "--stop-line"):
        argv[i] = tok + "=" + argv[i + 1]
        argv[i + 1] = None

argv = [x for x in argv if x is not None]

a = ap.parse_args(argv)
rules = set(a.rules.split(","))
opts = set(a.display.split(","))

given = lambda flag: any(
    x == flag or x.startswith(flag + "=") for x in argv
)

if "wrongway" in rules and not given("--allowed-dir"):
    sys.exit(
        "Wrong Way ke liye --allowed-dir zaroori hai. "
        "tools/pick_line.py se direction nikalo."
    )

if "redlight" in rules and not given("--stop-line"):
    sys.exit(
        "Red Light ke liye --stop-line zaroori hai. "
        "Video mein signal nazar aana chahiye."
    )

ALIAS = {
    "motorcycles": "motorcycle",
    "buses": "bus",
    "vehicles": "car",
    "bicycles": "bicycle",
}

VEH_CLASSES = {
    "car",
    "motorcycle",
    "bus",
    "truck",
    "emv",
    "htv",
    "rikshaw",
    "bicycle",
}


def dets(res, names):
    """Convert YOLO boxes to dictionaries."""
    return [
        {
            "cls": ALIAS.get(
                names[int(b.cls)],
                names[int(b.cls)],
            ),
            "conf": float(b.conf),
            "box": b.xyxy[0].tolist(),
            "id": int(b.id) if b.id is not None else None,
        }
        for b in res.boxes
    ]


# Load AI models.
vehicle = YOLO(a.vehicle)
helmet = YOLO(a.helmet) if "helmet" in rules else None
light = YOLO(a.light) if "redlight" in rules else None
belt = YOLO(a.seatbelt) if "seatbelt" in rules else None

plate = (
    YOLO(a.plate)
    if pathlib.Path(a.plate).exists()
    else None
)

if plate is None:
    print(
        "Plate model not found; plates will be skipped:",
        a.plate,
        flush=True,
    )

reader = None

if a.ocr:
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
    except Exception as e:
        print("OCR disabled:", str(e), flush=True)

r_helmet = NoHelmet(
    min_conf=a.helmet_conf,
    confirm=a.confirm,
    min_h_frac=a.min_bike_h,
)
r_belt = NoSeatBelt()

r_wrong = WrongWay(
    tuple(map(float, a.allowed_dir.split(",")))
)

x1, y1, x2, y2 = map(
    int,
    a.stop_line.split(","),
)
r_red = RedLight(((x1, y1), (x2, y2)))

if not a.dry:
    from backend.db import violations

if not a.dry or a.save_img:
    ev = ROOT / "evidence"
    ev.mkdir(parents=True, exist_ok=True)

if a.job:
    live = ROOT / "data" / "live"
    live.mkdir(parents=True, exist_ok=True)

    live_path = live / f"{a.job}.jpg"
    live_tmp = live / f"{a.job}_tmp.jpg"

seen = set()
red_hist = deque(maxlen=5)

book = PlateBook()
plate_text = {}
track_plates = plate is not None and not a.no_plate_track


def read_plate(raw, box):
    """Find a number plate inside the violating vehicle's crop."""
    if plate is None:
        return None

    bx1, by1, bx2, by2 = map(int, box)

    crop = raw[
        max(0, by1):by2,
        max(0, bx1):bx2,
    ]

    if crop.size == 0:
        return None

    res = plate.predict(
        crop,
        conf=0.3,
        verbose=False,
    )[0]

    if not len(res.boxes):
        return None

    b = max(
        res.boxes,
        key=lambda x: float(x.conf),
    )

    px1, py1, px2, py2 = map(
        int,
        b.xyxy[0].tolist(),
    )

    pc = crop[
        max(0, py1):py2,
        max(0, px1):px2,
    ]

    return pc if pc.size else None


def ocr_text(vid, pc):
    """Read and cache number-plate text."""
    if reader is None or pc is None:
        return ""

    if vid not in plate_text:
        try:
            big = cv2.resize(
                pc,
                None,
                fx=3,
                fy=3,
                interpolation=cv2.INTER_CUBIC,
            )

            plate_text[vid] = "".join(
                ch
                for ch in " ".join(
                    reader.readtext(big, detail=0)
                ).upper()
                if ch.isalnum() or ch in " -"
            ).strip()

        except Exception:
            plate_text[vid] = ""

    return plate_text[vid]


def cloud_upload_safely(file_path, folder):
    """Upload an image; return URL/public ID or None values on failure."""
    try:
        result = upload_evidence(
            str(file_path),
            folder=folder,
        )

        print(
            "CLOUDINARY_UPLOAD_SUCCESS",
            result["public_id"],
            flush=True,
        )

        return result["url"], result["public_id"]

    except Exception as exc:
        print(
            "CLOUDINARY_UPLOAD_ERROR:",
            str(exc),
            flush=True,
        )
        return None, None


# Main detection loop.
for r in vehicle.track(
    source=a.video,
    stream=True,
    persist=True,
    tracker="bytetrack.yaml",
    conf=a.vconf,
    vid_stride=a.stride,
    verbose=False,
):
    raw = r.orig_img
    H, W = raw.shape[:2]

    found = []
    heads = []
    belts = []
    plates = []

    veh = [
        d
        for d in dets(r, vehicle.names)
        if d["cls"] in VEH_CLASSES
    ]

    # Helmet detection on motorcycle crops.
    if helmet:
        for m in veh:
            if m["cls"] != "motorcycle":
                continue

            bx1, by1, bx2, by2 = m["box"]
            bw = bx2 - bx1
            bh = by2 - by1

            cx1 = max(0, int(bx1 - 0.15 * bw))
            cy1 = max(0, int(by1 - 0.9 * bh))
            cx2 = min(W, int(bx2 + 0.15 * bw))
            cy2 = min(H, int(by2))

            crop = raw[cy1:cy2, cx1:cx2]

            if crop.size == 0:
                continue

            result = helmet.predict(
                crop,
                conf=0.35,
                verbose=False,
            )[0]

            for d in dets(result, helmet.names):
                b = d["box"]
                d["box"] = [
                    b[0] + cx1,
                    b[1] + cy1,
                    b[2] + cx1,
                    b[3] + cy1,
                ]
                heads.append(d)

        found += r_helmet.check(veh, heads, H)

    # Seat-belt detection.
    if belt:
        for m in veh:
            if m["cls"] not in ("car", "emv"):
                continue

            if m["box"][2] - m["box"][0] < 0.18 * W:
                continue

            bx1, by1, bx2, by2 = map(int, m["box"])

            cx1 = max(0, bx1)
            cy1 = max(0, by1)

            crop = raw[
                cy1:int(by1 + 0.65 * (by2 - by1)),
                cx1:bx2,
            ]

            if crop.size == 0:
                continue

            result = belt.predict(
                crop,
                conf=0.25,
                verbose=False,
            )[0]

            for d in dets(result, belt.names):
                b = d["box"]
                d["box"] = [
                    b[0] + cx1,
                    b[1] + cy1,
                    b[2] + cx1,
                    b[3] + cy1,
                ]
                belts.append(d)

        found += r_belt.check(veh, belts, W)

    # Wrong-way detection.
    if "wrongway" in rules:
        found += r_wrong.check(veh)

    # Red-light detection with temporal smoothing.
    if light:
        light_result = light.predict(
            raw,
            conf=0.4,
            verbose=False,
        )[0]

        red_hist.append(
            any(
                d["cls"] == "red" and d["conf"] >= 0.6
                for d in dets(light_result, light.names)
            )
        )

        found += r_red.check(
            veh,
            sum(red_hist) >= 3,
        )

    # Track number plates.
    if track_plates:
        plate_result = plate.predict(
            raw,
            conf=0.3,
            imgsz=960,
            verbose=False,
        )[0]

        plates = dets(plate_result, plate.names)
        book.update(veh, plates, raw)

    cls_by_id = {
        d["id"]: d["cls"]
        for d in veh
        if d["id"] is not None
    }

    # Save each vehicle/type violation once per run.
    for v in found:
        key = (v["type"], v["vehicle_id"])

        if key in seen:
            continue

        seen.add(key)

        print(
            "VIOLATION",
            v["type"],
            "vehicle",
            v["vehicle_id"],
            f'{v["confidence"]:.0%}',
            flush=True,
        )

        if a.dry and not a.save_img:
            continue

        pc = book.get(v["vehicle_id"])

        if pc is None:
            pc = read_plate(raw, v["box"])

        ptxt = ocr_text(v["vehicle_id"], pc)

        safe_type = (
            v["type"].replace(" ", "_").lower()
        )

        name = (
            f'{safe_type}_{v["vehicle_id"]}_'
            f'{int(time.time())}.jpg'
        )

        pname = None
        plate_path = None

        if pc is not None:
            pname = "plate_" + name
            plate_path = ev / pname

            if not cv2.imwrite(str(plate_path), pc):
                print(
                    "PLATE_LOCAL_SAVE_ERROR",
                    str(plate_path),
                    flush=True,
                )
                pname = None
                plate_path = None

        evidence_path = ev / name

        evidence_image = render_evidence(
            raw,
            v,
            pc,
            ptxt,
        )

        if not cv2.imwrite(
            str(evidence_path),
            evidence_image,
        ):
            print(
                "EVIDENCE_LOCAL_SAVE_ERROR",
                str(evidence_path),
                flush=True,
            )
            continue

        # Dry mode: save locally only; never upload or write DB.
        if a.dry:
            print(
                "DRY_EVIDENCE_SAVED",
                str(evidence_path),
                flush=True,
            )
            continue

        # Upload violation evidence to Cloudinary.
        evidence_url, evidence_public_id = cloud_upload_safely(
            evidence_path,
            "smart-ai-traffic/violations",
        )

        plate_url = None
        plate_public_id = None

        if plate_path is not None:
            plate_url, plate_public_id = cloud_upload_safely(
                plate_path,
                "smart-ai-traffic/plates",
            )

        # Save existing fields plus Cloudinary metadata to MongoDB.
        document = {
            "type": v["type"],
            "vehicleId": v["vehicle_id"],
            "confidence": round(v["confidence"], 3),
            "timestamp": datetime.utcnow(),
            "location": a.location,
            "evidenceImage": name,
            "plateImage": pname,
            "plateText": ptxt or None,
            "vehicleClass": cls_by_id.get(
                v["vehicle_id"]
            ),
            "evidenceUrl": evidence_url,
            "evidencePublicId": evidence_public_id,
            "plateUrl": plate_url,
            "platePublicId": plate_public_id,
        }

        try:
            inserted = violations.insert_one(document)

            print(
                "MONGODB_VIOLATION_SAVED",
                str(inserted.inserted_id),
                flush=True,
            )

            if evidence_url:
                print(
                    "EVIDENCE_CLOUD_URL",
                    evidence_url,
                    flush=True,
                )

        except Exception as exc:
            print(
                "MONGODB_SAVE_ERROR:",
                str(exc),
                flush=True,
            )
            raise

    # Live preview is kept separate from Cloudinary uploads.
    if a.show or a.job:
        frame = draw_frame(
            raw,
            veh,
            heads,
            belts,
            plates,
            opts,
            {k[1] for k in seen},
            len(seen),
        )

        scale = min(
            1280 / W,
            720 / H,
            1.0,
        )

        if scale < 1.0:
            frame = cv2.resize(
                frame,
                (
                    int(W * scale),
                    int(H * scale),
                ),
            )

        if a.job:
            cv2.imwrite(
                str(live_tmp),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 70],
            )

            try:
                os.replace(live_tmp, live_path)
            except OSError:
                pass

        if a.show:
            cv2.imshow(
                "Smart Traffic AI (Esc to quit)",
                frame,
            )

            if cv2.waitKey(1) == 27:
                break

if a.show:
    cv2.destroyAllWindows()
