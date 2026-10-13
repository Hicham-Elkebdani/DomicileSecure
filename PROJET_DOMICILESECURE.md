# DomicileSecure — Assistant IA de Sécurité Domestique Intelligente

> Document de référence du projet de stage — Elkebdani Hicham
> À placer à la racine du repository (ou dans `docs/`), à mettre à jour à chaque sprint.

---

## 1. Informations du stage

| Élément | Détail |
|---|---|
| Stagiaire | Elkebdani Hicham |
| Entreprise d'accueil | XeleronAI LTD (Private Limited Company, Royaume-Uni) |
| N° Companies House | 16311684 (immatriculée le 12/03/2025, statut : active) |
| Siège social | 71-75 Shelton Street, Covent Garden, Londres, WC2H 9JQ |
| Sujet | DomicileSecure — Assistant IA de Sécurité Domestique Intelligente |
| Durée | 2 mois |
| Modalité | 100 % à distance (Remote — United Kingdom) |
| Plateforme de candidature | Stagi-GO |
| Compétences demandées | React/Next.js, Python (FastAPI/Flask), reconnaissance faciale/objet pré-entraînée, REST API, notifications push |

### Modalités de suivi
- Travail organisé en **sprints**.
- Fin de chaque sprint : **compte rendu d'avancement + code source** poussés sur le repository partagé.
- Vérifications effectuées par l'entreprise à chaque fin de sprint.
- Rigueur et **documentation** attendues.
- Fin de stage : **attestation** basée sur l'avancement ; possibilité de recommandation pour pré-embauche / embauche.

---

## 2. Problème et objectifs

**Problème :** une caméra qui alerte à chaque mouvement (un chat qui passe) finit par être ignorée.

**Objectifs :**
1. **Reconnaître les personnes** : membre du foyer / invité récurrent / inconnu.
2. **Détecter des anomalies contextuelles** (porte restée ouverte, présence à une heure inhabituelle) plutôt que le simple mouvement.
3. **Alertes intelligentes** (push) + **résumé quotidien** de l'activité en quelques lignes.

---

## 3. Architecture générale

```
Caméra (webcam / caméra IP RTSP)
   │
   ▼
[Modèle 1] Détection d'objets (YOLO) → person, cat, dog, car, porte ouverte/fermée
   │  si "person" → découpe du visage
   ▼
[Modèle 2] Reconnaissance faciale → membre / invité récurrent / inconnu
   │
   ▼
Événement enregistré en base (qui, quoi, caméra, horodatage)
   │
   ▼
[Modèle 3] Moteur d'anomalies
   Phase 1 : règles explicites (if/else)  ──►  Phase 2 : LSTM (même interface)
   │
   ▼
Alertes (Web Push + WebSocket) + Résumé quotidien → Interface Next.js
```

**Principe clé :** la lecture vidéo et l'inférence tournent dans un **worker séparé** (processus Python indépendant). L'API FastAPI ne fait que lire/écrire en base et exposer les résultats. On ne lance jamais l'inférence dans une requête HTTP.

---

## 4. Stack technique (sans Docker)

### Environnement
| Outil | Usage |
|---|---|
| Python 3.11+ + `venv` | Environnement isolé du backend |
| `requirements.txt` | Liste des dépendances Python |
| Fichier `.env` + `python-dotenv` / `pydantic-settings` | Configuration (seuils, horaires, mode règles/LSTM, clés) |
| Node.js LTS + npm | Frontend Next.js |
| Git + GitHub | Versionnement, livraison par sprint |

### Backend
| Outil | Rôle |
|---|---|
| FastAPI + Uvicorn | API REST + WebSocket temps réel |
| Pydantic | Schémas de validation (entrée / sortie) |
| SQLAlchemy (ou SQLModel) + Alembic | ORM + migrations |
| SQLite → PostgreSQL | SQLite au début (aucune installation), PostgreSQL installé localement plus tard si besoin |
| APScheduler | Tâches planifiées (résumé quotidien) |
| OpenCV | Lecture du flux vidéo (`cv2.VideoCapture(0)` ou URL RTSP) |
| python-jose / passlib | Authentification JWT |
| pytest + httpx | Tests |

### Vision / IA
| Outil | Rôle |
|---|---|
| Ultralytics YOLO (v8 / 11) | Modèle 1 — détection d'objets (pré-entraîné COCO) |
| ByteTrack (intégré à Ultralytics) | Suivi d'une même personne entre images → évite les alertes en double |
| InsightFace (ArcFace) ou face_recognition (dlib) | Modèle 2 — embeddings de visages |
| NumPy → FAISS | Stockage / recherche des embeddings |
| scikit-learn (DBSCAN) | Regroupement des inconnus → détection des invités récurrents |
| PyTorch | Modèle 3 — LSTM (phase 2) |

