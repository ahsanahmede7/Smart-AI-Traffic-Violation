"""Demo data so the dashboard has something to show before the model is ready.
Add:    python -m backend.seed_demo
Remove: python -m backend.seed_demo --clear"""
import sys, random
from datetime import datetime, timedelta
from backend.db import violations

if "--clear" in sys.argv:
    print("deleted", violations.delete_many({"demo": True}).deleted_count); sys.exit()
types = ["No Helmet"] * 5 + ["Wrong Way"] * 3 + ["Red Light"] * 2 + ["No Helmet", "Red Light"]
places = ["Main Road", "Shahrah-e-Faisal", "University Road"]
now = datetime.utcnow()
violations.insert_many([dict(type=random.choice(types), vehicleId=random.randint(1, 60),
    confidence=round(random.uniform(.6, .98), 2), timestamp=now - timedelta(minutes=random.randint(0, 1400)),
    location=random.choice(places), evidenceImage=None, demo=True) for _ in range(40)])
print("added 40 demo violations")
