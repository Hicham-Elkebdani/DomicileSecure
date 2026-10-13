from __future__ import annotations

import httpx

from tests.conftest import solid_image


async def test_camera_crud(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    created = await client.post(
        "/cameras", json={"name": "Jardin", "location": "Arrière"}, headers=admin_headers
    )
    assert created.status_code == 201
    camera = created.json()
    assert camera["door_state"] == "unknown"

    duplicate = await client.post("/cameras", json={"name": "Jardin"}, headers=admin_headers)
    assert duplicate.status_code == 409

    updated = await client.patch(
        f"/cameras/{camera['id']}", json={"location": "Terrasse"}, headers=admin_headers
    )
    assert updated.json()["location"] == "Terrasse"

    assert (
        await client.delete(f"/cameras/{camera['id']}", headers=admin_headers)
    ).status_code == 204
    assert (await client.get(f"/cameras/{camera['id']}", headers=admin_headers)).status_code == 404


async def _create_person(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post(
        "/persons", json={"display_name": name, "role": "resident"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_face_enrollment(client: httpx.AsyncClient, user_headers: dict[str, str]) -> None:
    person = await _create_person(client, user_headers, "Hicham")
    files = {"photo": ("face.png", solid_image((10, 200, 30)), "image/png")}
    enrolled = await client.post(
        f"/persons/{person['id']}/faces", files=files, headers=user_headers
    )
    assert enrolled.status_code == 201, enrolled.text
    assert enrolled.json()["face_count"] == 1

    listed = (await client.get("/persons", headers=user_headers)).json()
    assert listed[0]["face_count"] == 1


async def test_face_enrollment_rejects_bad_photos(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    person = await _create_person(client, user_headers, "Sara")
    url = f"/persons/{person['id']}/faces"

    async def upload(content: bytes, content_type: str = "image/png") -> httpx.Response:
        files = {"photo": ("p.png", content, content_type)}
        return await client.post(url, files=files, headers=user_headers)

    no_face = await upload(solid_image((0, 0, 0)))
    assert no_face.status_code == 422
    assert "Aucun visage" in no_face.json()["error"]["message"]

    two_faces = await upload(solid_image((10, 10, 200), split=(200, 10, 10)))
    assert two_faces.status_code == 422
    assert "Plusieurs visages" in two_faces.json()["error"]["message"]

    corrupted = await upload(b"definitely not an image")
    assert corrupted.status_code == 422

    wrong_type = await upload(b"%PDF-1.4", "application/pdf")
    assert wrong_type.status_code == 422


async def test_visitors_cannot_be_created_by_hand(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/persons", json={"display_name": "X", "role": "visitor"}, headers=user_headers
    )
    assert response.status_code == 422


async def test_person_deletion_removes_faces(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    person = await _create_person(client, user_headers, "Temp")
    files = {"photo": ("face.png", solid_image((50, 50, 250)), "image/png")}
    await client.post(f"/persons/{person['id']}/faces", files=files, headers=user_headers)
    assert (
        await client.delete(f"/persons/{person['id']}", headers=user_headers)
    ).status_code == 204
    assert (await client.get(f"/persons/{person['id']}", headers=user_headers)).status_code == 404
