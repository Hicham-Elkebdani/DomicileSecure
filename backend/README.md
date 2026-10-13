# DomicileSecure — Backend

API FastAPI, worker de vision et pipeline ML. Vue d'ensemble : [../README.md](../README.md) · architecture : [../docs/architecture.md](../docs/architecture.md).

## Installation

```bash
python -m venv .venv
# Windows : .\.venv\Scripts\Activate.ps1      Linux/macOS : source .venv/bin/activate
pip install -r requirements/dev.txt                 # API + outils de test (léger)
pip install -r requirements/vision.txt              # + worker (YOLO, PyTorch)
pip install -r requirements/ml.txt                  # + entraînement / inférence LSTM
cp .env.example .env                                # Windows : Copy-Item .env.example .env
python scripts/generate_secrets.py                  # coller les valeurs dans .env
python scripts/download_models.py
alembic upgrade head
```

Les dépendances sont séparées par rôle : un serveur d'API qui n'utilise que les règles n'a pas besoin de PyTorch, et une machine qui n'héberge qu'un worker n'a pas besoin de l'API.

## Lancer

| Processus | Commande |
|---|---|
| API (développement) | `uvicorn app.main:create_app --factory --reload` → <http://localhost:8000/docs> |
| Worker d'une caméra | `python -m worker` (variables `WORKER_*` dans `.env`) |
| Données de démo | `python scripts/seed_demo.py` → `demo@example.com` / `demo-password-123` |

## Administration (CLI)

```bash
python -m app.cli create-admin --email vous@exemple.com
python -m app.cli create-camera --name "Entrée" --location "Porte" --has-door
python -m app.cli list-cameras
python -m app.cli generate-summary --day 2026-10-01
```

## IA / entraînement

```bash
python -m training.simulate_events --days 120 --out data/synthetic
python -m training.train_lstm --events data/synthetic/events.csv --anomalies data/synthetic/anomalies.csv --promote
python -m training.evaluate --events data/synthetic/events.csv --anomalies data/synthetic/anomalies.csv
python -m training.export_events --out data/real/events.csv --days 60
python -m training.finetune_door --data data/door/data.yaml
```

Détails : [../docs/ml.md](../docs/ml.md).

## Qualité

```bash
ruff check . && ruff format --check .
pytest --cov
alembic check
```

## Organisation du code

| Dossier | Contenu |
|---|---|
| `app/core` | Configuration (`Settings`), sécurité, logs, erreurs, middlewares |
| `app/db`, `app/models` | Moteur SQLAlchemy async, tables |
| `app/schemas` | Contrats Pydantic, dont `ingest.py` (contrat worker ↔ API) |
| `app/repositories` | Accès aux données (seule couche qui écrit du SQL) |
| `app/services` | Logique métier : identité, ingestion, alertes, résumé, notifications |
| `app/anomaly` | Modèle 3 : `rules/`, `lstm/`, `composite.py`, `factory.py` |
| `app/api/v1/routes` | Endpoints HTTP et WebSocket |
| `app/container.py` | Composition des dépendances (implémentations concrètes) |
| `vision/` | Adaptateurs des modèles 1 et 2 (YOLO, YuNet/SFace) |
| `worker/` | Source vidéo, agrégation par piste, porte, client HTTP résilient, pipeline |
| `training/` | Simulation, export, fenêtres, entraînement, évaluation, fine-tuning porte |
| `scripts/` | Modèles, secrets, données de démo |
