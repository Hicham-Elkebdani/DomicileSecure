# data/

Datasets. **Not versioned in Git**: they may contain personal or biometric data.

```
data/
├── synthetic/          # python -m training.simulate_events
│   ├── events.csv
│   └── anomalies.csv   # ground truth for evaluation
├── real/               # python -m training.export_events
│   └── events.csv
├── door/               # YOLO dataset for the door model (training.finetune_door)
│   ├── data.yaml
│   ├── images/{train,val}/*.jpg
│   └── labels/{train,val}/*.txt
└── reports/            # python -m training.evaluate --report ...
```

`data/door/data.yaml`:

```yaml
path: data/door
train: images/train
val: images/val
names:
  0: door_open
  1: door_closed
```

Face photos are **never** stored: the API keeps only the face signature (embedding).
