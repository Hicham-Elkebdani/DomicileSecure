# One-shot development setup for Windows (PowerShell), from the repository root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== Backend ==" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements/dev.txt -r requirements/vision.txt -r requirements/ml.txt
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created backend\.env - generate secrets with: python scripts/generate_secrets.py" -ForegroundColor Yellow
}
& .\.venv\Scripts\python.exe scripts/download_models.py
& .\.venv\Scripts\alembic.exe upgrade head

Write-Host "== Frontend ==" -ForegroundColor Cyan
Set-Location "$root\frontend"
if (-not (Test-Path ".env.local")) { Copy-Item .env.example .env.local }
npm install

Set-Location $root
Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
Write-Host "  cd backend; .\.venv\Scripts\Activate.ps1; python scripts/seed_demo.py"
Write-Host "  uvicorn app.main:create_app --factory --reload"
Write-Host "  (new terminal) cd frontend; npm run dev"
