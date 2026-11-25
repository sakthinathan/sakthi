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


# --- FLAGSMITH MANAGEMENT API V2 VERSIONING & EDGE CONFIRMATION TESTS ---

DUMMY_ADMIN_KEY = "test_admin_prefix.mock_secret_token_value_32chars!"
DUMMY_ENV_ID = "118673"
DUMMY_SDK_KEY = "ser.mock_test_sdk_key_for_edge_evaluation"


@pytest.mark.asyncio
async def test_flagsmith_test_1_missing_admin_key():
    """1. Missing admin key falls back to local override with explicit LOCAL_OVERRIDE status."""
    fs = FlagsmithService()
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=None)):
        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert result["success"] is True
        assert result["source"] == "local_override"
        assert result["status"] == "LOCAL_OVERRIDE"
        assert "local in-memory override" in result["message"]


@pytest.mark.asyncio
async def test_flagsmith_test_2_missing_environment_id():
    """2. Missing environment ID returns UNAVAILABLE without making any network calls."""
    fs = FlagsmithService()
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=None)), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert result["success"] is False
        assert result["status"] == "UNAVAILABLE"
        assert "FLAGSMITH_ENVIRONMENT_ID is not configured" in result["error"]
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_flagsmith_test_3_invalid_environment_id_404():
    """3. Invalid environment ID returns HTTP 404 from Flagsmith and UNAVAILABLE status."""
    fs = FlagsmithService()
    mock_404 = MagicMock(status_code=404)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value="999999_invalid")), \
         patch("httpx.AsyncClient.get", return_value=mock_404):

        result = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert result["success"] is False
        assert result["status"] == "UNAVAILABLE"
        assert result["status_code"] == 404
        assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_test_4_unauthorized_and_forbidden():
    """4. Unauthorized (401) and Forbidden (403) responses return UNAVAILABLE without falsely claiming success."""
    fs = FlagsmithService()

    # 401 Unauthorized
    mock_401 = MagicMock(status_code=401)
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value="invalid_token")), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", return_value=mock_401):

        res_401 = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res_401["success"] is False
        assert res_401["status"] == "UNAVAILABLE"
        assert res_401["status_code"] == 401
        assert "401" in res_401["error"]

    # 403 Forbidden
    mock_403 = MagicMock(status_code=403)
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", return_value=mock_403):

        res_403 = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res_403["success"] is False
        assert res_403["status"] == "UNAVAILABLE"
        assert res_403["status_code"] == 403
        assert "403" in res_403["error"]


@pytest.mark.asyncio
async def test_flagsmith_test_5_feature_id_not_found():
    """5. Missing or unregistered feature ID returns UNAVAILABLE without making calls."""
    fs = FlagsmithService()
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)):

        res = await fs.update_feature_state_remote(enabled=True, feature_name="unregistered_custom_feature", feature_id=None)
        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert "Missing feature ID" in res["error"]


@pytest.mark.asyncio
async def test_flagsmith_test_6_draft_creation_failure():
    """6. Failure during draft version creation (POST) returns UNAVAILABLE."""
    fs = FlagsmithService()
    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": []}  # No existing draft

    mock_create_fail = MagicMock(status_code=500)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", return_value=mock_list), \
         patch("httpx.AsyncClient.post", return_value=mock_create_fail):

        res = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert res["status_code"] == 500
        assert "create draft version" in res["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_test_7_draft_featurestate_lookup_failure():
    """7. Failure retrieving feature states inside draft version returns UNAVAILABLE."""
    fs = FlagsmithService()
    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs_fail = MagicMock(status_code=502)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs_fail]):

        res = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert res["status_code"] == 502
        assert "draft feature states" in res["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_test_8_draft_patch_failure():
    """8. Failure during draft feature state PATCH returns UNAVAILABLE."""
    fs = FlagsmithService()
    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs = MagicMock(status_code=200)
    mock_fs.json.return_value = [{"id": 5555, "feature": 299379, "enabled": False}]

    mock_patch_fail = MagicMock(status_code=400)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch_fail):

        res = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert res["status_code"] == 400
        assert "draft feature state patch failed" in res["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_test_9_publish_failure():
    """9. Failure during draft version publish returns UNAVAILABLE."""
    fs = FlagsmithService()
    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs = MagicMock(status_code=200)
    mock_fs.json.return_value = [{"id": 5555, "feature": 299379, "enabled": False}]

    mock_patch = MagicMock(status_code=200)
    mock_pub_fail = MagicMock(status_code=500)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch), \
         patch("httpx.AsyncClient.post", return_value=mock_pub_fail):

        res = await fs.update_feature_state_remote(enabled=True, feature_id="299379")
        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert res["status_code"] == 500
        assert "publish failed" in res["error"].lower()


