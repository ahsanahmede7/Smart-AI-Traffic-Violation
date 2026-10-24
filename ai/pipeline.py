"""Video/camera -> vehicle tracking + helmet + plate + traffic-light + seat-belt models -> violations -> evidence -> MongoDB.
Run from the project root:
  python -m ai.pipeline --video data\\traffic.mp4 --vehicle yolov8s.pt --dry --save-img --show --stride 3    (test, nothing saved to DB)
  python -m ai.pipeline --video data\\traffic.mp4 --vehicle yolov8s.pt --location "Main Road" --stride 3     (saves to MongoDB)
  --video 0 uses the laptop camera.  --display vehicles,ids,helmets,belts,plates  chooses what is drawn."""
import argparse, os, sys, time, pathlib, cv2
from collections import deque
from datetime import datetime
from ultralytics import YOLO
from ai.evidence import render_evidence
from ai.overlay import draw_frame
from ai.plates import PlateBook
from ai.violations.engine import NoHelmet, WrongWay, RedLight, NoSeatBelt

ROOT = pathlib.Path(__file__).resolve().parents[1]; M = ROOT / "Models"
ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True, help="video file, 0 = laptop camera, or rtsp/http URL"); ap.add_argument("--location", default="Main Road")
ap.add_argument("--vehicle", default=str(M / "Pakistan_vehicle" / "best.pt"))
ap.add_argument("--helmet", default=str(M / "Helmet" / "best.pt"))
ap.add_argument("--light", default=str(M / "Light" / "best.pt"))
ap.add_argument("--plate", default=str(M / "LicennsePlate" / "best.pt"), help="number-plate model (skipped if file missing)")
ap.add_argument("--seatbelt", default=str(M / "SeatBelt" / "best.pt"))
ap.add_argument("--ocr", action="store_true", help="read plate text with easyocr (pip install easyocr)")
ap.add_argument("--no-plate-track", action="store_true", help="do not detect plates on every frame")
ap.add_argument("--rules", default="helmet", help="comma list: helmet,redlight,wrongway,seatbelt")
ap.add_argument("--display", default="helmets,plates", help="comma list: vehicles,ids,helmets,belts,plates")
ap.add_argument("--allowed-dir", default="1,0", help="legal traffic direction dx,dy (wrong-way)")
ap.add_argument("--stop-line", default="0,400,1280,400", help="x1,y1,x2,y2 (red-light)")
ap.add_argument("--helmet-conf", type=float, default=0.65, help="min confidence of a Without Helmet box (lower = more catches, more false alarms)")
ap.add_argument("--confirm", type=int, default=4, help="frames a rider must look helmetless")
ap.add_argument("--min-bike-h", type=float, default=0.12, help="ignore bikes shorter than this fraction of frame height")
ap.add_argument("--vconf", type=float, default=0.3, help="vehicle detection confidence")
ap.add_argument("--stride", type=int, default=2, help="process every Nth frame (speed)")
ap.add_argument("--job", default="", help="job id: writes live preview frames to data/live/<job>.jpg (used by the web page)")
ap.add_argument("--dry", action="store_true", help="print only, no DB"); ap.add_argument("--save-img", action="store_true", help="with --dry: still save evidence images (no DB)")
ap.add_argument("--show", action="store_true")
argv = sys.argv[1:]   # argparse mistakes "-1,0" for an option, so glue such values to their flag: --allowed-dir=-1,0
for i, tok in enumerate(argv[:-1]):
    if tok in ("--allowed-dir", "--stop-line") and argv[i + 1] is not None: argv[i] = tok + "=" + argv[i + 1]; argv[i + 1] = None
argv = [x for x in argv if x is not None]
a = ap.parse_args(argv); rules = set(a.rules.split(",")); opts = set(a.display.split(","))
given = lambda flag: any(x == flag or x.startswith(flag + "=") for x in argv)
if "wrongway" in rules and not given("--allowed-dir"): sys.exit("Wrong Way ke liye --allowed-dir zaroori hai (tools\\pick_line.py se nikalo). Default se jhoote challan banenge.")
if "redlight" in rules and not given("--stop-line"): sys.exit("Red Light ke liye --stop-line zaroori hai (tools\\pick_line.py se nikalo) aur video mein signal nazar aana chahiye.")

