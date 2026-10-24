"""Clean live/preview overlay. Only what you switch on is drawn; flagged vehicles are always highlighted (orange)."""
import cv2

def _tag(img, text, x, y, fs, fg=(255, 255, 255), bg=(50, 50, 50)):
    (tw, th), b = cv2.getTextSize(text, 0, fs, 1); x, y = max(0, int(x)), max(th + b + 1, int(y))
    cv2.rectangle(img, (x, y - th - b), (x + tw + 4, y + b), bg, -1); cv2.putText(img, text, (x + 2, y), 0, fs, fg, 1, cv2.LINE_AA)

def draw_frame(raw, vehicles, heads, belts, plates, opts, flagged, n_viol):
    img = raw.copy(); W = img.shape[1]; sc = min(2.0, max(0.5, W / 1920)); t = max(1, round(2 * sc)); fs = max(0.4, 0.55 * sc)
    flagged = set(flagged)
    for v in vehicles:
        bad = v["id"] in flagged
        if not bad and "vehicles" not in opts: continue
        x1, y1, x2, y2 = map(int, v["box"]); col = (0, 140, 255) if bad else (190, 150, 70)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, t + 1 if bad else max(1, t - 1))
        label = v["cls"] + (f' #{v["id"]}' if "ids" in opts and v["id"] is not None else "")
        if bad or "vehicles" in opts: _tag(img, label + (" - VIOLATION" if bad else ""), x1, y1 - 3, fs, bg=col if bad else (90, 90, 90))
    if "helmets" in opts:
        for d in heads:
            no = d["cls"] == "Without Helmet"; col = (0, 0, 220) if no else (0, 170, 0); x1, y1, x2, y2 = map(int, d["box"])
            cv2.rectangle(img, (x1, y1), (x2, y2), col, t); _tag(img, f'{"NO" if no else "OK"} {d["conf"]:.2f}', x1, y1 - 3, fs * 0.9, bg=col)
    if "belts" in opts:
        for d in belts:
            x1, y1, x2, y2 = map(int, d["box"]); cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 255), t)
    if "plates" in opts:
        for d in plates:
            x1, y1, x2, y2 = map(int, d["box"]); cv2.rectangle(img, (x1, y1), (x2, y2), (255, 220, 0), max(1, t - 1)); _tag(img, "PLATE", x1, y1 - 3, fs * 0.8, fg=(0, 0, 0), bg=(255, 220, 0))
    txt = f"Violations: {n_viol}"; (tw, th), _ = cv2.getTextSize(txt, 0, fs * 1.2, 2)
    cv2.rectangle(img, (W - tw - 24, 8), (W - 8, th + 24), (30, 30, 30), -1); cv2.putText(img, txt, (W - tw - 16, th + 16), 0, fs * 1.2, (255, 255, 255), 2, cv2.LINE_AA)
    return img
