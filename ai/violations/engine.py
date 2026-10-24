"""Rule-based violation engine. A detection is dict(cls, conf, box=[x1,y1,x2,y2], id)."""
from collections import defaultdict, deque
import numpy as np

VEHICLES = ("car", "motorcycle", "emv", "htv", "rikshaw")

def center(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

def frac_inside(a, b):
    """Fraction of box a lying inside box b."""
    iw = min(a[2], b[2]) - max(a[0], b[0]); ih = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, iw) * max(0, ih) / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))

class NoHelmet:
    """'Without Helmet' head box inside a motorcycle's rider zone.
    False-alarm guards: confidence >= min_conf, seen in `confirm` frames, and a rider who was EVER seen
    'With Helmet' is only flagged if the bad frames clearly outnumber the good ones (3x)."""
    def __init__(self, bad="Without Helmet", good="With Helmet", min_conf=0.65, confirm=4, min_h_frac=0.12):
        self.bad, self.good, self.min_conf, self.confirm, self.min_h_frac = bad, good, min_conf, confirm, min_h_frac
        self.bad_n = defaultdict(int); self.good_n = defaultdict(int)
    def check(self, vehicles, heads, frame_h=0):
        out = []
        for m in vehicles:
            if m["cls"] != "motorcycle" or m["id"] is None: continue
            x1, y1, x2, y2 = m["box"]
            if frame_h and (y2 - y1) < self.min_h_frac * frame_h: continue   # rider too far/small to judge a helmet
            zone = (x1, y1 - 0.8 * (y2 - y1), x2, y2)
            inz = [h for h in heads if frac_inside(h["box"], zone) > 0.6]
            bad = [h for h in inz if h["cls"] == self.bad and h["conf"] >= self.min_conf]
            if any(h["cls"] == self.good and h["conf"] >= 0.4 for h in inz): self.good_n[m["id"]] += 1
            if bad: self.bad_n[m["id"]] += 1
            n, g = self.bad_n[m["id"]], self.good_n[m["id"]]
            if bad and n >= self.confirm and (g == 0 or n >= 3 * g):
                best = max(bad, key=lambda h: h["conf"]); out.append(dict(type="No Helmet", vehicle_id=m["id"], confidence=best["conf"], box=m["box"], head_box=best["box"]))
        return out

class WrongWay:
    """allowed = (dx, dy): direction of legal traffic in image coordinates, e.g. (1,0) = left->right, (0,1) = towards camera."""
    def __init__(self, allowed=(1, 0), window=20, min_px=40):
        n = float(np.hypot(*allowed)); self.allowed = (allowed[0] / n, allowed[1] / n)
        self.hist = defaultdict(lambda: deque(maxlen=window)); self.min_px = min_px
    def check(self, vehicles):
        out = []
        for d in vehicles:
            if d["cls"] not in VEHICLES or d["id"] is None: continue
            h = self.hist[d["id"]]; h.append(center(d["box"]))
            if len(h) < h.maxlen: continue
            dx, dy = h[-1][0] - h[0][0], h[-1][1] - h[0][1]; dist = float(np.hypot(dx, dy))
            if dist >= self.min_px and (dx * self.allowed[0] + dy * self.allowed[1]) / dist < -0.6:
                out.append(dict(type="Wrong Way", vehicle_id=d["id"], confidence=d["conf"], box=d["box"]))
        return out

class RedLight:
    """stop_line=((x1,y1),(x2,y2)); red_on comes from the traffic-light model. Violation = vehicle crosses the line while red."""
    def __init__(self, stop_line): self.a, self.b = stop_line; self.prev = {}
    def _side(self, p):
        return np.sign((self.b[0] - self.a[0]) * (p[1] - self.a[1]) - (self.b[1] - self.a[1]) * (p[0] - self.a[0]))
    def check(self, vehicles, red_on):
        out = []
        for d in vehicles:
            if d["cls"] not in VEHICLES or d["id"] is None: continue
            s = self._side(center(d["box"])); p = self.prev.get(d["id"]); self.prev[d["id"]] = s
            if red_on and p is not None and p != 0 and s != p:
                out.append(dict(type="Red Light", vehicle_id=d["id"], confidence=d["conf"], box=d["box"]))
        return out

class NoSeatBelt:
    """EXPERIMENTAL. The seat-belt model has one class, so it can only see a belt that IS worn.
    A close car whose windshield shows no belt for `confirm` frames -> "No Seat Belt". Glare, angle and distance cause
    false alarms, so evidence must be checked by a human."""
    def __init__(self, min_width_frac=0.18, confirm=8):
        self.min_width_frac, self.confirm = min_width_frac, confirm; self.miss = defaultdict(int); self.worn = set()
    def check(self, vehicles, belts, frame_w):
        out = []
        for v in vehicles:
            if v["cls"] not in ("car", "emv") or v["id"] is None or v["id"] in self.worn: continue
            if v["box"][2] - v["box"][0] < self.min_width_frac * frame_w: continue   # too far to judge
            if any(frac_inside(b["box"], v["box"]) > 0.5 for b in belts): self.worn.add(v["id"]); continue
            self.miss[v["id"]] += 1
            if self.miss[v["id"]] == self.confirm:
                out.append(dict(type="No Seat Belt", vehicle_id=v["id"], confidence=0.5, box=v["box"]))
        return out
