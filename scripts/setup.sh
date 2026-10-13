#!/usr/bin/env bash
# One-shot development setup for Linux/macOS, from the repository root:  ./scripts/setup.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Backend =="
cd "$root/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements/dev.txt -r requirements/vision.txt -r requirements/ml.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env - generate secrets with: python scripts/generate_secrets.py"
fi
.venv/bin/python scripts/download_models.py
.venv/bin/alembic upgrade head

echo "== Frontend =="
cd "$root/frontend"
[ -f .env.local ] || cp .env.example .env.local
npm install

echo
echo "Done. Next steps:"
echo "  cd backend && source .venv/bin/activate && python scripts/seed_demo.py"
echo "  uvicorn app.main:create_app --factory --reload"
echo "  (new terminal) cd frontend && npm run dev"
