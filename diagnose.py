"""Finds WHICH stage fails. Put this file in the project root, then run:
    python diagnose.py data\\new.mp4
It samples 12 frames, tests each model, prints a summary and saves annotated frames to diag_out\\"""
import sys, pathlib, cv2
from ultralytics import YOLO

ROOT = pathlib.Path(__file__).resolve().parent
video = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "traffic.mp4")
OUT = ROOT / "diag_out"; OUT.mkdir(exist_ok=True)
stock = YOLO("yolov8s.pt")                                   # COCO model (auto-download)
pk = YOLO(str(ROOT / "Models" / "Pakistan_vehicle" / "best.pt"))
traffic = YOLO(str(ROOT / "Models" / "Traffic" / "best.pt"))
helmet = YOLO(str(ROOT / "Models" / "Helmet" / "best.pt"))

cap = cv2.VideoCapture(video)
if not cap.isOpened(): sys.exit(f"Video nahi khuli: {video}")
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"video: {video} | frames={n} | size={int(cap.get(3))}x{int(cap.get(4))}\n")
print(f"{'frame':>6} {'bike(stock640)':>15} {'bike(stock1280)':>16} {'bike(pakistan)':>15} {'bike(traffic)':>14} {'helmet results on bike crops'}")
for k in range(12):
    idx = int(n * (k + 0.5) / 12); cap.set(cv2.CAP_PROP_POS_FRAMES, idx); ok, fr = cap.read()
    if not ok: continue
    def bikes(model, **kw):
        r = model.predict(fr, conf=0.2, verbose=False, **kw)[0]
        return [(b.xyxy[0].tolist(), float(b.conf)) for b in r.boxes if model.names[int(b.cls)] in ("motorcycle", "motorcycles")], r
    b640, _ = bikes(stock, imgsz=640); b1280, r1280 = bikes(stock, imgsz=1280); bpk, _ = bikes(pk); btr, _ = bikes(traffic)
    H, W = fr.shape[:2]; res = []; vis = r1280.plot()
    for (x1, y1, x2, y2), c in b1280:
        bw, bh = x2 - x1, y2 - y1
        cx1, cy1, cx2, cy2 = max(0, int(x1 - .15 * bw)), max(0, int(y1 - .9 * bh)), min(W, int(x2 + .15 * bw)), min(H, int(y2))
        crop = fr[cy1:cy2, cx1:cx2]
        if crop.size == 0: continue
        hr = helmet.predict(crop, conf=0.25, verbose=False)[0]
        res.append([(helmet.names[int(b.cls)], round(float(b.conf), 2)) for b in hr.boxes] or "none")
        for b in hr.boxes:
            a = b.xyxy[0].tolist(); col = (0, 0, 255) if helmet.names[int(b.cls)] == "Without Helmet" else (0, 200, 0)
            cv2.rectangle(vis, (int(a[0]) + cx1, int(a[1]) + cy1), (int(a[2]) + cx1, int(a[3]) + cy1), col, 3)
    cv2.imwrite(str(OUT / f"frame_{idx}.jpg"), vis)
    print(f"{idx:>6} {len(b640):>15} {len(b1280):>16} {len(bpk):>15} {len(btr):>14} {res}")
print(f"\nAnnotated frames saved in: {OUT}")
