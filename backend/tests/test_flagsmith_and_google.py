"""
Unit & Integration Tests for Flagsmith Live VIP Evaluation, Management API PATCH,
and Google Cloud APIs Dual-Key & Metadata Transparency.
"""
import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from app.config import Settings
from app.services.flagsmith_service import FlagsmithService
from app.services.google_apis import GoogleMapsService, AQI_DISCLAIMER


# --- GOOGLE MAPS & AIR QUALITY TESTS ---

def test_google_maps_dual_key_precedence():
    """Verify GOOGLE_MAPS_AQI_ADDR_API_KEY takes canonical precedence over GOOGLE_MAPS_API_KEY"""
    # 1. Primary key provided
    s1 = Settings(GOOGLE_MAPS_AQI_ADDR_API_KEY="primary_key", GOOGLE_MAPS_API_KEY="secondary_key")
    assert s1.google_maps_api_key == "primary_key"

    # 2. Only legacy key provided
    s2 = Settings(GOOGLE_MAPS_AQI_ADDR_API_KEY=None, GOOGLE_MAPS_API_KEY="secondary_key")
    assert s2.google_maps_api_key == "secondary_key"

    # 3. Neither provided
    s3 = Settings(GOOGLE_MAPS_AQI_ADDR_API_KEY=None, GOOGLE_MAPS_API_KEY=None)
    assert s3.google_maps_api_key is None


@pytest.mark.asyncio
async def test_google_apis_live_metadata():
    """Verify live responses return provider metadata with is_mock=False and status=live"""
    service = GoogleMapsService(api_key="valid-test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "verdict": {"hasUnconfirmedComponents": False},
            "address": {"formattedAddress": "100 Feet Rd, Indiranagar, Bengaluru"},
            "geocode": {"location": {"latitude": 12.9783, "longitude": 77.6408}}
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await service.validate_address("100 Feet Rd Indiranagar")

        assert res["is_mock"] is False
        assert res["provider"] == "google_address_validation"
        assert res["status"] == "live"
        assert res["latitude"] == 12.9783
        assert res["longitude"] == 77.6408


@pytest.mark.asyncio
async def test_google_air_quality_disclaimer_preserved():
    """Verify AQI contextual delivery planning disclaimer is strictly returned in live and fallback"""
    service = GoogleMapsService(api_key="")
    res = await service.get_air_quality(12.9716, 77.5946)

    assert res["is_mock"] is True
    assert res["provider"] == "google_air_quality"
    assert res["status"] == "not_configured"
    assert res["disclaimer"] == AQI_DISCLAIMER


# --- FLAGSMITH VIP EVALUATION TESTS ---

def test_flagsmith_vip_express_delivery_during_surge():
    """
    CRITICAL BUSINESS RULE:
    During surge mode:
    - VIP customers retain express delivery
    - Non-VIP customers have express delivery shed/disabled
    """
    fs = FlagsmithService()
    fs.local_overrides.clear()

    # Case 1: Normal mode (Surge = False)
    fs.toggle_surge_mode(False)
    eval_vip_normal = fs.evaluate_vip_express_delivery(customer_id="cust-vip-1", is_vip=True)
    eval_std_normal = fs.evaluate_vip_express_delivery(customer_id="cust-std-1", is_vip=False)

    assert eval_vip_normal["allowed"] is True
    assert eval_vip_normal["traits"]["tier"] == "VIP"
    assert eval_std_normal["allowed"] is True
    assert eval_std_normal["traits"]["tier"] == "STANDARD"

    # Case 2: Surge Mode Active (Surge = True)
    fs.toggle_surge_mode(True)
    eval_vip_surge = fs.evaluate_vip_express_delivery(customer_id="cust-vip-2", is_vip=True)
    eval_std_surge = fs.evaluate_vip_express_delivery(customer_id="cust-std-2", is_vip=False)

    assert eval_vip_surge["allowed"] is True
    assert eval_vip_surge["decision_rule"] == "surge_vip_priority"
    assert eval_vip_surge["segment"] == "vip_festive_buyers"

    assert eval_std_surge["allowed"] is False
    assert eval_std_surge["decision_rule"] == "surge_non_vip_load_shed"
    assert eval_std_surge["segment"] == "standard_buyers"

    # Verify should_allow_express helper matches
    assert fs.should_allow_express("cust-vip-2", is_vip=True) is True
    assert fs.should_allow_express("cust-std-2", is_vip=False) is False


# --- FLAGSMITH MANAGEMENT API PATCH TESTS ---

@pytest.mark.asyncio
async def test_flagsmith_management_api_patch_success():
    """Verify Management API successfully PATCHes feature state and verifies remote update"""
    fs = FlagsmithService()

    mock_get_feature = MagicMock()
    mock_get_feature.status_code = 200
    mock_get_feature.json.return_value = {
        "results": [{"id": 14205, "enabled": False}]
    }

    mock_patch = MagicMock()
    mock_patch.status_code = 200
    mock_patch.json.return_value = {"id": 14205, "enabled": True}

    mock_confirm = MagicMock()
    mock_confirm.status_code = 200
    mock_confirm.json.return_value = {"id": 14205, "enabled": True}

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="admin_secret_token_123")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.test_env_key")), \
         patch("httpx.AsyncClient.get", side_effect=[mock_get_feature, mock_confirm]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch):

        result = await fs.update_feature_state_remote(enabled=True, feature_id="299380")

        assert result["success"] is True
        assert result["enabled"] is True
        assert result["source"] == "flagsmith_remote_admin"
        assert result["feature_id"] == "299380"
        assert result["feature_state_id"] == 14205