### Notifications et frontend
| Outil | Rôle |
|---|---|
| pywebpush + clés VAPID | Envoi des notifications push |
| Next.js (React) + Tailwind CSS + shadcn/ui | Interface |
| TanStack Query | Appels API |
| Recharts | Graphiques d'activité |
| Service Worker | Réception des notifications push dans le navigateur |

---

## 5. Structure du projet

```
domicilesecure/
├── backend/
│   ├── app/
│   │   ├── main.py                    # création de l'application FastAPI
│   │   ├── core/
│   │   │   ├── config.py              # lecture du .env (seuils, horaires, ANOMALY_ENGINE=rules|lstm)
│   │   │   └── security.py            # JWT
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/                    # tables SQLAlchemy
│   │   │   ├── person.py              # membres, invités, embeddings
│   │   │   ├── camera.py
│   │   │   ├── event.py               # chaque détection
│   │   │   └── alert.py
│   │   ├── schemas/                   # modèles Pydantic
│   │   ├── api/v1/routes/
│   │   │   ├── auth.py
│   │   │   ├── cameras.py
│   │   │   ├── persons.py             # ajout d'un membre + upload photos
│   │   │   ├── events.py
│   │   │   ├── alerts.py
│   │   │   ├── summary.py             # GET /summary/today
│   │   │   ├── notifications.py       # abonnement push
│   │   │   └── ws.py                  # WebSocket alertes en direct
│   │   ├── services/
│   │   │   ├── detection_service.py   # Modèle 1
│   │   │   ├── face_service.py        # Modèle 2
│   │   │   ├── anomaly/
│   │   │   │   ├── base.py            # interface commune : evaluate(events) -> list[Anomaly]
│   │   │   │   ├── rules_engine.py    # Phase 1
│   │   │   │   └── lstm_detector.py   # Phase 2
│   │   │   ├── summary_service.py
│   │   │   └── push_service.py
│   │   ├── workers/
│   │   │   └── camera_worker.py       # caméra → modèles → événements → anomalies
│   │   └── ml/
│   │       ├── weights/               # fichiers .pt (non versionnés si trop lourds)
│   │       └── training/
│   │           ├── simulate_events.py # génération de données synthétiques
│   │           ├── train_lstm.py
│   │           └── finetune_door.py
│   ├── alembic/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/                          # Next.js
├── data/                              # images, annotations (hors Git si volumineux)
├── docs/
│   ├── sprint-1.md
│   ├── sprint-2.md
│   └── ...
├── .gitignore
└── README.md
```

### Endpoints principaux (v1)
| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/v1/auth/login` | Connexion |
| GET / POST | `/api/v1/persons` | Lister / ajouter un membre ou un invité |
| POST | `/api/v1/persons/{id}/photos` | Ajouter des photos → calcul des embeddings |
| GET / POST | `/api/v1/cameras` | Gérer les caméras |
| GET | `/api/v1/events` | Historique des détections (filtres date, caméra, type) |
| GET | `/api/v1/alerts` | Liste des alertes |
| PATCH | `/api/v1/alerts/{id}` | Marquer une alerte comme lue / fausse alerte |
| GET | `/api/v1/summary/today` | Résumé du jour |
| POST | `/api/v1/notifications/subscribe` | Enregistrer un abonnement push |
| WS | `/api/v1/ws/alerts` | Alertes en temps réel |

---

## 6. Les trois modèles

### Modèle 1 — Détection d'objets
- YOLO pré-entraîné COCO : `person`, `cat`, `dog`, `car`… sans entraînement.
- Tracking ByteTrack : une personne = un identifiant, pas une alerte par image.
- État de la porte : fine-tuning YOLO sur deux classes (`door_open`, `door_closed`).

### Modèle 2 — Reconnaissance faciale
- Chaque visage → vecteur (embedding).
- Comparaison par similarité cosinus avec les membres enregistrés (seuil configurable dans `.env`).
- Inconnus : embeddings conservés puis regroupés (DBSCAN). Un même visage vu plusieurs fois → proposition « invité récurrent » à l'utilisateur.

### Modèle 3 — Moteur d'anomalies

**Phase 1 : règles explicites**
```python
nuit = hour >= 23 or hour < 6

if objet in ("cat", "dog"):
    ignorer()
elif person_type == "membre":
    journaliser()
elif person_type == "inconnu" and nuit:
    alerte(niveau="HAUTE")
elif person_type == "inconnu":
    alerte(niveau="MOYENNE")

