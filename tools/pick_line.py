"""Find stop-line and traffic direction for a video by clicking on its first frame.
    python tools\\pick_line.py data\\traffic.mp4
1) click 2 points ON the stop line  2) click 2 points: start -> end of the LEGAL traffic direction. Press any key to finish."""
import sys, cv2
cap = cv2.VideoCapture(sys.argv[1]); ok, fr = cap.read()
if not ok: sys.exit("Video nahi khuli: " + sys.argv[1])
H, W = fr.shape[:2]; s = min(1280 / W, 720 / H, 1.0); show = cv2.resize(fr, (int(W * s), int(H * s))); pts = []
def click(e, x, y, *_):
    if e == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
        pts.append((int(x / s), int(y / s))); col = (0, 0, 255) if len(pts) <= 2 else (0, 255, 0)
        cv2.circle(show, (x, y), 5, col, -1)
        if len(pts) in (2, 4): cv2.line(show, (int(pts[-2][0] * s), int(pts[-2][1] * s)), (x, y), col, 2)
        cv2.imshow("pick", show)
cv2.imshow("pick", show); cv2.setMouseCallback("pick", click); cv2.waitKey(0); cv2.destroyAllWindows()
if len(pts) >= 2: print("--stop-line", f"{pts[0][0]},{pts[0][1]},{pts[1][0]},{pts[1][1]}")
if len(pts) == 4: print("--allowed-dir", f"{pts[3][0] - pts[2][0]},{pts[3][1] - pts[2][1]}")