ALIAS = {"motorcycles": "motorcycle", "buses": "bus", "vehicles": "car", "bicycles": "bicycle"}  # Traffic model names
VEH_CLASSES = {"car", "motorcycle", "bus", "truck", "emv", "htv", "rikshaw", "bicycle"}           # persons etc. are never drawn/used

def dets(res, names):
    return [dict(cls=ALIAS.get(names[int(b.cls)], names[int(b.cls)]), conf=float(b.conf), box=b.xyxy[0].tolist(),
                 id=int(b.id) if b.id is not None else None) for b in res.boxes]

vehicle = YOLO(a.vehicle)
helmet = YOLO(a.helmet) if "helmet" in rules else None
light = YOLO(a.light) if "redlight" in rules else None
belt = YOLO(a.seatbelt) if "seatbelt" in rules else None
plate = YOLO(a.plate) if pathlib.Path(a.plate).exists() else None
if plate is None: print("Plate model not found, plates will be skipped:", a.plate, flush=True)
reader = None
if a.ocr:
    try:
        import easyocr; reader = easyocr.Reader(["en"], gpu=False)
    except Exception as e:
        print("OCR disabled:", e, flush=True)
r_helmet = NoHelmet(min_conf=a.helmet_conf, confirm=a.confirm, min_h_frac=a.min_bike_h); r_belt = NoSeatBelt(); r_wrong = WrongWay(tuple(map(float, a.allowed_dir.split(","))))
x1, y1, x2, y2 = map(int, a.stop_line.split(",")); r_red = RedLight(((x1, y1), (x2, y2)))
if not a.dry:
    from backend.db import violations
if not a.dry or a.save_img:
    ev = ROOT / "evidence"; ev.mkdir(exist_ok=True)
if a.job:
    live = ROOT / "data" / "live"; live.mkdir(parents=True, exist_ok=True)
    live_path, live_tmp = live / f"{a.job}.jpg", live / f"{a.job}_tmp.jpg"
seen = set(); red_hist = deque(maxlen=5)   # red must be seen in 3 of the last 5 frames (filters one-frame false reds)
book = PlateBook(); plate_text = {}; track_plates = plate is not None and not a.no_plate_track

def read_plate(raw, box):
    """Fallback: search for a plate inside the violating vehicle's box."""
    if plate is None: return None
    bx1, by1, bx2, by2 = map(int, box); crop = raw[max(0, by1):by2, max(0, bx1):bx2]
    if crop.size == 0: return None
    res = plate.predict(crop, conf=0.3, verbose=False)[0]
    if not len(res.boxes): return None
    b = max(res.boxes, key=lambda x: float(x.conf)); px1, py1, px2, py2 = map(int, b.xyxy[0].tolist())
    pc = crop[max(0, py1):py2, max(0, px1):px2]
    return pc if pc.size else None

