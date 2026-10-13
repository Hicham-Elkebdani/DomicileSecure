from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import (
    api_keys_match,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.face_gallery import FaceGallery
from vision.face.similarity import l2_normalize

SECRET = "x" * 40


def test_password_hashing() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip() -> None:
    token = create_access_token("user-1", secret=SECRET, algorithm="HS256", expires_minutes=5)
    assert decode_access_token(token, secret=SECRET, algorithm="HS256")["sub"] == "user-1"


def test_expired_token_is_rejected() -> None:
    token = create_access_token("user-1", secret=SECRET, algorithm="HS256", expires_minutes=-1)
    with pytest.raises(AuthenticationError, match="expirée"):
        decode_access_token(token, secret=SECRET, algorithm="HS256")


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = create_access_token("user-1", secret="y" * 40, algorithm="HS256", expires_minutes=5)
    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret=SECRET, algorithm="HS256")


def test_api_key_comparison() -> None:
    assert api_keys_match("abc", "abc")
    assert not api_keys_match("abd", "abc")
    assert not api_keys_match(None, "abc")
    assert not api_keys_match("", "")


async def test_rate_limiter() -> None:
    limiter = SlidingWindowRateLimiter(max_hits=2, window_seconds=60)
    assert await limiter.hit("ip")
    assert await limiter.hit("ip")
    assert not await limiter.hit("ip")
    assert await limiter.hit("other-ip")
    await limiter.reset("ip")
    assert await limiter.hit("ip")


def test_production_refuses_insecure_defaults() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None, environment="production")


def test_production_accepts_strong_secrets() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="s" * 48,
        worker_api_key="w" * 32,
    )
    assert settings.environment == "production"


def test_gallery_matches_above_threshold_only() -> None:
    gallery = FaceGallery(threshold=0.5)
    alice, bob = uuid.uuid4(), uuid.uuid4()
    rng = np.random.default_rng(1)
    alice_vec, bob_vec = l2_normalize(rng.normal(size=128)), l2_normalize(rng.normal(size=128))
    gallery.add(alice, alice_vec, "m")
    gallery.add(bob, bob_vec, "m")

    noisy_alice = l2_normalize(alice_vec + rng.normal(scale=0.02, size=128))
    match = gallery.match(noisy_alice, "m")
    assert match is not None and match.person_id == alice and match.score > 0.9
    assert gallery.match(l2_normalize(rng.normal(size=128)), "m") is None
    assert gallery.match(noisy_alice, "another-model") is None
