# from pathlib import Path
# from ultralytics import YOLO

# HERE = Path(__file__).parent                      # Models/ folder (check.py yahin hai)

# # ---- Settings (sirf yahan badalna hai) ----
# HELMET = HERE / "Helmet" / "best.pt"              # naya helmet model
# TEST_DIR = HERE / "test_images"                   # test tasveerein yahan rakho
# DATA_YAML = None                                  # val ke liye, neeche samjhaya hai
# # -------------------------------------------

# # Step 1: Models/ ke andar jitne best.pt hain, sab ke class names
# print("=== Saare models ===")
# for p in sorted(HERE.rglob("best.pt")):
#     print(p.relative_to(HERE), "->", YOLO(str(p)).names)

# # Step 2: helmet model ko tasveeron par chalao
# print("\n=== Helmet test ===")
# print("Model:", HELMET, "| exists:", HELMET.exists())
# if HELMET.exists():
#     m = YOLO(str(HELMET))
#     imgs = sorted(p for p in TEST_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
#     if not imgs:
#         print(f"'{TEST_DIR}' mein tasveerein nahi hain. Folder banao aur 8-10 tasveerein rakho.")
#     for p in imgs:
#         r = m.predict(str(p), conf=0.25, verbose=False, save=True,
#                       project=str(HERE / "test_out"), name="run", exist_ok=True)[0]
#         print(p.name, "->", [(m.names[int(c)], round(float(s), 2)) for c, s in zip(r.boxes.cls, r.boxes.conf)])
#     print("Boxes wali tasveerein:", HERE / "test_out" / "run")

#     # Step 3: har class ka score (sirf agar DATA_YAML diya ho)
#     if DATA_YAML:
#         m.val(data=str(DATA_YAML))

from ultralytics import YOLO
from pathlib import Path

# 1. Model ka path
model_path = Path(
    r"D:\AI_course\Smart-AI-Traffic Project\Smart-Traffic-AI\Smart-Traffic-AI\Models\Helmet\best.pt"
)

# 2. Input image ka path
image_path = Path(
    r"D:\AI_course\Smart-AI-Traffic Project\Smart-Traffic-AI\Smart-Traffic-AI\data\petrol.webp"
)

# 3. Output folder
output_dir = Path(
    r"D:\AI_course\Smart-AI-Traffic Project\Smart-Traffic-AI\Smart-Traffic-AI\prediction_results"
)

# 4. Check paths
if not model_path.exists():
    raise FileNotFoundError(f"Model nahi mila: {model_path}")

if not image_path.exists():
    raise FileNotFoundError(f"Image nahi mili: {image_path}")

# 5. Load model
model = YOLO(str(model_path))

print("Model classes:", model.names)

# 6. Prediction aur image save
results = model.predict(
    source=str(image_path),
    conf=0.25,
    save=True,
    project=str(output_dir.parent),
    name=output_dir.name,
    exist_ok=True
)

# 7. Detection details
for result in results:
    for box in result.boxes:
        class_id = int(box.cls.item())
        confidence = float(box.conf.item())
        coordinates = box.xyxy[0].tolist()

        print(
            f"Class: {model.names[class_id]} | "
            f"Confidence: {confidence:.2f} | "
            f"Box: {coordinates}"
        )

# 8. Saved image ka exact path
saved_image = output_dir / image_path.name

print("\nPrediction complete!")
print("Saved image path:", saved_image)
print("Image exists:", saved_image.exists())
