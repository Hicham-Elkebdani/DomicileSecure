# Déploiement (sans Docker)

Cible de référence : **un serveur Linux** (Ubuntu 24.04 LTS ou Debian 12) avec :
- **systemd**, pour lancer et relancer automatiquement les services ;
- **Nginx**, pour le HTTPS, le reverse proxy et le WebSocket ;
- **PostgreSQL**.

Tous les fichiers de configuration sont dans [`infra/`](../infra).

```
              Internet / réseau local
                       │ HTTPS 443
                 ┌─────▼─────┐
                 │   Nginx   │  TLS (Let's Encrypt), en-têtes, WebSocket
                 └──┬─────┬──┘
        /api/*, /api/v1/ws │ /
       ┌───────────▼┐   ┌──▼─────────────┐
       │ API :8000  │   │ Next.js :3000  │   systemd : domicilesecure-api / -web
       └──┬──────▲──┘   └────────────────┘
          │      │ HTTP + clé API (réseau local)
   ┌──────▼──┐ ┌─┴───────────────────────────┐
   │PostgreSQL│ │ worker@entree  worker@jardin │ systemd : domicilesecure-worker@<caméra>
   └──────────┘ └──────────────────────────────┘
```

## 1. Préparer le serveur

```bash
sudo apt update && sudo apt install -y python3.12-venv python3-dev nginx postgresql \
     certbot python3-certbot-nginx libgl1 git
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs

sudo useradd --system --create-home --home-dir /opt/domicilesecure --shell /usr/sbin/nologin domicile
sudo -u domicile git clone <URL_DU_DEPOT> /opt/domicilesecure/app
```

`libgl1` est requis par `opencv-python` sur un serveur sans interface graphique.

## 2. Base de données

```bash
sudo -u postgres psql <<'SQL'
CREATE USER domicile WITH PASSWORD 'MOT_DE_PASSE_FORT';
CREATE DATABASE domicilesecure OWNER domicile;
SQL
```

## 3. Backend

```bash
cd /opt/domicilesecure/app/backend
sudo -u domicile python3 -m venv .venv
sudo -u domicile .venv/bin/pip install -r requirements/api.txt -r requirements/vision.txt -r requirements/ml.txt
sudo -u domicile cp .env.example .env && sudo chmod 600 .env
sudo -u domicile .venv/bin/python scripts/generate_secrets.py     # coller les valeurs dans .env
```

À modifier dans `.env` :

```ini
ENVIRONMENT=production
LOG_JSON=true
DATABASE_URL=postgresql+asyncpg://domicile:MOT_DE_PASSE_FORT@localhost:5432/domicilesecure
CORS_ORIGINS=["https://securite.exemple.com"]
ANOMALY_ENGINE=hybrid          # une fois le LSTM entraîné et promu
```

```bash
sudo -u domicile .venv/bin/python scripts/download_models.py
sudo -u domicile .venv/bin/alembic upgrade head
sudo -u domicile .venv/bin/python -m app.cli create-admin --email vous@exemple.com
sudo -u domicile .venv/bin/python -m app.cli create-camera --name entree --has-door
```

## 4. Frontend

```bash
cd /opt/domicilesecure/app/frontend
echo "NEXT_PUBLIC_API_URL=https://securite.exemple.com/api/v1" | sudo -u domicile tee .env.production.local
sudo -u domicile npm ci && sudo -u domicile npm run build
# output: "standalone" → serveur autonome, copier les fichiers statiques à côté
sudo -u domicile cp -r public .next/standalone/ && sudo -u domicile cp -r .next/static .next/standalone/.next/
```

## 5. Services systemd

```bash
sudo cp /opt/domicilesecure/app/infra/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now domicilesecure-api domicilesecure-web
```

**Un worker par caméra** grâce au service *template* `domicilesecure-worker@.service` : l'instance (`@entree`) sélectionne le fichier `/opt/domicilesecure/app/backend/workers/entree.env`.

```bash
sudo -u domicile mkdir -p /opt/domicilesecure/app/backend/workers
sudo -u domicile tee /opt/domicilesecure/app/backend/workers/entree.env <<'ENV'
WORKER_CAMERA_ID=<id affiché par create-camera>
WORKER_CAMERA_SOURCE=rtsp://user:motdepasse@192.168.1.20:554/stream1
ENV
sudo chmod 600 /opt/domicilesecure/app/backend/workers/*.env
sudo systemctl enable --now domicilesecure-worker@entree
journalctl -u domicilesecure-worker@entree -f
```

## 6. Nginx et HTTPS

```bash
sudo cp /opt/domicilesecure/app/infra/nginx/domicilesecure.conf /etc/nginx/sites-available/
sudo sed -i 's/securite.exemple.com/VOTRE_DOMAINE/g' /etc/nginx/sites-available/domicilesecure.conf
sudo ln -s /etc/nginx/sites-available/domicilesecure.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d VOTRE_DOMAINE
```

Web Push et service worker exigent HTTPS, sauf sur `localhost`.

## 7. Mise à jour (déploiement continu manuel)

```bash
cd /opt/domicilesecure/app && sudo -u domicile git pull
cd backend && sudo -u domicile .venv/bin/pip install -r requirements/api.txt -r requirements/vision.txt -r requirements/ml.txt
sudo -u domicile .venv/bin/alembic upgrade head
cd ../frontend && sudo -u domicile npm ci && sudo -u domicile npm run build \
  && sudo -u domicile cp -r public .next/standalone/ && sudo -u domicile cp -r .next/static .next/standalone/.next/
sudo systemctl restart domicilesecure-api domicilesecure-web 'domicilesecure-worker@*'
```

## 8. Exploitation

| Besoin | Commande |
|---|---|
| Santé | `curl https://VOTRE_DOMAINE/api/v1/health/ready` |
| Logs API (JSON) | `journalctl -u domicilesecure-api -f` |
| Logs d'une caméra | `journalctl -u domicilesecure-worker@entree -f` |
| Sauvegarde | `infra/scripts/backup_postgres.sh` (cron quotidien, rotation 14 jours) |
| Nouveau modèle LSTM | `python -m training.train_lstm ... --promote` puis `systemctl restart domicilesecure-api` |
| Rollback du modèle | copier `artifacts/anomaly_lstm/<ancienne_version>` sur `latest/`, puis redémarrer l'API |

## Windows (poste de démonstration)

Pour une démo sur un PC Windows, le démarrage rapide du [README](../README.md) suffit (3 terminaux : API, worker, frontend). Pour un fonctionnement permanent, [NSSM](https://nssm.cc/) transforme chaque commande en service Windows :

```powershell
nssm install DomicileSecureAPI "C:\...\backend\.venv\Scripts\uvicorn.exe" "app.main:create_app --factory --host 127.0.0.1 --port 8000"
nssm set DomicileSecureAPI AppDirectory "C:\...\backend"
```
