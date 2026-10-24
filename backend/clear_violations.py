"""Delete wrong violations from MongoDB (evidence files stay in the evidence folder).
  python -m backend.clear_violations --vehicle 188      one vehicle id
  python -m backend.clear_violations --all              everything (not the demo-only ones: use seed_demo --clear for those)"""
import sys
from backend.db import violations
if "--all" in sys.argv:
    print("deleted", violations.delete_many({}).deleted_count)
elif "--vehicle" in sys.argv:
    vid = int(sys.argv[sys.argv.index("--vehicle") + 1]); print("deleted", violations.delete_many({"vehicleId": vid}).deleted_count)
else:
    print(__doc__)
