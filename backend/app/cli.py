"""Administration commands.

python -m app.cli create-admin --email admin@example.com
python -m app.cli create-camera --name "Entrée" --location "Porte d'entrée" --has-door
python -m app.cli list-cameras
python -m app.cli generate-summary --day 2026-10-01
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from datetime import date

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import Database
from app.schemas.camera import CameraCreate
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.camera_service import CameraService
from app.services.summary_service import SummaryService


async def _create_admin(args: argparse.Namespace, db: Database) -> None:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass(
        "Mot de passe (10+ caractères) : "
    )
    data = UserCreate(email=args.email, password=password, full_name=args.name, is_admin=True)
    async with db.session() as session:
        user = await AuthService(session, get_settings()).create_user(data)
    print(f"Administrateur créé : {user.email}")


async def _create_camera(args: argparse.Namespace, db: Database) -> None:
    data = CameraCreate(name=args.name, location=args.location, has_door=args.has_door)
    async with db.session() as session:
        camera = await CameraService(session).create(data)
    print(f"Caméra créée. Ajoutez dans le .env du worker :\nWORKER_CAMERA_ID={camera.id}")


async def _list_cameras(_: argparse.Namespace, db: Database) -> None:
    async with db.session() as session:
        for camera in await CameraService(session).list():
            print(
                f"{camera.id}  {camera.name:<20} porte={camera.has_door}  active={camera.is_active}"
            )


async def _generate_summary(args: argparse.Namespace, db: Database) -> None:
    async with db.session() as session:
        summary = await SummaryService(session, get_settings()).generate(
            date.fromisoformat(args.day)
        )
    print(summary.text)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Créer un compte administrateur")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="")
    admin.set_defaults(handler=_create_admin)

    camera = sub.add_parser("create-camera", help="Déclarer une caméra")
    camera.add_argument("--name", required=True)
    camera.add_argument("--location", default="")
    camera.add_argument("--has-door", action="store_true")
    camera.set_defaults(handler=_create_camera)

    sub.add_parser("list-cameras", help="Lister les caméras").set_defaults(handler=_list_cameras)

    summary = sub.add_parser("generate-summary", help="Générer le résumé d'une journée")
    summary.add_argument("--day", default=date.today().isoformat())
    summary.set_defaults(handler=_generate_summary)

    args = parser.parse_args()
    settings = get_settings()

    async def run() -> None:
        db = Database(settings.database_url)
        try:
            await args.handler(args, db)
        finally:
            await db.dispose()

    try:
        asyncio.run(run())
    except (AppError, ValueError) as exc:
        print(f"Erreur : {getattr(exc, 'message', exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
