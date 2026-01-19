from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.parsers.policy.aetna_policy import parse_policy
from app.parsers.policy.dispatch import PARSERS

client = TestClient(app)

SAMPLE_HTML = """
<html>
<head><title>Aetna CPB 0123</title></head>
<body>
    <h3>Medical Necessity</h3>
    <p>Aetna considers this procedure medically necessary when:</p>
    <ul>
        <li>Criterion 1</li>
        <li>Criterion 2</li>
    </ul>
    <p>Note: Some notes here.</p>
</body>
</html>
"""


@pytest.mark.asyncio
@patch("app.parsers.policy.aetna_policy.fetch_html", new_callable=AsyncMock)
async def test_parse_policy_in_process(mock_fetch):
    mock_fetch.return_value = SAMPLE_HTML

    # Test Aetna parsing
    parsed = await parse_policy(url="http://example.com/aetna", payer_code="aetna")

    assert parsed.payer_code == "aetna"
    assert "Aetna CPB 0123" in parsed.title
    assert "Criterion 1" in parsed.medical_necessity_clean
    assert len(parsed.structured["criteria"]) == 2  # Top level list
    assert parsed.structured["criteria"][0]["text"] == "Criterion 1"

    mock_fetch.assert_called_once_with("http://example.com/aetna")


def test_api_policy_parse_endpoint():
    with patch("app.parsers.policy.policy_parse.fetch_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = SAMPLE_HTML

        response = client.post(
            "/api/policy/parse", json={"url": "http://example.com/aetna", "payer_code": "aetna"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payer_code"] == "aetna"
        assert "Aetna CPB 0123" in data["title"]
        assert "Criterion 1" in data["medical_necessity_clean"]


@pytest.mark.asyncio
async def test_dispatch_resolves_aetna():
    from app.parsers.policy.aetna_cpb import parse_aetna_medical_necessity

    assert PARSERS["aetna"] == parse_aetna_medical_necessity


@pytest.mark.asyncio
async def test_invalid_payer_code():
    with pytest.raises(HTTPException):
        await parse_policy(url="http://example.com", payer_code="invalid")


@patch("app.parsers.policy.aetna_policy.fetch_html", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_parse_iso_date_handling(mock_fetch):
    from app.parsers.policy.aetna_policy import _parse_iso_date

    # Test MM/DD/YYYY to date conversion
    assert _parse_iso_date("10/20/2025") == date(2025, 10, 20)
    assert _parse_iso_date("2025-10-20") == date(2025, 10, 20)
    assert _parse_iso_date("invalid") is None
    assert _parse_iso_date(None) is None
