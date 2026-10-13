"""Download the pre-trained vision models into artifacts/vision/ and verify their checksums.

    python scripts/download_models.py

* YuNet face detector and SFace face recognizer (OpenCV Zoo, Apache-2.0 licence)
* YOLO11n object detector (Ultralytics, AGPL-3.0 licence): downloaded on first use
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TARGET = BACKEND_DIR / "artifacts" / "vision"
ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"

MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        f"{ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "face_recognition_sface_2021dec.onnx": (
        f"{ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, (url, checksum) in MODELS.items():
        path = TARGET / name
        if path.is_file() and sha256(path) == checksum:
            print(f"✓ {name} already present")
            continue
        print(f"↓ {name} ...")
        urllib.request.urlretrieve(url, path)
        if sha256(path) != checksum:
            path.unlink(missing_ok=True)
            print(f"✗ checksum mismatch for {name}", file=sys.stderr)
            return 1
        print(f"✓ {name} ({path.stat().st_size / 1e6:.1f} MB)")

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed: YOLO will be downloaded by the worker on first start")
        return 0
    YOLO(str(TARGET / "yolo11n.pt"))
    print("✓ yolo11n.pt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
