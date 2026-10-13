"""Anomaly engine (model 3).

Phase 1 is a rule-based detector, phase 2 an LSTM autoencoder. Both implement
`AnomalyDetector`, so the rest of the application never knows which one is running:
switching is a single `ANOMALY_ENGINE` setting.
"""
