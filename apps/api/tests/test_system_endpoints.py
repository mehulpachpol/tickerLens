from fastapi.testclient import TestClient

from tickerlens_api.main import create_app


def test_health() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_version() -> None:
    client = TestClient(create_app())
    resp = client.get("/version")
    assert resp.status_code == 200
    assert resp.json()["name"] == "TickerLens API"

