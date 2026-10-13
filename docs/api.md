# API REST — v1

Base URL : `http://localhost:8000/api/v1` · Documentation interactive (hors production) : `/docs` (Swagger) et `/redoc`.

## Authentification

| Appelant | Mécanisme |
|---|---|
| Utilisateur (frontend) | `POST /auth/login` (formulaire OAuth2 `username`/`password`) → JWT à envoyer dans `Authorization: Bearer <token>` |
| Worker caméra | En-tête `X-API-Key: <WORKER_API_KEY>` sur les routes `/ingest/*` uniquement |
| WebSocket | Premier message `{"type": "auth", "token": "<jwt>"}`, sinon fermeture (code 1008) après 5 s |

Rôles : **membre** (lecture, gestion des personnes et des alertes) et **administrateur** (en plus : caméras, utilisateurs, régénération des résumés). Il n'y a pas d'inscription publique : le premier administrateur est créé en ligne de commande (`python -m app.cli create-admin`).

## Format des erreurs

Toutes les erreurs ont la même forme :

```json
{ "error": { "code": "validation_error", "message": "Requête invalide", "details": { "errors": [...] } } }
```

| HTTP | `code` | Cas |
|---|---|---|
| 401 | `not_authenticated` | Jeton absent, expiré ou invalide ; clé worker invalide |
| 403 | `permission_denied` | Action réservée aux administrateurs |
| 404 | `not_found` | Ressource inexistante |
| 409 | `conflict` | Doublon (nom de caméra, e-mail), caméra désactivée |
| 413 | `payload_too_large` | Photo > `MAX_UPLOAD_SIZE_MB` |
| 422 | `validation_error` | Données invalides, photo sans visage ou avec plusieurs visages |
| 429 | `rate_limited` | Trop de tentatives de connexion |
| 503 | `service_unavailable` | Base indisponible, modèle de visage absent, push non configuré |

Chaque réponse porte un en-tête `X-Request-ID`, repris dans les logs pour le diagnostic.

## Endpoints

| Méthode | Route | Accès | Description |
|---|---|---|---|
| GET | `/health` | public | *Liveness* |
| GET | `/health/ready` | public | *Readiness* : base joignable, moteur d'anomalies actif |
| POST | `/auth/login` | public | Connexion → `{access_token, token_type, expires_in}` |
| GET | `/auth/me` | membre | Utilisateur connecté |
| GET · POST | `/users` | admin | Lister / créer des comptes |
| GET · POST | `/cameras` | membre · admin | Lister / créer |
| GET · PATCH · DELETE | `/cameras/{id}` | membre · admin · admin | Détail / modifier / supprimer |
| GET | `/persons?role=` | membre | Lister (filtre `resident`, `guest`, `visitor`) |
| POST | `/persons` | membre | Créer un résident ou un invité |
| GET · PATCH · DELETE | `/persons/{id}` | membre | Détail / renommer, changer de rôle (promouvoir un visiteur) / supprimer (+ signatures) |
| POST | `/persons/{id}/faces` | membre | `multipart/form-data` champ `photo` → calcule et stocke la signature ; **la photo n'est pas conservée** |
| DELETE | `/persons/{id}/faces` | membre | Supprimer toutes les signatures faciales (droit à l'effacement) |
| GET | `/events` | membre | Filtres `camera_id`, `kind`, `identity`, `person_id`, `start`, `end`, pagination `limit`/`offset` |
| GET | `/events/activity?days=7` | membre | Compteurs par jour (graphique) |
| GET | `/alerts` | membre | Filtres `status`, `min_severity`, `start`, `end`, pagination |
| GET | `/alerts/counts` | membre | Nombre d'alertes non traitées par gravité |
| PATCH | `/alerts/{id}` | membre | `{"status": "acknowledged" \| "dismissed" \| "new"}` |
| GET | `/summaries` | membre | Résumés archivés |
| GET | `/summaries/today` | membre | Résumé du jour, calculé en temps réel |
| GET | `/summaries/{YYYY-MM-DD}` | membre | Résumé d'une date |
| POST | `/summaries/{YYYY-MM-DD}/generate` | admin | (Re)générer et archiver |
| GET | `/notifications/config` | membre | Push activé ? clé publique VAPID |
| POST · DELETE | `/notifications/subscriptions` | membre | Abonner / désabonner cet appareil |
| POST | `/notifications/test` | membre | Notification de test |
| POST | `/ingest/observations` | worker | Lot d'observations (voir ci-dessous) |
| POST | `/ingest/cameras/{id}/heartbeat` | worker | Signal de vie de la caméra |
| WS | `/ws` | membre | Flux temps réel |

## Contrat worker → API

Défini **une seule fois** dans `backend/app/schemas/ingest.py`, et importé par le worker : les deux côtés ne peuvent pas diverger.

```json
POST /api/v1/ingest/observations
X-API-Key: ...

{
  "camera_id": "30233940-56b6-4480-b804-442548dfd162",
  "observations": [
    {
      "observed_at": "2026-10-01T02:14:07.120Z",
      "kind": "person",
      "label": "person",
      "confidence": 0.91,
      "track_id": 12,
      "bbox": [120.0, 40.5, 310.2, 470.0],
      "face": { "embedding": [0.012, -0.087, ...128 valeurs], "model_name": "sface-2021dec", "detection_score": 0.94 }
    },
    { "observed_at": "2026-10-01T02:14:09Z", "kind": "door", "label": "door_open", "confidence": 0.88 }
  ]
}
```

Règles de validation : date avec fuseau et pas dans le futur ; `kind` ∈ `person|animal|vehicle|door` ; un visage seulement sur une personne ; une porte seulement `door_open|door_closed` ; 1 à 200 observations par lot.

Réponse : `{"events_created": 2, "alerts_created": 1}`.

## Messages WebSocket (serveur → client)

```json
{"type": "ready", "data": {"user": "vous@exemple.com"}}
{"type": "event.created", "data": { ...EventRead }}
{"type": "alert.created", "data": { ...AlertRead }}
{"type": "message", "data": {"title": "Résumé du jour", "body": "...", "url": "/summary"}}
```
