# artifacts/

Trained and pre-trained model files. **Not versioned in Git** (size, licences); they are
reproducible with the commands below.

```
artifacts/
├── vision/
│   ├── face_detection_yunet_2023mar.onnx    # python scripts/download_models.py
│   ├── face_recognition_sface_2021dec.onnx  # python scripts/download_models.py
│   ├── yolo11n.pt                           # downloaded automatically
│   └── door_yolo.pt                         # python -m training.finetune_door (optional)
└── anomaly_lstm/
    ├── 20261012-181502/                     # one folder per trained version
    │   ├── model.pt
    │   └── metadata.json                    # features, threshold, metrics, data hash
    └── latest/                              # version loaded by the API (--promote)
```

Rollback = copy an older version folder over `latest/` and restart the API.
