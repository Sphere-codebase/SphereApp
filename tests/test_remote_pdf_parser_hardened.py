import pytest
import httpx
from unittest.mock import MagicMock, patch
from pathlib import Path
from fastapi import HTTPException
from app.parsers.pdf.remote_client import RemotePdfParserClient

@pytest.fixture
def mock_httpx_client():
    with patch("app.parsers.pdf.remote_client.RemotePdfParserClient.get_client") as mock:
        yield mock

def test_hardened_client_non_json_response(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 502
    mock_response.text = "<html>502 Bad Gateway</html>"
    # In httpx, raise_for_status raises if status >= 400
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "502 Bad Gateway", request=MagicMock(), response=mock_response
    )
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(retries=0)
    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))
    
    assert exc.value.status_code == 504 # It returns 504 because it ran out of retries (which was 0)
    assert "Remote PDF parser timed out after 0 retries" in exc.value.detail

def test_hardened_client_missing_parse_result(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"request_id": "abc"}
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(retries=0)
    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))
    
    assert exc.value.status_code == 502
    assert "invalid response format" in exc.value.detail

def test_hardened_client_auth_failure(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_httpx_client.return_value.post.return_value = mock_response

    client = RemotePdfParserClient(retries=0)
    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))
    
    assert exc.value.status_code == 500
    assert "authentication failed" in exc.value.detail

def test_hardened_client_size_limit():
    client = RemotePdfParserClient(retries=0)
    client.max_size = 10 # 10 bytes
    
    with pytest.raises(HTTPException) as exc:
        client.parse_pdf(Path("tests/test_claim.pdf"))
    
    assert exc.value.status_code == 413
    assert "PDF too large" in exc.value.detail

def test_hardened_client_retry_success(mock_httpx_client):
    # Mock timeout then success
    mock_timeout = MagicMock()
    mock_timeout.post.side_effect = httpx.TimeoutException("Timeout")
    
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {"parse_result": {"user_info": {}}, "request_id": "xyz"}
    
    # We need to control the sequence of responses
    responses = [httpx.TimeoutException("Timeout"), mock_success]
    
    # Actually, the way parse_pdf is written it calls client.post inside a loop
    # So we want mock_httpx_client().post to be the mock with side_effect
    mock_httpx_client.return_value.post.side_effect = responses

    client = RemotePdfParserClient(retries=1)
    # Patch time.sleep to avoid waiting during tests
    with patch("time.sleep"):
        result = client.parse_pdf(Path("tests/test_claim.pdf"))

    assert result["request_id"] == "xyz"
    assert mock_httpx_client.return_value.post.call_count == 2
