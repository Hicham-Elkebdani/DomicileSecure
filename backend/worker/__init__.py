"""Vision worker: reads one camera stream, runs models 1 and 2, sends observations to the API.

One process per camera. The worker is stateless with respect to the database: it only talks
to the API over HTTP, so it can run on another machine (e.g. a small PC next to the camera).
"""
