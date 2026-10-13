# Stratégie de tests

## Pyramide

| Niveau | Où | Ce qui est vérifié | Outils |
|---|---|---|---|
| **Unitaire** | `backend/tests/unit/` | Règles d'anomalies, variables LSTM, galerie de visages, sécurité (JWT, hachage, clé API), limiteur de débit, rédaction des résumés, agrégation des pistes, debouncer de porte, client worker (panne d'API), pipeline caméra | pytest, faux objets |
| **Intégration** | `backend/tests/integration/` | Application FastAPI complète sur une base SQLite en mémoire : authentification, droits, CRUD, enrôlement de visage, pipeline d'ingestion de bout en bout, dédoublonnage, tick d'anomalies, résumés, WebSocket, notifications | pytest-asyncio, httpx, TestClient |
| **ML** (marqué `slow`) | `tests/unit/test_lstm_pipeline.py` | Simulation → entraînement d'un mini-LSTM → artefact → chargement dans le moteur hybride → repli sur les règles si modèle absent | PyTorch |
| **Évaluation modèle** | `training/evaluate.py` | Rappel par type d'anomalie, fausses alertes par jour : règles vs LSTM vs hybride | Script |
| **Frontend statique** | `frontend/` | Types (TypeScript strict), lint (ESLint + règles React), build de production | tsc, ESLint, next build |

**Principe** : les tests passent par la même fabrique (`create_app`) et le même conteneur de dépendances que la production. Seules les frontières externes sont remplacées : base en mémoire, faux modèle de visage déterministe et faux transport HTTP pour le worker. On teste donc le vrai code et pas des simulacres.

## Commandes

```bash
cd backend
pytest                          # tous les tests (≈ 15 s)
pytest -m "not slow"            # sans l'entraînement du mini-LSTM
pytest --cov --cov-report=html  # couverture → htmlcov/index.html
pytest tests/integration/test_ingest_pipeline.py -k night -v

cd frontend
npm run lint && npm run typecheck && npm run build
```

## Couverture actuelle

79 tests, **84 %** de couverture sur `app`, `vision` et `worker`. Les parties non couvertes sont surtout les adaptateurs vers le matériel et les services externes : lecture RTSP, YOLO réel, envoi Web Push réel. Ils sont validés par les tests manuels ci-dessous.

## Tests manuels de bout en bout (checklist de sprint)

1. `python scripts/seed_demo.py`, puis parcourir toutes les pages du frontend (clair/sombre, mobile).
2. Webcam : `WORKER_CAMERA_SOURCE=0 WORKER_PREVIEW=true python -m worker`. Passer devant la caméra, vérifier **un** événement « inconnu » et une alerte en temps réel.
3. Enrôler son visage, repasser devant la caméra : l'événement doit indiquer « membre du foyer », sans alerte.
4. Activer les notifications dans **Paramètres**, cliquer sur « Envoyer un test », puis fermer l'onglet et provoquer une alerte.
5. Arrêter l'API pendant que le worker tourne, la relancer : les observations en attente doivent arriver.

## Intégration continue

`.github/workflows/ci.yml` exécute à chaque *push* et *pull request* : Ruff (lint et format), `alembic check`, pytest avec couverture, puis ESLint, TypeScript et build Next.js.

## Pistes d'amélioration

- Tests E2E navigateur (Playwright) : connexion → alerte temps réel → acquittement.
- Tests de charge de `/ingest/observations` (Locust) avec plusieurs workers simulés.
- Jeu de vidéos de référence annotées pour mesurer le modèle 1 dans *vos* conditions (mAP, suivi).
- Évaluation du modèle 2 sur LFW, avec la courbe faux acceptés / faux rejets pour choisir le seuil.
