# Smart Traffic AI – Complete Guide (Roman Urdu)

## 1. System kaise kaam karta hai
Video / camera -> **YOLO (yolov8s)** gaariyan pakarta hai -> **ByteTrack** har gaari ko ID deta hai -> bike par **Helmet model**
rider ke sar ko With/Without Helmet batata hai -> **rules** (kam az kam 4 frames, confidence, bike ka size) violation tay karte hain
-> **Plate model** har gaari ki sab se saaf number plate yaad rakhta hai -> evidence tasveer (gaari box + SAR box + zoom sar + zoom plate)
-> **MongoDB** -> **FastAPI** -> **React dashboard** (Overview, Violations, Analytics, Reports, Live Monitoring) -> **Challan PDF**.

## 2. Roz chalane ka tareeqa (3 terminals, project root se, venv active)
1. `python -m uvicorn backend.main:app --reload`
2. `cd frontend-react` phir `npm run dev`  -> http://localhost:5173
3. Live Monitoring page se video upload ya camera. (Command line sirf test ke liye.)

## 3. Live Monitoring ke options
| Option | Matlab |
|---|---|
| Upload video / Camera | File chuno, ya `0` (laptop camera), ya rtsp:// link |
| Rules | No Helmet (pakka), Red Light / Wrong Way (har video ke liye 2-2 click chahiye, abhi tajarbati), Seat Belt (tajarbati) |
| Helmet sensitivity | **Strict**: ghalat challan kam, kuch violations chhut sakti hain. **Balanced**. **Sensitive**: zyada pakrega, ghalat bhi zyada |
| Speed / quality | Fast = har 4th frame, Accurate = har 2nd frame |
| Screen par kya dikhana hai | Helmet boxes, Vehicle boxes, Vehicle IDs, Plate boxes, Seat-belt boxes. **Saaf screen = sirf Helmet + Plate** |
| Plate tracking | Har gaari ki behtareen plate crop yaad rakhta hai (Plate model chahiye) |
| OCR | Plate ka text padhta hai. `pip install easyocr` chahiye. Bharose ka nahi: tasveer dekh kar officer number likhta hai |
| Stop | Chalti hui detection rokta hai. Doosre page par jaa kar wapas aao to detection chalti rehti hai |

## 4. Violation se challan tak
1. Violations page kholo. Har row mein plate ki tasveer, **Evidence** link, aur **Challan** button hai.
2. Evidence kholo: **laal box = sar**, orange = gaari, upar-left par SAR aur PLATE ka zoom.
3. Agar sahi hai: pencil se plate ka number likho (ya sahi karo). Ghalat hai: dustbin se delete.
4. **Challan** dabao: PDF banta hai (challan no, waqt, jagah, violation, plate, evidence tasveer). Fine ki raqam officer bharta hai.

## 5. Settings kab badlein
- Ghalat challan aa rahe hain (helmet pehne rider flag) -> **Strict**.
- Bina helmet wale chhut rahe hain -> **Sensitive** aur **Accurate**, phir har evidence haath se check karo.
- Screen par ghich-mich -> Display mein sirf Helmet + Plate.
- Bike bohat door/chhoti hai -> model nahi parh sakta (12% se chhoti bike ignore hoti hai). Paas wali, saaf video use karo.

## 6. Kya chalta hai, kya nahi (report mein yehi likho)
- Chalta hai (test hua): tracking, No Helmet, evidence, MongoDB, dashboard, upload + live, delete, analytics, PDF report.
- Tajarbati / adhoora: Red Light (signal saaf chahiye + stop line), Wrong Way (do-tarfa sadak par ek direction kaafi nahi), Seat Belt (model sirf lagi hui belt dekhta hai), plate OCR, Speed, Lane.
- Helmet model: peele/anokhe rang ke helmet ya topi/pagri par ghalat aa sakta hai; kam resolution aur door ke riders par kamzor.
- Prediction: kam data par sirf demo; Random Forest kam az kam 5 records chahiye.
- Aage: zyada Pakistani helmet images par dobara train, lane-wise zones, OCR.

## 7. Aksar aane wale masle
| Masla | Hal |
|---|---|
| `No module named backend` | Command project root se chalao, `python -m ...` ke saath |
| Login 422 | ADMIN_PASS 6+ characters |
| Mongo timeout | Atlas > Network Access > Add Current IP |
| Live par "Stream connect nahi hua" | Reconnect dabao; login dobara; backend chal raha ho |
| Pehla frame der se | Models load hote hain (20-60 s) |
| Camera nahi khulta | Meet/Zoom band karo; index 0 ya 1 |
| Video preview nahi (click picker) | mp4 H.264 use karo |
| `Wrong Way ke liye --allowed-dir` error | Ye jaan-boojh kar hai: bina direction rule nahi chalta |

## 8. Challan fine rates (Pakistan)
- Fines come from `backend/fines.json` (editable, no code change). Default region = **Sindh (Karachi)**. For Punjab set the environment variable `FINE_REGION=punjab` in `.env` and restart the backend.
- The Violations page shows the fine per row; the Challan PDF shows legal basis, fine amount, demerit points and the schedule used.
- Fine depends on the vehicle class (bike, car, LTV/bus, HTV/truck). If the class is unknown the officer sets the amount.
- Rates differ by province and were revised several times in 2025-26. The file records where each number came from and when it was checked. Always verify with the official notification / traffic police before issuing a real challan.
