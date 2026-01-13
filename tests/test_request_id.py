import uuid

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app


class EchoPayload(BaseModel):
    message: str


@app.post("/__test__/ok")
def echo_ok(payload: EchoPayload) -> dict[str, str]:
    return {"message": payload.message}


@app.get("/__test__/boom")
def boom() -> None:
    raise RuntimeError("boom")


client = TestClient(app, raise_server_exceptions=False)


def test_request_id_echoed_from_client() -> None:
    request_id = "req-abc-123"
    response = client.post(
        "/__test__/ok",
        headers={"X-Request-ID": request_id},
        json={"message": "hi"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id


def test_request_id_generated_when_missing() -> None:
    response = client.post("/__test__/ok", json={"message": "hi"})

    assert response.status_code == 200
    response_request_id = response.headers.get("X-Request-ID")
    assert response_request_id is not None
    parsed = uuid.UUID(response_request_id)
    assert parsed.version == 4


def test_request_id_present_on_validation_error() -> None:
    response = client.post("/__test__/ok", json={})

    assert response.status_code == 422
    assert response.headers.get("X-Request-ID") is not None
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "Validation error"
    assert isinstance(payload["error"]["details"], list)


def test_error_format_for_unhandled_exception() -> None:
    response = client.get("/__test__/boom")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert payload["error"]["message"] == "Internal server error"
    assert isinstance(payload["error"]["details"], dict)