@pytest.mark.asyncio
async def test_flagsmith_test_10_publish_succeeds_but_edge_confirmation_fails():
    """10. Version publish succeeds but Edge API confirmation fails (network/error); does NOT report LIVE or update local state."""
    fs = FlagsmithService()
    fs.local_overrides.clear()

    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs = MagicMock(status_code=200)
    mock_fs.json.return_value = [{"id": 5555, "feature": 299379, "enabled": False}]

    mock_patch = MagicMock(status_code=200)
    mock_pub = MagicMock(status_code=200)

    # Edge API times out
    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value=DUMMY_SDK_KEY)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs, httpx.ConnectTimeout("Edge timeout")]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch), \
         patch("httpx.AsyncClient.post", return_value=mock_pub):

        res = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert res["success"] is False
        assert res["status"] == "UNAVAILABLE"
        assert res["source"] == "remote_unconfirmed"
        assert "Edge API confirmation failed" in res["error"]
        # Verify local override was NOT falsely set to True
        assert fs.local_overrides.get("surge_survival_mode") is not True


@pytest.mark.asyncio
async def test_flagsmith_test_11_edge_returns_mismatch():
    """11. Edge API confirmation returns value different from requested; returns REMOTE_MISMATCH and does not update local state."""
    fs = FlagsmithService()
    fs.local_overrides.clear()

    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs = MagicMock(status_code=200)
    mock_fs.json.return_value = [{"id": 5555, "feature": 299379, "enabled": False}]

    mock_patch = MagicMock(status_code=200)
    mock_pub = MagicMock(status_code=200)

    # Edge API returns enabled=False when we requested enabled=True
    mock_edge = MagicMock(status_code=200)
    mock_edge.json.return_value = [
        {"feature": {"id": 299379, "name": "surge_survival_mode"}, "enabled": False}
    ]

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value=DUMMY_SDK_KEY)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs, mock_edge]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch), \
         patch("httpx.AsyncClient.post", return_value=mock_pub):

        res = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert res["success"] is False
        assert res["status"] == "REMOTE_MISMATCH"
        assert res["source"] == "remote_mismatch"
        assert "mismatch" in res["error"].lower()
        # Verify local override was NOT falsely updated
        assert fs.local_overrides.get("surge_survival_mode") is not True


@pytest.mark.asyncio
async def test_flagsmith_test_12_successful_publish_and_matching_edge_confirmation():
    """12. Successful v2 draft update, publish, and matching Edge confirmation returns LIVE and syncs local state."""
    fs = FlagsmithService()
    fs.local_overrides.clear()

    mock_list = MagicMock(status_code=200)
    mock_list.json.return_value = {"results": [{"uuid": "draft-uuid-001", "published": False}]}

    mock_fs = MagicMock(status_code=200)
    mock_fs.json.return_value = [{"id": 5555, "feature": 299379, "enabled": False}]

    mock_patch = MagicMock(status_code=200)
    mock_pub = MagicMock(status_code=200)

    # Edge API confirms enabled=True
    mock_edge = MagicMock(status_code=200)
    mock_edge.json.return_value = [
        {"feature": {"id": 299379, "name": "surge_survival_mode"}, "enabled": True}
    ]

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value=DUMMY_SDK_KEY)), \
         patch("httpx.AsyncClient.get", side_effect=[mock_list, mock_fs, mock_edge]), \
         patch("httpx.AsyncClient.patch", return_value=mock_patch), \
         patch("httpx.AsyncClient.post", return_value=mock_pub):

        res = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")

        assert res["success"] is True
        assert res["status"] == "LIVE"
        assert res["enabled"] is True
        assert res["version_uuid"] == "draft-uuid-001"
        assert res["source"] == "flagsmith_remote_admin"
        assert fs.local_overrides.get("surge_survival_mode") is True


