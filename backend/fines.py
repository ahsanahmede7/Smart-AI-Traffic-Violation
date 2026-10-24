"""Looks up the fine for a violation from backend/fines.json (read on every call, so edits apply immediately)."""
import json, os, pathlib

def config():
    data = json.loads((pathlib.Path(__file__).parent / "fines.json").read_text(encoding="utf-8"))
    key = os.getenv("FINE_REGION", "sindh").lower()
    return key, data["regions"].get(key) or data["regions"]["sindh"]

def fine_for(v):
    """-> dict(region, verified, law, amount (PKR or None), points, note). amount None = officer must decide."""
    _, r = config(); rule = r["fines"].get(v.get("type"))
    out = {"region": r["name"], "verified": r["verified"], "law": None, "amount": None, "points": None, "note": None}
    if not rule: return out
    out.update(law=rule["law"], points=rule.get("points"), note=rule.get("note"))
    cls = v.get("vehicleClass") or ("motorcycle" if v.get("type") == "No Helmet" else None)
    col = r["classes"].get(cls)
    if col: out["amount"] = rule["amounts"].get(col)
    return out