if door_state == "open" and duree_ouverture > 10 * 60 and aucun_membre_present:
    alerte(niveau="MOYENNE", motif="porte restée ouverte")
```
Toutes les valeurs (heures de nuit, durée max porte, seuils) sont dans `.env`, pas dans le code.

**Phase 2 : LSTM**
- Entrée : séquence de fenêtres de temps (ex. 5 min) avec : nb membres, nb invités, nb inconnus, état de la porte, heure (sin/cos), jour de la semaine.
- Modèle conseillé : **LSTM Autoencoder**. Il apprend la routine normale ; une erreur de reconstruction élevée = anomalie. Peu d'exemples d'anomalies nécessaires.
- Même interface que le moteur de règles → bascule par `ANOMALY_ENGINE=lstm` dans `.env`.
- Évaluation : comparer les anomalies trouvées par le LSTM à celles des règles.

### Résumé quotidien
- V1 : texte généré par template.
  Exemple : « Aujourd'hui : 3 membres, 1 invité, 0 inconnu. Porte d'entrée ouverte 12 min à 14h05. Aucune alerte critique. »
- V2 (optionnel) : reformulation par un LLM.

---

## 7. Collecte des données

| Modèle | Source | Quantité indicative | Outils |
|---|---|---|---|
| Modèle 1 — objets | Pré-entraîné COCO (rien à collecter) | — | Ultralytics |
| Modèle 1 — porte | Photos/vidéos de ta propre porte (jour, nuit, éclairages différents) | 200 à 500 images | Roboflow, CVAT ou Label Studio |
| Modèle 1 — tests | Vidéos libres (Pexels, Pixabay), Open Images | — | OpenCV |
| Modèle 2 — membres | Photos des membres du foyer **avec leur consentement** | 5 à 10 photos / personne | Script d'enrôlement via l'API |
| Modèle 2 — évaluation | Dataset public LFW | — | — |
| Modèle 3 — LSTM | Événements réels enregistrés pendant la phase règles | Plusieurs jours / semaines | Base de données du projet |
| Modèle 3 — LSTM | Données synthétiques (routine simulée + anomalies injectées) | Plusieurs mois simulés | `simulate_events.py` |

### Données personnelles
- Les visages sont des données biométriques (loi marocaine 09-08, UK GDPR).
- Uniquement des personnes consentantes.
- Stocker de préférence les embeddings plutôt que les photos.
- Ne jamais pousser photos ni embeddings sur Git (`data/` dans `.gitignore`).

---

## 8. Installation et lancement (sans Docker)

### Backend
```bash
cd backend
python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux / macOS :
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # puis remplir les valeurs
alembic upgrade head          # crée les tables
```

### Lancement (deux terminaux)
```bash
# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — worker caméra
python -m app.workers.camera_worker
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

- API : http://localhost:8000 — documentation auto : http://localhost:8000/docs
- Interface : http://localhost:3000

### Exemple de `.env.example`
```
DATABASE_URL=sqlite:///./domicilesecure.db
CAMERA_SOURCE=0
FACE_MATCH_THRESHOLD=0.5
NIGHT_START_HOUR=23
NIGHT_END_HOUR=6
DOOR_OPEN_MAX_SECONDS=600
ANOMALY_ENGINE=rules
SUMMARY_HOUR=21
JWT_SECRET=changer_moi
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
```

---

## 9. Planning (4 sprints de 2 semaines)

| Sprint | Contenu | Livrable |
|---|---|---|
| 1 | Setup FastAPI + base + config, lecture caméra OpenCV, YOLO + tracking, événements en base | Détections visibles dans `/events` |
| 2 | Reconnaissance faciale, enrôlement des membres, invités récurrents, premières pages Next.js | Membres reconnus dans l'interface |
| 3 | Moteur de règles, alertes, Web Push, WebSocket, résumé quotidien | Alertes reçues sur le navigateur |
| 4 | Données synthétiques, entraînement LSTM, comparaison règles vs LSTM, documentation, démo | Rapport final + démo |

### Modèle de compte rendu de sprint (`docs/sprint-N.md`)
```
# Sprint N — du JJ/MM au JJ/MM
## Objectifs prévus
## Réalisé
## Non réalisé / reporté (et pourquoi)
## Difficultés et solutions
## Démo (captures, commandes pour tester)
## Objectifs du sprint suivant
```

---

## 10. Licences à signaler à l'entreprise
- **Ultralytics YOLO** : licence AGPL-3.0 → usage commercial soumis à conditions (ou licence entreprise).
- **Modèles pré-entraînés InsightFace** : usage non commercial.
- Sans problème pour le stage et la démo ; à valider avant tout usage produit.
