"""Plate tracking: remembers the sharpest/biggest plate crop seen for every tracked vehicle id."""
from ai.violations.engine import frac_inside

class PlateBook:
    def __init__(self, cap=2000): self.best, self.cap = {}, cap
    def update(self, vehicles, plates, frame):
        for p in plates:
            owners = [v for v in vehicles if v["id"] is not None and frac_inside(p["box"], v["box"]) > 0.8]
            if not owners: continue
            owner = min(owners, key=lambda v: (v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1]))  # tightest vehicle box
            x1, y1, x2, y2 = map(int, p["box"]); crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0: continue
            score = p["conf"] * crop.shape[0] * crop.shape[1]
            cur = self.best.get(owner["id"])
            if cur is None or score > cur[0]:
                self.best[owner["id"]] = (score, crop.copy())
                if len(self.best) > self.cap: self.best.pop(next(iter(self.best)))
    def get(self, vid):
        item = self.best.get(vid); return item[1] if item else None
