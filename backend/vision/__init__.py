"""Computer-vision adapters shared by the API (face enrollment) and the camera worker.

Every model sits behind a small abstract interface (`ObjectDetector`, `FaceEmbedder`) so an
implementation can be swapped (YOLO -> RT-DETR, SFace -> ArcFace...) without touching callers.
Heavy libraries are imported lazily inside the implementations.
"""
