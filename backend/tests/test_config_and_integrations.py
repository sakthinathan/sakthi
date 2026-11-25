"""
Unit and integration tests for secure configuration, sponsor services initialization,
and database connection handling.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from app.config import Settings, get_settings
from app.services.google_apis import GoogleMapsService
from app.services.gemini_service import GeminiService, GeminiBYOMService
from app.services.sarvam import SarvamService
from app.services.flagsmith_service import FlagsmithService
from app.services.nudgebee import NudgeBeeConfig
from app.database import check_database_health


def test_configuration_loading():
    """Verify settings loads variables, masks secrets, and parses GCP location"""
    settings = get_settings()

    # Verify basic settings loaded
    assert settings.app_env in ["development", "test", "testing", "production"]
    assert settings.app_port == 8000

    # Verify GCP zone vs region normalization
    if settings.gcp_region_raw:
        # e.g., asia-south1-a should normalize to region asia-south1
        assert not settings.gcp_region.endswith("-a")
        assert not settings.gcp_region.endswith("-b")
        assert not settings.gcp_region.endswith("-c")

    # Verify URL construction and password quote encoding
    if settings.db_password:
        assert "%21" in settings.database_url or "!" in settings.database_url

    # Verify representation masks secrets
    repr_str = repr(settings)
    if settings.db_password:
        assert settings.db_password not in repr_str
    if settings.sarvam_api_key:
        assert settings.sarvam_api_key not in repr_str
    if settings.gemini_api_key:
        assert settings.gemini_api_key not in repr_str


def test_production_missing_variables_validation():
    """Verify validation raises clear configuration error if required production keys are missing"""
    prod_settings = Settings(
        app_env="production",
        DB_HOST=None,
        DATABASE_URL=None,
        GOOGLE_MAPS_AQI_ADDR_API_KEY=None,
        GOOGLE_MAPS_API_KEY=None,
        SARVAM_API_KEY=None,
        FLAGSMITH_ENV_KEY=None,
        FLAGSMITH_ENVIRONMENT_KEY=None,
        GEMINI_API_KEY=None,
    )
    missing = prod_settings.validate_production_readiness()
    assert len(missing) >= 4
    assert any("Cloud SQL" in m for m in missing)
    assert any("SARVAM_API_KEY" in m for m in missing)


def test_google_api_service_initialization():
    """Verify Google Maps / Address / AQI service initializes and uses mocked responses when unconfigured"""
    service = GoogleMapsService(api_key="mock-key-for-unit-test")
    assert service.is_configured is True
    assert service.timeout == 15.0

    unconfigured_service = GoogleMapsService(api_key="")
    assert unconfigured_service.is_configured is False


@pytest.mark.asyncio
async def test_google_address_validation_mock_fallback():
    """Verify fallback returns graceful validated Indian structure when key is empty"""
    service = GoogleMapsService(api_key="")
    result = await service.validate_address("Malleshwaram Bengaluru")
    assert result["is_mock"] is True
    assert result["validation_status"] in ["validated", "partial_match"]
    assert result["latitude"] == 13.0033


def test_gemini_service_initialization():
    """Verify Gemini service initializes with configured model and separate BYOM client"""
    service = GeminiService(api_key="test-key", model="gemini-3.8-flash")
    assert service.is_configured is True
    assert service.model == "gemini-3.8-flash"

    byom = GeminiBYOMService(service)
    assert byom.client == service


@pytest.mark.asyncio
async def test_gemini_byom_fallback_rca():
    """Verify Gemini BYOM handles unconfigured or unreachable state gracefully"""
    service = GeminiService(api_key="")
    byom = GeminiBYOMService(service)
    res = await byom.analyze_incident_rca(
        service_name="utsavops-checkout",
        evidence={"p99": "4800ms"}
    )
    assert "root_cause" in res
    assert res["is_mock"] is True
    assert "utsavops-checkout" in res["root_cause"]


def test_sarvam_service_initialization():
    """Verify Sarvam service sets models and authorization headers without leaking key"""
    service = SarvamService(api_key="sk_test_key_12345")
    assert service.is_configured is True
    headers = service._get_headers()
    assert headers["API-Subscription-Key"] == "sk_test_key_12345"
    assert service.MODEL_SAARAS_V4 == "saaras:v4"
    assert service.MODEL_MAYURA_V1 == "mayura:v1"
    assert service.MODEL_BULBUL_V3 == "bulbul:v3"


def test_flagsmith_service_initialization():
    """Verify Flagsmith service initialization and VIP surge rules"""
    flagsmith = FlagsmithService()
    # Check VIP express logic
    # During surge mode, VIP gets express, non-VIP does not
    flagsmith.local_overrides["surge_survival_mode"] = True
    assert flagsmith.should_allow_express(customer_id="cust-1", is_vip=True) is True
    assert flagsmith.should_allow_express(customer_id="cust-2", is_vip=False) is False

    # During normal mode, both get express if base enabled
    flagsmith.local_overrides["surge_survival_mode"] = False
    assert flagsmith.should_allow_express(customer_id="cust-2", is_vip=False) is True


def test_nudgebee_configuration_validation():
    """Verify NudgeBee configuration metadata extraction"""
    meta = NudgeBeeConfig.get_metadata()
    assert "vm_name" in meta
    assert "secret_name" in meta
    assert "monitored_services" in meta
    assert "utsavops-checkout" in meta["monitored_services"]
    assert "newsletter-worker" in meta["monitored_services"]


@pytest.mark.asyncio
async def test_database_health_probe():
    """Verify database health probe returns structured status without exposing password"""
    health = await check_database_health()
    assert "status" in health
    assert "type" in health
    assert health["status"] in ["connected", "disconnected"]
    # Check that password is never in error or host
    settings = get_settings()
    if settings.db_password:
        assert settings.db_password not in str(health)
