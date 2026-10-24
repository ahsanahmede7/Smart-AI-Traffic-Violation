"""Process an uploaded video OR a camera in the background (ai.pipeline) and stream annotated frames.
Wire in backend/main.py (after `auth` and SECRET exist):
    from backend.jobs import build_router as jobs_router
    app.include_router(jobs_router(auth, SECRET))
Needs: pip install python-multipart"""
import os, re, sys, uuid, time, asyncio, pathlib, importlib.util, subprocess
import jwt
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

ROOT = pathlib.Path(__file__).resolve().parents[1]
UP, LIVE = ROOT / "data" / "uploads", ROOT / "data" / "live"
VEHICLE = os.getenv("VEHICLE_MODEL", "yolov8s.pt")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "2000")); EXT = {".mp4", ".avi", ".mov", ".mkv"}; RULES = {"helmet", "redlight", "wrongway", "seatbelt"}
SL, DIR = re.compile(r"^-?\d+(,-?\d+){3}$"), re.compile(r"^-?\d+,-?\d+$")
CAM = re.compile(r"^(\d{1,2}|(rtsp|http|https)://\S{3,300})$")   # laptop camera index, or a camera URL
SENS = {"strict": (0.70, 5), "balanced": (0.60, 4), "sensitive": (0.50, 3)}   # helmet confidence, confirm frames
SPEED = {"fast": 4, "balanced": 3, "accurate": 2}                                 # process every Nth frame
DISPLAY = {"vehicles", "ids", "helmets", "belts", "plates"}
JOBS = {}

def _info(jid, j):
    rc = j["proc"].poll()
    st = "running" if rc is None else "stopped" if j.get("stopped") else "done" if rc == 0 else "failed"
    try: log = j["log"].read_text(errors="ignore")
    except OSError: log = ""
    out = {"id": jid, "status": st, "source": j["source"], "seconds": int(time.time() - j["started"]),
           "violations": log.count("VIOLATION"), "hasFrame": (LIVE / f"{jid}.jpg").exists()}
    if st == "failed": out["error"] = log[-500:]
    return out

def build_router(auth, secret):
    r = APIRouter()

    @r.post("/api/jobs")
    async def create(file: UploadFile | None = File(None), camera: str = Form(""), location: str = Form("Main Road"),
                     rules: str = Form("helmet"), stop_line: str = Form(""), allowed_dir: str = Form(""),
                     display: str = Form("helmets,plates"), sensitivity: str = Form("balanced"), speed: str = Form("balanced"),
                     ocr: str = Form(""), plate_track: str = Form("1"), _=Depends(auth)):
        if any(j["proc"].poll() is None for j in JOBS.values()):
            raise HTTPException(409, "Another video/camera is still running. Stop it first.")
        camera = camera.strip()
        if bool(file and file.filename) == bool(camera): raise HTTPException(400, "Either choose a video file OR give a camera, not both/none")
        if camera and not CAM.match(camera): raise HTTPException(400, "Camera must be a number (0 = laptop camera) or an rtsp/http URL")
        chosen = [x for x in rules.split(",") if x in RULES] or ["helmet"]
        if "redlight" in chosen and not SL.match(stop_line): raise HTTPException(400, "Red Light ke liye stop line (2 click) zaroori hai")
        if "wrongway" in chosen and not DIR.match(allowed_dir): raise HTTPException(400, "Wrong Way ke liye direction (2 click) zaroori hai")
        UP.mkdir(parents=True, exist_ok=True); LIVE.mkdir(parents=True, exist_ok=True)
        jid = uuid.uuid4().hex[:10]
        if camera: src, label = camera, "camera " + camera
        else:
            ext = pathlib.Path(file.filename or "").suffix.lower()
            if ext not in EXT: raise HTTPException(400, "Only mp4, avi, mov or mkv videos are allowed")
            dest = UP / f"{jid}{ext}"; size = 0
            with open(dest, "wb") as f:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_MB << 20:
                        f.close(); dest.unlink(missing_ok=True); raise HTTPException(413, f"Video is larger than {MAX_MB} MB")
                    f.write(chunk)
            src, label = str(dest), file.filename
        logp = UP / f"{jid}.log"
        cmd = [sys.executable, "-m", "ai.pipeline", "--video", src, "--location", location.strip()[:60] or "Main Road",
               "--rules", ",".join(chosen), "--vehicle", VEHICLE, "--job", jid]
        hc, cf = SENS.get(sensitivity, SENS["balanced"])
        cmd += ["--stride", str(SPEED.get(speed, 3)), "--helmet-conf", str(hc), "--confirm", str(cf),
                "--display", ",".join(x for x in display.split(",") if x in DISPLAY) or "helmets"]
        if ocr == "1": cmd += ["--ocr"]
        if plate_track == "0": cmd += ["--no-plate-track"]
        if "redlight" in chosen: cmd += ["--stop-line=" + stop_line]
        if "wrongway" in chosen: cmd += ["--allowed-dir=" + allowed_dir]
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=open(logp, "w"), stderr=subprocess.STDOUT)
        JOBS[jid] = {"proc": proc, "source": label, "started": time.time(), "log": logp}
        return {"id": jid}

    @r.get("/api/capabilities")
    def capabilities(_=Depends(auth)):
        """What is installed on this computer (the Live page greys out what is missing)."""
        has = lambda sub: (ROOT / "Models" / sub / "best.pt").exists()
        return {"helmetModel": has("Helmet"), "plateModel": has("LicennsePlate"), "lightModel": has("Light"),
                "seatbeltModel": has("SeatBelt"), "ocr": importlib.util.find_spec("easyocr") is not None}

    @r.get("/api/jobs")
    def list_jobs(_=Depends(auth)):
        """Newest first. The Live page uses this to re-attach after you leave and come back."""
        return [_info(k, j) for k, j in sorted(JOBS.items(), key=lambda kv: -kv[1]["started"])][:5]

    @r.get("/api/jobs/{jid}")
    def status(jid: str, _=Depends(auth)):
        j = JOBS.get(jid)
        if not j: raise HTTPException(404, "Unknown job")
        return _info(jid, j)

    @r.post("/api/jobs/{jid}/stop")
    def stop(jid: str, _=Depends(auth)):
        j = JOBS.get(jid)
        if not j: raise HTTPException(404, "Unknown job")
        if j["proc"].poll() is None:
            j["stopped"] = True; j["proc"].terminate()
            try: j["proc"].wait(timeout=5)
            except subprocess.TimeoutExpired: j["proc"].kill()
        return _info(jid, j)

    @r.get("/api/jobs/{jid}/stream")
    async def stream(jid: str, request: Request, token: str = Query(...)):
        try: jwt.decode(token, secret, algorithms=["HS256"])  # <img> cannot send headers, so the token is a query param
        except jwt.PyJWTError: raise HTTPException(401, "Invalid or expired token")
        j = JOBS.get(jid)
        if not j: raise HTTPException(404, "Unknown job")
        path = LIVE / f"{jid}.jpg"

        async def gen():
            last = 0
            while not await request.is_disconnected():
                data = None
                if path.exists():
                    try:
                        m = path.stat().st_mtime
                        if m != last: data = path.read_bytes(); last = m
                    except OSError: pass
                if data: yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
                elif j["proc"].poll() is not None: break
                else: await asyncio.sleep(0.05)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
    return r
