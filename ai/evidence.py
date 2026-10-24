"""Builds the evidence picture: orange vehicle box, red HEAD box, readable label, zoomed HEAD and PLATE thumbnails."""
import cv2

def _label(img, text, x, y, scale):
    (tw, th), b = cv2.getTextSize(text, 0, scale, 2)
    x, y = max(0, x), max(th + b + 2, y)
    cv2.rectangle(img, (x, y - th - b), (x + tw + 6, y + b), (0, 0, 190), -1)
    cv2.putText(img, text, (x + 3, y), 0, scale, (255, 255, 255), 2)

def _thumb(img, title, crop, y, scale, w=220, maxh=220):
    """Paste a zoomed crop at the top-left; returns the next free y."""
    if crop is None or crop.size == 0: return y
    h0, w0 = crop.shape[:2]; s = min(w / w0, maxh / h0); tw, th = max(1, int(w0 * s)), max(1, int(h0 * s))
    H, W = img.shape[:2]; top = y + int(26 * scale)
    if 10 + tw + 4 >= W or top + th + 4 >= H: return y
    _label(img, title, 10, y + int(20 * scale), 0.6 * scale)
    img[top:top + th, 10:10 + tw] = cv2.resize(crop, (tw, th), interpolation=cv2.INTER_CUBIC)
    cv2.rectangle(img, (10, top), (10 + tw, top + th), (255, 255, 255), 2)
    return top + th + 8

def render_evidence(raw, v, plate=None, plate_text=""):
    img = raw.copy(); sc = max(0.6, img.shape[1] / 1600)
    vb = list(map(int, v["box"])); cv2.rectangle(img, tuple(vb[:2]), tuple(vb[2:]), (0, 165, 255), 2)   # vehicle = orange
    head = v.get("head_box"); head_crop = None; anchor = (vb[0], vb[1] - 8)
    if head:
        hx1, hy1, hx2, hy2 = map(int, head); cv2.rectangle(img, (hx1, hy1), (hx2, hy2), (0, 0, 255), 3)  # head = red
        head_crop = raw[max(0, hy1):hy2, max(0, hx1):hx2]; anchor = (hx1, hy1 - 8)
    _label(img, f'{v["type"]} {v["confidence"]:.0%}', anchor[0], anchor[1], 0.7 * sc)
    y = 10
    if head_crop is not None: y = _thumb(img, "HEAD (zoom)", head_crop, y, sc)
    if plate is not None:
        y = _thumb(img, "PLATE", plate, y, sc)
        if plate_text: _label(img, plate_text, 10, y + int(20 * sc), 0.7 * sc)
    return img
