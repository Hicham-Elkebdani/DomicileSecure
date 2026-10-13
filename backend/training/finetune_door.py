"""Fine-tune YOLO to recognise the state of *your* door (classes: door_open, door_closed).

1. Record your door in different conditions (day, night, lights on/off, people passing):
   200-500 images are enough to start.
2. Annotate them with Roboflow, CVAT or Label Studio and export in "YOLO" format into
   data/door/ (see data/README.md for the expected layout).
3. Train:
       python -m training.finetune_door --data data/door/data.yaml --epochs 60
4. The best weights are copied to artifacts/vision/door_yolo.pt; set in .env:
       WORKER_DOOR_MODEL_PATH=artifacts/vision/door_yolo.pt
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.core.config import BACKEND_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--data", type=Path, required=True, help="YOLO data.yaml")
    parser.add_argument("--base-model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default=None, help="cpu, 0 (first GPU)...")
    parser.add_argument(
        "--output", type=Path, default=BACKEND_DIR / "artifacts/vision/door_yolo.pt"
    )
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.base_model)
    results = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.image_size,
        batch=args.batch,
        device=args.device,
        project=str(BACKEND_DIR / "runs/door"),
        name="train",
        exist_ok=True,
        patience=15,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, args.output)
    metrics = YOLO(str(args.output)).val(data=str(args.data), verbose=False)
    print(f"Door model saved to {args.output} (mAP50={metrics.box.map50:.3f})")


if __name__ == "__main__":
    main()
