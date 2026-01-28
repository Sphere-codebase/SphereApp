from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.parsers.pdf.remote_client import RemotePdfParserClient


@pytest.fixture
def mock_httpx_client():
    with patch("httpx.Client") as mock:
        yield mock


def test_remote_parser_client_success(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "parse_result": {"user_info": {"name": "Test User"}, "codes": [], "info": []},
        "request_id": "test-uuid",
    }
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(base_url="http://mock-parser", api_key="test-key")
    result = client.parse_pdf(Path("tests/test_claim.pdf"))

    assert result["pdf"]["user_info"]["name"] == "Test User"
    assert result["request_id"] == "test-uuid"
    assert result["error_message"] is None


def test_remote_parser_client_validation_error(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {"detail": "Invalid PDF format"}
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(base_url="http://mock-parser", api_key="test-key")

    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))

    assert exc.value.status_code == 422
    assert "Remote parser validation error" in exc.value.detail


def test_remote_parser_client_server_error(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = Exception("Internal Server Error")
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(base_url="http://mock-parser", api_key="test-key")

    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))

    assert exc.value.status_code == 500