def ocr_text(vid, pc):
    if reader is None or pc is None: return ""
    if vid not in plate_text:
        try:
            big = cv2.resize(pc, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            plate_text[vid] = "".join(ch for ch in " ".join(reader.readtext(big, detail=0)).upper() if ch.isalnum() or ch in " -").strip()
        except Exception:
            plate_text[vid] = ""
    return plate_text[vid]

for r in vehicle.track(source=a.video, stream=True, persist=True, tracker="bytetrack.yaml",
                       conf=a.vconf, vid_stride=a.stride, verbose=False):
    raw = r.orig_img; H, W = raw.shape[:2]; found = []; heads = []; belts = []; plates = []
    veh = [d for d in dets(r, vehicle.names) if d["cls"] in VEH_CLASSES]
    if helmet:
        for m in veh:  # run the helmet model on each rider's crop (heads are tiny in a full frame)
            if m["cls"] != "motorcycle": continue
            bx1, by1, bx2, by2 = m["box"]; bw, bh = bx2 - bx1, by2 - by1
            cx1, cy1 = max(0, int(bx1 - 0.15 * bw)), max(0, int(by1 - 0.9 * bh))
            cx2, cy2 = min(W, int(bx2 + 0.15 * bw)), min(H, int(by2))
            crop = raw[cy1:cy2, cx1:cx2]
            if crop.size == 0: continue
            for d in dets(helmet.predict(crop, conf=0.35, verbose=False)[0], helmet.names):
                b = d["box"]; d["box"] = [b[0] + cx1, b[1] + cy1, b[2] + cx1, b[3] + cy1]; heads.append(d)
        found += r_helmet.check(veh, heads, H)
    if belt:
        for m in veh:  # seat-belt model on the windshield area of close cars
            if m["cls"] not in ("car", "emv") or m["box"][2] - m["box"][0] < 0.18 * W: continue
            bx1, by1, bx2, by2 = map(int, m["box"]); cx1, cy1 = max(0, bx1), max(0, by1)
            crop = raw[cy1:int(by1 + 0.65 * (by2 - by1)), cx1:bx2]
            if crop.size == 0: continue
            for d in dets(belt.predict(crop, conf=0.25, verbose=False)[0], belt.names):
                b = d["box"]; d["box"] = [b[0] + cx1, b[1] + cy1, b[2] + cx1, b[3] + cy1]; belts.append(d)
        found += r_belt.check(veh, belts, W)
    if "wrongway" in rules: found += r_wrong.check(veh)
    if light:
        red_hist.append(any(d["cls"] == "red" and d["conf"] >= 0.6 for d in dets(light.predict(raw, conf=0.4, verbose=False)[0], light.names)))
        found += r_red.check(veh, sum(red_hist) >= 3)
    if track_plates:  # plates are detected on every processed frame and remembered per vehicle id
        plates = dets(plate.predict(raw, conf=0.3, imgsz=960, verbose=False)[0], plate.names)
        book.update(veh, plates, raw)
    cls_by_id = {d["id"]: d["cls"] for d in veh if d["id"] is not None}
    for v in found:
        key = (v["type"], v["vehicle_id"])
        if key in seen: continue  # one record per vehicle per violation type
        seen.add(key); print("VIOLATION", v["type"], "vehicle", v["vehicle_id"], f'{v["confidence"]:.0%}', flush=True)
        if a.dry and not a.save_img: continue
        pc = book.get(v["vehicle_id"])
        if pc is None: pc = read_plate(raw, v["box"])
        ptxt = ocr_text(v["vehicle_id"], pc)
        name = f'{v["type"].replace(" ", "_").lower()}_{v["vehicle_id"]}_{int(time.time())}.jpg'; pname = None
        if pc is not None: pname = "plate_" + name; cv2.imwrite(str(ev / pname), pc)
        cv2.imwrite(str(ev / name), render_evidence(raw, v, pc, ptxt))   # vehicle box + HEAD box + zoomed head/plate
        if a.dry: continue
        violations.insert_one(dict(type=v["type"], vehicleId=v["vehicle_id"], confidence=round(v["confidence"], 3),
                                   timestamp=datetime.utcnow(), location=a.location, evidenceImage=name,
                                   plateImage=pname, plateText=ptxt or None, vehicleClass=cls_by_id.get(v["vehicle_id"])))
    if a.show or a.job:
        frame = draw_frame(raw, veh, heads, belts, plates, opts, {k[1] for k in seen}, len(seen))
        s = min(1280 / W, 720 / H, 1.0)          # fit the window to the screen
        if s < 1.0: frame = cv2.resize(frame, (int(W * s), int(H * s)))
        if a.job:
            cv2.imwrite(str(live_tmp), frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            try: os.replace(live_tmp, live_path)
            except OSError: pass
        if a.show:
            cv2.imshow("Smart Traffic AI (Esc to quit)", frame)
            if cv2.waitKey(1) == 27: break
