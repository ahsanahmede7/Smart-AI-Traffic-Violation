# Smart Traffic AI

AI-Powered Smart Traffic Intelligence & Violation Monitoring System.
Video -> YOLO + ByteTrack -> rule engine (No Helmet / Wrong Way / Red Light) -> evidence image -> MongoDB -> FastAPI -> React dashboard -> analytics, risk prediction, PDF report.

## Setup (Windows, PowerShell, from project root)
```
python -m venv venv
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& ".\venv\Scripts\Activate.ps1")
pip install -r requirements.txt
copy .env.example .env     # then edit .env (never upload .env to GitHub)
```

## Run (3 terminals)
1. Backend: `python -m uvicorn backend.main:app --reload`  -> http://127.0.0.1:8000/docs
2. Dashboard: `cd frontend-react ; npm install ; npm run dev` -> http://localhost:5173
3. Pipeline test (no DB): `python -m ai.pipeline --video data\traffic.mp4 --vehicle yolov8s.pt --dry --save-img --show --stride 3`
   Real run: same without `--dry`, add `--location "Main Road"`

## New modules
- `ai/prediction/risk_model.py` : Random Forest hourly risk. `python -m ai.prediction.risk_model --train`
  (uses MongoDB if >= 7 days of data, otherwise synthetic demo data; the model prints which one it used).
- `backend/extras.py` : `/api/predict`, `/api/alerts`, `/api/reports/daily.pdf` (JWT protected). Already included in `backend/main.py`.
- Dashboard: new pages Alerts and Risk, and a Download PDF button on Reports (frontend-react/src/pages).
- `tests/test_engine.py` : `python -m pytest tests -q` (6 engine tests passed when run).

## Not verified yet (needs your machine / data)
- Helmet threshold: Without Helmet scores were 0.26-0.37 on traffic.mp4 vs rule min_conf 0.5. Inspect evidence images before changing `min_conf`.
- Wrong Way / Red Light with real videos, MongoDB insert from pipeline, Light model.
- backend/extras.py and the new React pages were NOT run (no packages/network where they were written); only Python syntax was checked.

## Credits
Traffic model dataset: Roboflow `road-traffic-pmqwc` (Saul Casas Lorenzo, CC BY 4.0).

## Deployment
Frontend -> Vercel, backend -> Render, DB -> MongoDB Atlas. YOLO inference is heavy: keep the pipeline running locally (or Colab) for the demo.

## Presentation flow
Problem -> Solution -> AI (YOLO + tracking + rules) -> Data science (analytics + prediction) -> Backend -> Frontend -> Live demo (video -> violation -> evidence -> DB -> dashboard).
Be ready to say honestly: detections need human review; helmet model is weaker on small riders in 4K traffic video.
