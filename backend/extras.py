"""Random Forest violation-risk prediction + daily PDF report.
Wire it in backend/main.py (after `auth` is defined):
    from backend.extras import build_router
    app.include_router(build_router(auth))"""
from collections import Counter
from datetime import datetime, timedelta
from io import BytesIO
import pathlib, re
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.db import violations
from backend.fines import fine_for, config as fine_config
from backend.cloud_storage import delete_evidence

EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "evidence"

def _rm(name):
    """Delete an evidence file (plain file names only, never paths)."""
    if name and name == pathlib.Path(name).name:
        (EVIDENCE / name).unlink(missing_ok=True)

class PlateBody(BaseModel):
    plateText: str = ""

def _oid(vid):
    try: return ObjectId(vid)
    except Exception: raise HTTPException(400, "Bad id")

def _hourly():
    c = Counter()
    for d in violations.find({}, {"timestamp": 1}):
        t = d["timestamp"]; c[(t.date(), t.hour)] += 1
    return c

def build_router(auth):
    r = APIRouter()

    @r.get("/api/prediction")
    def prediction(_=Depends(auth)):
        from sklearn.ensemble import RandomForestRegressor
        c = _hourly(); days = sorted({k[0] for k in c}); total = sum(c.values())
        if total < 20:
            return {"ready": False, "total": total, "message": "At least 20 recorded violations are needed to train the model."}
        X, y = [], []
        for d in days:                      # one row per (day, hour); hours with no violation count as 0
            for h in range(24):
                X.append([h, d.weekday()]); y.append(c.get((d, h), 0))
        model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, y)
        tomorrow = datetime.utcnow().date() + timedelta(days=1)
        pred = model.predict([[h, tomorrow.weekday()] for h in range(24)]); mx = max(float(pred.max()), 1e-9)
        hours = [{"hour": h, "predicted": round(float(p), 2),
                  "risk": "HIGH" if p >= .66 * mx else "MEDIUM" if p >= .33 * mx else "LOW"} for h, p in enumerate(pred)]
        return {"ready": True, "date": tomorrow.isoformat(), "model": "RandomForestRegressor",
                "trainedOnDays": len(days), "totalRecords": total, "hours": hours}

    @r.get("/api/reports/pdf")
    def pdf(_=Depends(auth)):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = list(violations.find({"timestamp": {"$gte": start}}))
        by = Counter(x["type"] for x in rows); hrs = Counter(x["timestamp"].hour for x in rows)
        buf = BytesIO(); c = canvas.Canvas(buf, pagesize=A4, pageCompression=0); y = A4[1] - 60
        c.setFont("Helvetica-Bold", 18); c.drawString(50, y, "SMART TRAFFIC REPORT"); y -= 30
        c.setFont("Helvetica", 12); c.drawString(50, y, f"Date: {start.strftime('%d %B %Y')} (UTC)"); y -= 22
        c.drawString(50, y, f"Total Violations: {len(rows)}"); y -= 22
        for k, v in by.most_common(): c.drawString(70, y, f"{k}: {v}"); y -= 18
        if hrs:
            ph = hrs.most_common(1)[0][0]; y -= 8
            c.drawString(50, y, f"Peak Violation Time: {ph:02d}:00 - {(ph + 1) % 24:02d}:00 (UTC)")
        c.showPage(); c.save(); buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=daily_report.pdf"})

    @r.get("/api/alerts")
    def alerts(minutes: int = 1440, _=Depends(auth)):
        since = datetime.utcnow() - timedelta(minutes=max(1, min(minutes, 10080)))
        out = []
        for d in violations.find({"timestamp": {"$gte": since}}).sort("timestamp", -1).limit(200):
            d["id"] = str(d.pop("_id")); out.append(d)
        return out

    @r.get("/api/predict")
    def predict(_=Depends(auth)):
        """Hourly forecast for today (UTC) in the shape the Risk page expects: [{hour, expected, risk}]."""
        from sklearn.ensemble import RandomForestRegressor
        c = _hourly(); days = sorted({k[0] for k in c}); total = sum(c.values())
        if total < 5: return [{"hour": h, "expected": 0, "risk": "LOW"} for h in range(24)]
        X = [[h, d.weekday()] for d in days for h in range(24)]; y = [c.get((d, h), 0) for d in days for h in range(24)]
        m = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, y)
        today = datetime.utcnow().date(); pred = m.predict([[h, today.weekday()] for h in range(24)]); mx = max(float(pred.max()), 1e-9)
        lv = lambda p: "VERY HIGH" if p >= .85 * mx else "HIGH" if p >= .6 * mx else "MEDIUM" if p >= .3 * mx else "LOW"
        return [{"hour": h, "expected": round(float(p), 2), "risk": lv(p)} for h, p in enumerate(pred)]

    @r.delete("/api/violations/{vid}")
    def delete_one(vid: str, _=Depends(auth)):
        try: oid = ObjectId(vid)
        except Exception: raise HTTPException(400, "Bad id")
        d = violations.find_one_and_delete({"_id": oid})
        if not d: raise HTTPException(404, "Not found")
        _rm(d.get("evidenceImage")); _rm(d.get("plateImage"))
        return {"deleted": 1}

    @r.delete("/api/violations")
    def delete_all(confirm: str = "", _=Depends(auth)):
        if confirm != "yes": raise HTTPException(400, "Add ?confirm=yes to delete everything")
        docs = list(violations.find({}, {"evidenceImage": 1, "plateImage": 1}))
        n = violations.delete_many({}).deleted_count
        for d in docs: _rm(d.get("evidenceImage")); _rm(d.get("plateImage"))
        return {"deleted": n}

    @r.patch("/api/violations/{vid}")
    def edit_plate(vid: str, body: PlateBody, _=Depends(auth)):
        """The officer types/corrects the number plate after looking at the evidence."""
        txt = body.plateText.strip().upper()
        if not re.fullmatch(r"[A-Z0-9 \-]{0,15}", txt): raise HTTPException(422, "Plate: letters, numbers, space or dash (max 15)")
        res = violations.update_one({"_id": _oid(vid)}, {"$set": {"plateText": txt or None, "plateVerified": True}})
        if res.matched_count == 0: raise HTTPException(404, "Not found")
        return {"plateText": txt}

    @r.get("/api/fines")
    def fines(_=Depends(auth)):
        """The active fine schedule (the Violations page shows the fine per row from this)."""
        key, cfg = fine_config(); return {"region": key, **cfg}

    @r.get("/api/violations/{vid}/challan")
    def challan(vid: str, _=Depends(auth)):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        d = violations.find_one({"_id": _oid(vid)})
        if not d: raise HTTPException(404, "Not found")
        W, H = A4; buf = BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 20); c.drawString(50, H - 60, "TRAFFIC VIOLATION CHALLAN")
        c.setFont("Helvetica", 10); c.drawString(50, H - 78, "Generated by Smart Traffic AI. Must be verified by an authorised officer before issue.")
        fi = fine_for(d)
        fine_rows = [("Legal basis", (fi["law"] or "-")[:62]),
                     ("Fine amount", f'PKR {fi["amount"]:,}' if fi["amount"] else "To be determined by the officer"),
                     ("Demerit points", str(fi["points"]) if fi["points"] else "-")]
        t = d.get("timestamp"); rows = [("Challan No", "CH-" + str(d["_id"])[-8:].upper()), ("Violation", d.get("type", "")),
            ("Date / time (UTC)", t.strftime("%d %b %Y, %H:%M:%S") if t else ""), ("Location", d.get("location", "")),
            ("Tracked vehicle ID", "#" + str(d.get("vehicleId", ""))), ("Detection confidence", f'{round(d.get("confidence", 0) * 100)}%'),
            ("Number plate", (d.get("plateText") or "NOT READ - verify from the plate image") + ("  (officer verified)" if d.get("plateVerified") else "")),
            *fine_rows]
        y = H - 120
        for k, v in rows:
            c.setFont("Helvetica-Bold", 11); c.drawString(50, y, k + ":"); c.setFont("Helvetica", 11); c.drawString(190, y, str(v)[:70]); y -= 20
        def img(name, label, w, y):
            if not name or name != pathlib.Path(name).name or not (EVIDENCE / name).exists(): return y
            ir = ImageReader(str(EVIDENCE / name)); iw, ih = ir.getSize(); h = w * ih / iw
            if h > 300: h = 300; w = h * iw / ih
            c.setFont("Helvetica-Bold", 10); c.drawString(50, y - 12, label); c.drawImage(ir, 50, y - 22 - h, width=w, height=h)
            return y - 36 - h
        y = img(d.get("evidenceImage"), "Evidence", 480, y - 10); y = img(d.get("plateImage"), "Number plate (zoom)", 220, y)
        c.setFont("Helvetica-Oblique", 9); c.drawString(50, 54, f'Fine schedule: {fi["region"]}, verified {fi["verified"]}. Verify against the official notification.'); c.drawString(50, 40, "Automatic detections can be wrong. This document is not valid until an officer has checked the evidence.")
        c.showPage(); c.save(); buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="challan_{str(d["_id"])[-8:]}.pdf"'})
    return r
