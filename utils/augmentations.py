import albumentations as A
import cv2
import numpy as np


class PlateAugmentations:
    @staticmethod
    def get_train_augmentations(img_size=640):
        return A.Compose(
            [
                # Color transforms
                A.RandomBrightnessContrast(p=0.5),
                A.RandomGamma(p=0.3),
                A.CLAHE(p=0.3),
                A.HueSaturationValue(p=0.3),
                # Blur/noise
                A.GaussNoise(var_limit=(10, 50), p=0.3),
                A.MotionBlur(blur_limit=5, p=0.2),
                # Weather effects
                A.RandomShadow(p=0.1),
                A.RandomSunFlare(p=0.1),
                # Geometric
                A.ShiftScaleRotate(
                    shift_limit=0.1, scale_limit=0.1, rotate_limit=10, p=0.5
                ),
                # Perspective
                A.Perspective(scale=(0.05, 0.1), p=0.3),
                # Plate-specific
                A.RandomGridShuffle(grid=(3, 3), p=0.1),  # Simulates partial occlusion
            ],
            bbox_params=A.BboxParams(
                format="yolo", min_visibility=0.4, label_fields=["class_labels"]
            ),
        )

    @staticmethod
    def get_val_augmentations(img_size=640):
        return A.Compose(
            [
                A.Resize(img_size, img_size),
            ],
            bbox_params=A.BboxParams(
                format="yolo", min_visibility=0.4, label_fields=["class_labels"]
            ),
        )
