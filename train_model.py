from ultralytics import YOLO
import os

def train_model():
    # Load a model
    model = YOLO('yolov8n.pt')  # load a pretrained model (recommended for training)

    # Train the model
    results = model.train(
        data='license_plate.yaml',      # path to data config file
        epochs=100,                     # number of training epochs
        imgsz=640,                      # image size
        batch=16,                       # batch size
        patience=20,                    # early stopping patience
        save=True,                      # save checkpoints
        device='0',                     # cuda device (use 'cpu' if no GPU)
        workers=8,                      # number of worker threads
        project='runs/train',           # save to project/name
        name='license_plate_model',     # experiment name
        exist_ok=True,                  # existing project/name ok, do not increment
        pretrained=True,                # use pretrained model
        optimizer='auto',               # optimizer (SGD, Adam, etc.)
        verbose=True,                   # print verbose output
        seed=42,                        # random seed for reproducibility
        deterministic=True,             # deterministic training
    )

    # Save the trained model
    model.export(format='onnx')  # export the model to ONNX format

if __name__ == "__main__":
    train_model() 