@pytest.mark.asyncio
async def test_flagsmith_management_api_unauthorized_401():
    """Verify 401 Unauthorized returns visible failure without falsely reporting success"""
    fs = FlagsmithService()

    mock_get = MagicMock()
    mock_get.status_code = 401

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="invalid_admin_key")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.test_env_key")), \
         patch("httpx.AsyncClient.get", return_value=mock_get):

        result = await fs.update_feature_state_remote(enabled=True, feature_id="299380")

        assert result["success"] is False
        assert result["source"] == "remote_failed"
        assert result["status_code"] == 401
        assert "401" in result["error"]


@pytest.mark.asyncio
async def test_flagsmith_management_api_missing_key_fallback():
    """Verify absent admin key triggers local override and explicitly reports local source"""
    fs = FlagsmithService()

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=None)):
        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert result["success"] is True
        assert result["source"] == "local_override"
        assert result["status"] == "LOCAL_OVERRIDE"
        assert "local in-memory override" in result["message"]


@pytest.mark.asyncio
async def test_flagsmith_base_express_disabled_blocks_all():
    """When base express delivery is globally disabled, both VIP and non-VIP are blocked."""
    fs = FlagsmithService()
    fs.local_overrides["express_delivery_enabled"] = False
    fs.toggle_surge_mode(False)

    eval_vip = fs.evaluate_vip_express_delivery(customer_id="vip-blocked", is_vip=True)
    eval_std = fs.evaluate_vip_express_delivery(customer_id="std-blocked", is_vip=False)

    assert eval_vip["allowed"] is False
    assert eval_std["allowed"] is False
    fs.local_overrides.clear()


@pytest.mark.asyncio
async def test_flagsmith_management_api_read_after_write_mismatch():
    """Verify read-after-write mismatch returns failure and does not claim remote update."""
    fs = FlagsmithService()

    mock_get = MagicMock(status_code=200)
    mock_get.json.return_value = {"results": [{"id": 14205, "enabled": False}]}

    mock_patch = MagicMock(status_code=200)

    # Read-after-write returns state that DOES NOT match what was requested
    mock_confirm = MagicMock(status_code=200)
    mock_confirm.json.return_value = {"id": 14205, "enabled": False}

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="valid_admin_token")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.test_env_key")), \
         patch("httpx.AsyncClient.get", side_effect=[mock_get, mock_confirm]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch):

        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert result["success"] is False
        assert result["source"] == "remote_mismatch"
        assert "mismatch" in result["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_management_api_missing_feature_id():
    """Verify missing feature ID returns UNAVAILABLE without failing silently."""
    fs = FlagsmithService()
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="valid_admin_token")):
        result = await fs.update_feature_state_remote(enabled=True, feature_name="unregistered_feature", feature_id=None)

        assert result["success"] is False
        assert result["status"] == "UNAVAILABLE"
        assert "Missing feature ID" in result["error"]


