from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories.user import UserRepository
from app.schemas.user import Token, UserCreate

logger = logging.getLogger(__name__)

# Verifying against a dummy hash when the user does not exist keeps response times equal,
# so attackers cannot discover which e-mails have an account.
_DUMMY_HASH = hash_password("timing-attack-protection")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._settings = settings

    async def authenticate(self, email: str, password: str) -> Token:
        user = await self._users.get_by_email(email)
        valid = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
        if user is None or not valid or not user.is_active:
            logger.warning("Failed login attempt", extra={"email": email})
            raise AuthenticationError("E-mail ou mot de passe incorrect")
        return self.issue_token(user)

    def issue_token(self, user: User) -> Token:
        expires = self._settings.access_token_expire_minutes
        token = create_access_token(
            str(user.id),
            secret=self._settings.jwt_secret_key.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
            expires_minutes=expires,
            extra_claims={"adm": user.is_admin},
        )
        return Token(access_token=token, expires_in=expires * 60)

    async def create_user(self, data: UserCreate) -> User:
        if await self._users.get_by_email(data.email):
            raise ConflictError("Un compte existe déjà avec cet e-mail")
        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            is_admin=data.is_admin,
            is_active=True,
        )
        self._users.add(user)
        await self._session.commit()
        return user

    async def list_users(self) -> list[User]:
        return list(await self._users.list_all())
