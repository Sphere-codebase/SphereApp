from fastapi.testclient import TestClient

from app.llm.client import LLMUnavailable
from app.main import app


@app.get("/__test__/llm-unavailable")
def llm_unavailable() -> None:
    raise LLMUnavailable("unreachable")


def test_llm_unavailable_maps_to_503() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__test__/llm-unavailable")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "LLM_UNAVAILABLE"
    assert payload["error"]["message"] == "LLM service is unavailable"
