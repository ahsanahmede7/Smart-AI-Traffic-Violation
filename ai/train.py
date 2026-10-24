"""Phase 4: python ai/train.py  (GPU/Colab recommended). Best model -> ai/models/best.pt"""
from ultralytics import YOLO
m = YOLO("yolov8s.pt")
m.train(data="ai/data.yaml", epochs=60, imgsz=640, batch=16, project="ai/runs", name="traffic")
print(m.val())  # precision, recall, mAP50, mAP50-95 + confusion matrix saved in ai/runs
