from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_root_returns_api_status() -> None:
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "SphereApp API"
    assert payload["status"] == "ok"


def test_ui_routes_removed() -> None:
    response = client.get("/login")
    assert response.status_code == 404

    response = client.get("/app/chat")
    assert response.status_code == 404

    response = client.get("/app/admin/users")
    assert response.status_code == 404


def test_static_assets_removed() -> None:
    response = client.get("/static/app.css")
    assert response.status_code == 404
