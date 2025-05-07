# scripts/auto_label.py
import cv2
from ultralytics import YOLO
import os


def auto_label(images_dir="dataset/raw", output_dir="dataset/raw/labels"):
    # Load pretrained plate detection model
    model = YOLO("yolov8n.pt")  # or your custom model

    os.makedirs(output_dir, exist_ok=True)

    for img_file in os.listdir(images_dir):
        if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        # Process image
        img_path = os.path.join(images_dir, img_file)
        img = cv2.imread(img_path)
        results = model(img)

        # Create label file
        label_file = os.path.splitext(img_file)[0] + ".txt"
        with open(os.path.join(output_dir, label_file), "w") as f:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Convert to YOLO format (normalized center-x, center-y, width, height)
                img_h, img_w = img.shape[:2]
                x_center = ((x1 + x2) / 2) / img_w
                y_center = ((y1 + y2) / 2) / img_h
                width = (x2 - x1) / img_w
                height = (y2 - y1) / img_h

                # Write to file (class 0, coordinates)
                f.write(f"0 {x_center} {y_center} {width} {height}\n")

        print(f"Processed {img_file}")


if __name__ == "__main__":
    auto_label()
