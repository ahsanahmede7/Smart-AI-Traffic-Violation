"""Violation-risk prediction (Random Forest).

Usage (from project root):
  python -m ai.prediction.risk_model --train            # train from MongoDB violations (falls back to demo data)
  python -m ai.prediction.risk_model --predict 18       # risk for hour 18 (today)

Features: hour, day_of_week, location_id, traffic_count (violations/hour used as proxy).
Target: violations per hour-bucket -> converted to LOW / MEDIUM / HIGH / VERY HIGH.
NOTE: with little real data the model learns the demo pattern. Say this honestly in the viva.
"""
import argparse, pathlib, pickle
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "Models" / "risk_rf.pkl"
LABELS = ["LOW", "MEDIUM", "HIGH", "VERY HIGH"]


def level(count, q):
    """q = quantile thresholds (q1,q2,q3) from training data."""
    return LABELS[int(np.searchsorted(q, count, side="right"))]


def demo_data(n_days=60, seed=0):
    """Synthetic pattern: evening peak (7 PM), weekends a bit higher. Used when DB is empty."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for d in range(n_days):
        for h in range(24):
            base = 3 + 40 * np.exp(-((h - 19) ** 2) / 8) + 15 * np.exp(-((h - 9) ** 2) / 6)
            base *= 1.2 if d % 7 in (5, 6) else 1.0
            X.append([h, d % 7]); y.append(max(0, rng.normal(base, 4)))
    return np.array(X), np.array(y)


def db_data():
    """Counts violations per (hour, weekday) from MongoDB. Returns None if too little data."""
    try:
        from backend.db import violations
        from collections import Counter
        c = Counter()
        days = set()
        for v in violations.find({}, {"timestamp": 1}):
            t = v["timestamp"]; c[(t.date(), t.hour)] += 1; days.add(t.date())
        if len(days) < 7:
            return None
        X, y = [], []
        for dte in days:
            for h in range(24):
                X.append([h, dte.weekday()]); y.append(c.get((dte, h), 0))
        return np.array(X), np.array(y)
    except Exception as e:
        print("DB not used:", e)
        return None


def train():
    data = db_data()
    src = "MongoDB"
    if data is None:
        data, src = demo_data(), "synthetic demo data"
    X, y = data
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    m = RandomForestRegressor(n_estimators=200, random_state=42).fit(Xtr, ytr)
    mae = mean_absolute_error(yte, m.predict(Xte))
    q = np.quantile(y, [0.5, 0.8, 0.95])
    MODEL_PATH.parent.mkdir(exist_ok=True)
    pickle.dump(dict(model=m, q=q), open(MODEL_PATH, "wb"))
    print(f"trained on {src}: {len(y)} rows, MAE={mae:.2f} violations/hour")
    return mae


def predict_day(weekday):
    if not MODEL_PATH.exists():
        train()
    d = pickle.load(open(MODEL_PATH, "rb"))
    out = []
    for h in range(24):
        c = float(d["model"].predict([[h, weekday]])[0])
        out.append(dict(hour=h, expected=round(c, 1), risk=level(c, d["q"])))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--predict", type=int)
    a = ap.parse_args()
    if a.train:
        train()
    if a.predict is not None:
        from datetime import datetime
        row = predict_day(datetime.now().weekday())[a.predict]
        print(row)
