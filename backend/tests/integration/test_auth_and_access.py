from __future__ import annotations

import httpx

from tests.conftest import ADMIN_EMAIL


async def test_health_endpoints(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    ready = (await client.get("/health/ready")).json()
    assert ready == {"status": "ready", "anomaly_engine": "rules", "push": "disabled"}


async def test_login_and_me(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.get("/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL
    assert response.json()["is_admin"] is True


async def test_wrong_password_returns_uniform_error(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    wrong = await client.post("/auth/login", data={"username": ADMIN_EMAIL, "password": "nope"})
    missing = await client.post("/auth/login", data={"username": "x@y.io", "password": "nope"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong.json()["error"]["code"] == "not_authenticated"


async def test_login_is_rate_limited(client: httpx.AsyncClient) -> None:
    statuses = [
        (await client.post("/auth/login", data={"username": "a@b.io", "password": "x"})).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


async def test_protected_routes_require_a_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/cameras")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_invalid_token_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.get("/cameras", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


async def test_non_admin_cannot_manage_cameras_or_users(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    assert (await client.get("/cameras", headers=user_headers)).status_code == 200
    create = await client.post("/cameras", json={"name": "X"}, headers=user_headers)
    assert create.status_code == 403
    assert (await client.get("/users", headers=user_headers)).status_code == 403


async def test_admin_creates_user(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    payload = {"email": "sara@example.com", "password": "Sara-Password-1", "full_name": "Sara"}
    created = await client.post("/users", json=payload, headers=admin_headers)
    assert created.status_code == 201
    duplicate = await client.post("/users", json=payload, headers=admin_headers)
    assert duplicate.status_code == 409


async def test_security_headers_and_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_validation_errors_have_a_consistent_shape(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.post("/cameras", json={"name": ""}, headers=admin_headers)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]["errors"][0]["loc"] == ["body", "name"]
