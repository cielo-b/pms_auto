# scripts/train.py
from ultralytics import YOLO
import torch

def train_model():
    # Clear GPU cache
    torch.cuda.empty_cache()
    
    # Load model (use yolov8s for better accuracy than n)
    model = YOLO("yolov8s.pt")
    
    # Training parameters
    params = {
        'data': 'configs/license_plate_aug.yaml',
        'epochs': 300,
        'imgsz': 640,
        'batch': 16,
        'optimizer': 'AdamW',
        'lr0': 3e-4,
        'cos_lr': True,  # Cosine learning rate scheduler
        'weight_decay': 0.05,
        'patience': 50,
        'device': '0',
        'name': 'new_best',
        'pretrained': True,
        'augment': True,
        'dropout': 0.2,
        'val': True,
        'save_period': 10  # Save checkpoint every 10 epochs
    }
    
    # Start training
    results = model.train(**params)
    
    # Export to different formats
    model.export(format='onnx', simplify=True, dynamic=True)
    model.export(format='engine', device=0)  # TensorRT
    
    print("Training complete! Model saved as 'new-best.pt'")

if __name__ == '__main__':
    train_model()