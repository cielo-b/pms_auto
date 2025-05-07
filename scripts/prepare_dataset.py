import os
import shutil
import random
from sklearn.model_selection import train_test_split


def split_dataset(dataset_path="dataset-new/raw", output_path="../dataset/processed"):
    # Create directories
    splits = ["train", "val", "test"]
    for split in splits:
        os.makedirs(f"{output_path}/{split}/images", exist_ok=True)
        os.makedirs(f"{output_path}/{split}/labels", exist_ok=True)

    # Get all images
    images = [f for f in os.listdir(f"{dataset_path}") if f.endswith(".jpg")]
    random.shuffle(images)

    # Split 70% train, 20% val, 10% test
    train, test = train_test_split(images, test_size=0.3, random_state=42)
    val, test = train_test_split(test, test_size=0.33, random_state=42)

    # Helper function to copy files
    def copy_files(files, split):
        for file in files:
            # Copy image
            shutil.copy(
                f"{dataset_path}/images/{file}", f"{output_path}/{split}/images/{file}"
            )
            # Copy corresponding label
            label_file = os.path.splitext(file)[0] + ".txt"
            if os.path.exists(f"{dataset_path}/labels/{label_file}"):
                shutil.copy(
                    f"{dataset_path}/labels/{label_file}",
                    f"{output_path}/{split}/labels/{label_file}",
                )

    copy_files(train, "train")
    copy_files(val, "val")
    copy_files(test, "test")


if __name__ == "__main__":
    split_dataset()
