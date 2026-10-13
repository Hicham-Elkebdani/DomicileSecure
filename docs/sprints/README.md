# Sprints

Stage de 2 mois : **4 sprints de 2 semaines**. À la fin de chaque sprint, poussez sur le dépôt partagé :
1. le code (branche `main` à jour, CI verte) ;
2. le compte rendu `docs/sprints/sprint-N.md`, à partir de [TEMPLATE.md](TEMPLATE.md).

| Sprint | Objectif | Livrable démontrable | État |
|---|---|---|---|
| 0 — Fondations | Architecture, structure du dépôt, API, BDD, tests, CI, frontend de base | `seed_demo.py` + interface complète sur données de démo | ✅ Socle livré |
| 1 — Vision | Worker sur **vraie caméra** : YOLO + suivi, visages ; enrôlement des membres du foyer | Passer devant la webcam → événement « membre du foyer » en temps réel | À faire |
| 2 — Porte et règles | Jeu de données de la porte, fine-tuning YOLO, réglage des règles et seuils sur données réelles | Alerte « porte restée ouverte » sur la vraie porte | À faire |
| 3 — Notifications et résumé | Web Push en HTTPS, résumé quotidien, retours « fausse alerte » | Notification reçue sur le téléphone | À faire |
| 4 — LSTM | Export des données réelles, réentraînement, évaluation règles / LSTM / hybride, rapport final | Tableau comparatif + démo du mode hybride | À faire |

Conseils :
- Une branche par fonctionnalité (`feat/door-model`), une *pull request* relue, CI verte avant fusion.
- Commits courts et explicites (`feat(worker): debounce door state`).
- Chaque sprint : mettre à jour la documentation concernée.
