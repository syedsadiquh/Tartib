"""F-02 smoke test: the app factory exposes the health route.

Real router tests arrive with BE-01.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from scheduler.api.app import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_is_served_under_api() -> None:
    client = TestClient(create_app())

    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
