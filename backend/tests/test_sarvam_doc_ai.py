"""
Unit & Integration Tests for Sarvam Document AI SDK Async-Job Workflow
Verifies:
- SDK initialization
- doc_ai.extract submission
- doc_ai.get_status polling (completed, partially_completed, failed, rejected, timeout)
- doc_ai.get_results parsing & normalization
- Missing API key fallback
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.sarvam import SarvamService, MOCK_FESTIVE_ORDER, DOC_AI_ORDER_SCHEMA


@pytest.mark.asyncio
async def test_sarvam_unconfigured_fallback():
    """Verify missing API key returns clearly labelled not_configured fallback"""
    service = SarvamService(api_key="")
    result = await service.extract_from_image(b"dummy image bytes", "chit.png")

    assert result["success"] is True
    assert result["is_mock"] is True
    assert result["provider"] == "sarvam_document_ai"
    assert result["status"] == "not_configured"
    assert result["data"]["customer_name"] == MOCK_FESTIVE_ORDER["customer_name"]
    assert len(result["data"]["items"]) == len(MOCK_FESTIVE_ORDER["items"])


@pytest.mark.asyncio
async def test_sarvam_doc_ai_successful_job_workflow():
    """Verify full async-job lifecycle: submit -> poll completed -> retrieve results"""
    service = SarvamService(api_key="sk_test_mock_sarvam_key", doc_ai_poll_interval=0.01, doc_ai_max_timeout=1.0)

    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "job-diwali-101"
    mock_client.doc_ai.extract.return_value = mock_job

    mock_status = MagicMock()
    mock_status.status = "completed"
    mock_client.doc_ai.get_status.return_value = mock_status

    mock_results = MagicMock()
    mock_results.result = {
        "customer_name": "Smt. Shreya Sen",
        "delivery_address": "Indiranagar, Bengaluru",
        "items": [
            {"name": "Kaju Katli Box", "quantity": 3},
            {"name": "Gulab Jamun Tin", "quantity": 2}
        ]
    }
    mock_client.doc_ai.get_results.return_value = mock_results

    service._sdk_client = mock_client

    result = await service.extract_from_image(b"fake-bytes", "order.jpg")

    assert result["success"] is True
    assert result["is_mock"] is False
    assert result["provider"] == "sarvam_document_ai"
    assert result["status"] == "live"
    assert result["job_id"] == "job-diwali-101"

    data = result["data"]
    assert data["customer_name"] == "Smt. Shreya Sen"
    assert data["delivery_address"] == "Indiranagar, Bengaluru"
    assert len(data["items"]) == 2
    assert data["items"][0]["product_name"] == "Kaju Katli Box"
    assert data["items"][0]["quantity"] == 3
    assert data["items"][1]["product_name"] == "Gulab Jamun Tin"
    assert data["items"][1]["quantity"] == 2

    # Verify extract was called with required format
    mock_client.doc_ai.extract.assert_called_once()
    call_kwargs = mock_client.doc_ai.extract.call_args[1]
    assert call_kwargs["output_format"] == "json"
    assert json.loads(call_kwargs["schema"]) == DOC_AI_ORDER_SCHEMA


@pytest.mark.asyncio
async def test_sarvam_doc_ai_failed_job():
    """Verify failed job status returns error status and labelled fallback"""
    service = SarvamService(api_key="sk_test_key", doc_ai_poll_interval=0.01, doc_ai_max_timeout=1.0)

    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "job-fail-999"
    mock_client.doc_ai.extract.return_value = mock_job

    mock_status = MagicMock()
    mock_status.status = "failed"
    mock_client.doc_ai.get_status.return_value = mock_status

    service._sdk_client = mock_client

    result = await service.extract_from_image(b"bad-bytes", "damaged_chit.png")

    assert result["success"] is False
    assert result["is_mock"] is True
    assert result["status"] == "error"
    assert "failed" in result["failure_reason"].lower()
    assert result["job_id"] == "job-fail-999"
    assert result["data"]["customer_name"] == MOCK_FESTIVE_ORDER["customer_name"]


@pytest.mark.asyncio
async def test_sarvam_doc_ai_timeout_handling():
    """Verify job that stays processing past timeout is terminated safely"""
    service = SarvamService(api_key="sk_test_key", doc_ai_poll_interval=0.01, doc_ai_max_timeout=0.05)

    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "job-timeout-404"
    mock_client.doc_ai.extract.return_value = mock_job

    mock_status = MagicMock()
    mock_status.status = "processing"
    mock_client.doc_ai.get_status.return_value = mock_status

    service._sdk_client = mock_client

    result = await service.extract_from_image(b"bytes", "slow_chit.png")

    assert result["success"] is False
    assert result["is_mock"] is True
    assert result["status"] == "error"
    assert "timed out" in result["failure_reason"].lower()
    assert result["job_id"] == "job-timeout-404"