@pytest.mark.asyncio
async def test_flagsmith_test_13_no_accidental_environment_discovery():
    """13. Explicit environment ID guarantees NO /api/v1/projects/ calls or accidental cross-environment mutation."""
    fs = FlagsmithService()

    requested_urls = []

    async def mock_tracking_get(url, **kwargs):
        requested_urls.append(str(url))
        if "/versions/" in str(url) and not "/featurestates/" in str(url):
            m = MagicMock(status_code=200)
            m.json.return_value = {"results": [{"uuid": "draft-007", "published": False}]}
            return m
        elif "/featurestates/" in str(url):
            m = MagicMock(status_code=200)
            m.json.return_value = [{"id": 777, "feature": 299379, "enabled": False}]
            return m
        elif "/flags/" in str(url):
            m = MagicMock(status_code=200)
            m.json.return_value = [{"feature": {"id": 299379, "name": "surge_survival_mode"}, "enabled": True}]
            return m
        return MagicMock(status_code=404)

    with patch.object(Settings, "flagsmith_admin_key", PropertyMock(return_value=DUMMY_ADMIN_KEY)), \
         patch.object(Settings, "flagsmith_environment_id", PropertyMock(return_value=DUMMY_ENV_ID)), \
         patch.object(Settings, "flagsmith_environment_key", PropertyMock(return_value=DUMMY_SDK_KEY)), \
         patch("httpx.AsyncClient.get", side_effect=mock_tracking_get), \
         patch("httpx.AsyncClient.patch", return_value=MagicMock(status_code=200)), \
         patch("httpx.AsyncClient.post", return_value=MagicMock(status_code=200)):

        res = await fs.update_feature_state_remote(enabled=True, feature_name="surge_survival_mode", feature_id="299379")
        assert res["success"] is True

        # Assert no project discovery URLs were ever touched
        for url in requested_urls:
            assert "/projects/" not in url, f"Accidental project discovery detected: {url}"


@pytest.mark.asyncio
async def test_flagsmith_test_14_surge_update_changes_only_surge_flag():
    """14. Surge update modifies only surge_survival_mode (299379) and leaves express_delivery_enabled untouched."""
    fs = FlagsmithService()
    with patch.object(fs, "update_feature_state_remote", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"success": True, "source": "flagsmith_remote_admin", "status": "LIVE"}
        res = await fs.update_surge_mode_remote(True)

        assert mock_update.call_count == 1
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["enabled"] is True
        assert call_kwargs["feature_name"] == "surge_survival_mode"
        assert call_kwargs["feature_id"] == "299379"
        assert call_kwargs["feature_id"] != "299380"
        assert res["surge_mode_active"] is True


def test_flagsmith_test_15_vip_express_behavior_during_surge_and_base_disabled():
    """15. VIP express delivery rules during surge mode and when base express is globally disabled."""
    fs = FlagsmithService()
    fs.local_overrides.clear()

    # Normal mode: Both VIP and Standard allowed
    fs.toggle_surge_mode(False)
    assert fs.evaluate_vip_express_delivery("v1", is_vip=True)["allowed"] is True
    assert fs.evaluate_vip_express_delivery("s1", is_vip=False)["allowed"] is True

    # Surge mode: VIP allowed, Standard load-shed
    fs.toggle_surge_mode(True)
    assert fs.evaluate_vip_express_delivery("v2", is_vip=True)["allowed"] is True
    assert fs.evaluate_vip_express_delivery("s2", is_vip=False)["allowed"] is False

    # Base express delivery globally disabled: BOTH blocked even if VIP
    fs.local_overrides["express_delivery_enabled"] = False
    assert fs.evaluate_vip_express_delivery("v3", is_vip=True)["allowed"] is False
    assert fs.evaluate_vip_express_delivery("s3", is_vip=False)["allowed"] is False
    fs.local_overrides.clear()