@pytest.mark.asyncio
async def test_flagsmith_management_api_403_404_and_network_error():
    """Verify 403 Forbidden, 404 Not Found, and Network exceptions return proper status."""
    fs = FlagsmithService()

    # 403 Forbidden
    mock_403 = MagicMock(status_code=403)
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="restricted_key")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.env")), \
         patch("httpx.AsyncClient.get", return_value=mock_403):
        res_403 = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert res_403["success"] is False
        assert res_403["status"] == "UNAVAILABLE"
        assert res_403["status_code"] == 403

    # 404 Not Found
    mock_404 = MagicMock(status_code=404)
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="valid_key")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.env")), \
         patch("httpx.AsyncClient.get", return_value=mock_404):
        res_404 = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert res_404["success"] is False
        assert res_404["status_code"] == 404

    # Network Exception
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="valid_key")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="ser.env")), \
         patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Connection timeout")):
        res_net = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert res_net["success"] is False
        assert res_net["status"] == "UNAVAILABLE"
        assert "ConnectTimeout" in res_net["error"]


@pytest.mark.asyncio
async def test_flagsmith_surge_mode_remote_targets_correct_surge_feature():
    """Verify update_surge_mode_remote targets surge_survival_mode (299379), not express delivery."""
    fs = FlagsmithService()
    with patch.object(fs, "update_feature_state_remote", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"success": True, "source": "flagsmith_remote_admin"}
        res = await fs.update_surge_mode_remote(True)

        assert mock_update.call_count == 1
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["enabled"] is True
        assert call_kwargs["feature_name"] == "surge_survival_mode"
        assert call_kwargs["feature_id"] == "299379"
        assert res["surge_mode_active"] is True


@pytest.mark.asyncio
async def test_flagsmith_management_api_v2_versioning_flow():
    """Verify Flagsmith Management API seamlessly handles environments with v2 feature versioning."""
    fs = FlagsmithService()

    # Initial legacy featurestate get
    mock_get_fs = MagicMock(status_code=200)
    mock_get_fs.json.return_value = {"results": [{"id": 1856917, "enabled": False}]}

    # Legacy patch fails with 400 because environment uses v2 feature versioning
    mock_patch_fail = MagicMock(status_code=400, text='{"detail":"This environment uses v2 feature versioning. Use the environment feature version endpoint instead."}')

    # Environment meta returns env_id 118673
    mock_env_meta = MagicMock(status_code=200)
    mock_env_meta.json.return_value = {"id": 118673, "name": "Development"}

    # Draft version create returns uuid
    mock_post_draft = MagicMock(status_code=201)
    mock_post_draft.json.return_value = {"uuid": "test-draft-uuid-123"}

    # Draft featurestates get
    mock_get_draft_fs = MagicMock(status_code=200)
    mock_get_draft_fs.json.return_value = [{"id": 9999, "enabled": False}]

    # Draft featurestate patch
    mock_patch_draft = MagicMock(status_code=200)

    # Version publish post
    mock_post_publish = MagicMock(status_code=200)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="8coM1k1z.test_api_key")), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value="SEgA7VXmvu5AbDLRjpZsrM")), \
         patch("httpx.AsyncClient.get", side_effect=[mock_get_fs, mock_env_meta, mock_get_draft_fs]), \
         patch("httpx.AsyncClient.patch", side_effect=[mock_patch_fail, mock_patch_draft]), \
         patch("httpx.AsyncClient.post", side_effect=[mock_post_draft, mock_post_publish]):

        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert result["success"] is True
        assert result["status"] == "LIVE"
        assert result["version_uuid"] == "test-draft-uuid-123"
        assert "v2 versioning" in result["message"]

