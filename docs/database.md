# Base de données

SQLite en développement (aucune installation), PostgreSQL en production. Le code est identique : seule `DATABASE_URL` change.

## Schéma

```mermaid
erDiagram
    users ||--o{ push_subscriptions : "possède"
    users ||--o{ alerts : "traite (resolved_by)"
    cameras ||--o{ events : "observe"
    cameras ||--o{ alerts : "concerne"
    persons ||--o{ face_embeddings : "signatures"
    persons ||--o{ events : "identifiée dans"
    persons ||--o{ alerts : "concerne"
    events ||--o{ alerts : "déclenche"

    users {
        uuid id PK
        string email UK
        string hashed_password "Argon2"
        bool is_admin
        bool is_active
    }
    cameras {
        uuid id PK
        string name UK
        bool has_door
        string door_state "unknown|open|closed"
        datetime door_state_changed_at
        datetime last_seen_at
    }
    persons {
        uuid id PK
        string display_name
        string role "resident|guest|visitor"
        int sightings_count
        datetime first_seen_at
        datetime last_seen_at
    }
    face_embeddings {
        uuid id PK
        uuid person_id FK "ON DELETE CASCADE"
        bytes vector "float32 x dim"
        int dim
        string model_name
        string source "enrollment|observation"
    }
    events {
        uuid id PK
        uuid camera_id FK
        datetime occurred_at "index"
        string kind "person|animal|vehicle|door"
        string label
        float confidence
        int track_id
        string identity "resident|guest|visitor|unknown"
        uuid person_id FK "ON DELETE SET NULL"
        float match_score
        json bbox
    }
    alerts {
        uuid id PK
        string source "rules|lstm"
        string rule_code
        string severity "info..critical"
        string status "new|acknowledged|dismissed"
        string dedupe_key "index"
        json details
        datetime created_at
    }
    push_subscriptions {
        uuid id PK
        uuid user_id FK
        string endpoint UK
        string p256dh
        string auth
    }
    daily_summaries {
        uuid id PK
        date day UK
        text text
        json stats
    }
```

## Choix de modélisation

- **Pas de photos en base.** `face_embeddings.vector` contient 128 flottants (512 octets). Une signature ne permet pas de reconstruire le visage.
- **Pas d'URL RTSP en base.** Les identifiants de caméra restent dans le `.env` du worker.
- **`model_name` sur chaque signature.** Changer de modèle de reconnaissance ne mélange jamais des vecteurs incompatibles : la galerie les sépare par modèle.
- **Enums stockés par valeur** (`"open"`, pas `"OPEN"`) et en `VARCHAR` (`native_enum=False`) : lisibles dans les exports et portables SQLite ↔ PostgreSQL.
- **Toutes les dates en UTC**, via le type `UTCDateTime` qui refuse les dates naïves.
- **Index** sur les requêtes chaudes : `events(camera_id, occurred_at)`, `events(kind, occurred_at)`, `alerts(dedupe_key, created_at)` (dédoublonnage), `alerts(status)`, `persons(role)`.
- **Contraintes nommées** (convention de nommage) : migrations reproductibles d'une base à l'autre.

## Migrations (Alembic)

```bash
alembic upgrade head                                    # appliquer
alembic revision --autogenerate -m "add camera zones"   # après modification d'un modèle
alembic downgrade -1                                    # annuler la dernière
alembic check                                           # vérifier que modèles et migrations sont alignés (utilisé en CI)
```

Relisez toujours une migration générée avant de la committer. Pour SQLite, Alembic utilise le mode *batch*, qui recrée la table pour les `ALTER`.

## Rétention (recommandation)

| Table | Conservation conseillée |
|---|---|
| `events` | 90 jours (au-delà, exporter en CSV pour l'entraînement puis purger) |
| `alerts` | 1 an |
| `face_embeddings` des visiteurs jamais identifiés | 30 jours |

La purge automatique fait partie de la roadmap. Elle est importante pour la conformité RGPD (minimisation des données).
