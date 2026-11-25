"""
Flagsmith Integration & Business Rules Service
Integrates Flagsmith SDK with live evaluation, VIP identity traits,
official Management API PATCH updates, and server-side surge protection.

Flags:
- surge_survival_mode: bool
- express_delivery_enabled: bool (Feature ID: 299380)
- festive_bundle_price: float / string
- sarvam_ai_routing: string

VIP Segment:
- vip_festive_buyers (triggered by trait: {"tier": "VIP"})

Security:
- FLAGSMITH_ADMIN_API_KEY is restricted to server-side operations only
- Credentials are never leaked to client responses or frontend
"""
from typing import Dict, Any, Optional
import httpx
import structlog
from app.config import get_settings

logger = structlog.get_logger()

# Safe production defaults during festive peak
DEFAULT_FLAGS = {
    "surge_survival_mode": False,
    "express_delivery_enabled": True,
    "festive_bundle_price": 999.0,
    "sarvam_ai_routing": "primary"
}


class FlagsmithService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FlagsmithService, cls).__new__(cls)
            cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        self.settings = get_settings()
        self.client = None
        self.local_overrides = {}

        if self.settings.has_flagsmith:
            try:
                from flagsmith import Flagsmith
                self.client = Flagsmith(
                    environment_key=self.settings.flagsmith_environment_key,
                    api_url=self.settings.flagsmith_server_url
                )
                logger.info(
                    "Flagsmith SDK initialized successfully",
                    env_key=self.settings.flagsmith_environment_key[:8] + "...",
                    has_admin=self.settings.has_flagsmith_admin,
                    feature_id=self.settings.flagsmith_express_delivery_feature_id
                )
            except Exception as e:
                logger.warn("Failed to initialize Flagsmith SDK, falling back to local evaluation", error=type(e).__name__)
                self.client = None
        else:
            logger.info("Flagsmith environment key not configured; using local resilient rule engine")

    def get_flag_value(self, flag_name: str, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> Any:
        """Evaluate flag value for environment or specific customer identity"""
        if identity and self.client:
            try:
                identity_flags = self.client.get_identity_flags(identifier=identity, traits=traits or {})
                return identity_flags.get_feature_value(flag_name)
            except Exception as e:
                logger.warn("Flagsmith identity flag value check failed, using fallback", flag=flag_name, error=type(e).__name__)

        if flag_name in self.local_overrides:
            return self.local_overrides[flag_name]

        if self.client:
            try:
                env_flags = self.client.get_environment_flags()
                return env_flags.get_feature_value(flag_name)
            except Exception as e:
                logger.warn("Flagsmith API call failed, falling back to default", flag=flag_name, error=type(e).__name__)

        return DEFAULT_FLAGS.get(flag_name)

    def is_flag_enabled(self, flag_name: str, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> bool:
        """Check if flag is enabled, respecting identity traits without global override bypass"""
        if identity and self.client:
            try:
                identity_flags = self.client.get_identity_flags(identifier=identity, traits=traits or {})
                return identity_flags.is_feature_enabled(flag_name)
            except Exception as e:
                logger.warn("Flagsmith identity flag check failed, using fallback", flag=flag_name, error=type(e).__name__)

        if flag_name in self.local_overrides:
            return bool(self.local_overrides[flag_name])

        if self.client:
            try:
                env_flags = self.client.get_environment_flags()
                return env_flags.is_feature_enabled(flag_name)
            except Exception as e:
                logger.warn("Flagsmith evaluation error, falling back", flag=flag_name, error=type(e).__name__)

        return bool(DEFAULT_FLAGS.get(flag_name, False))

    def get_surge_mode(self) -> bool:
        """Check if surge survival mode is active"""
        return self.is_flag_enabled("surge_survival_mode")

    def toggle_surge_mode(self, enabled: bool) -> bool:
        """Operator toggle for surge mode (local state)"""
        self.local_overrides["surge_survival_mode"] = enabled
        logger.info("Surge survival mode state updated locally", enabled=enabled)
        return enabled

    def get_express_delivery_enabled(self, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> bool:
        return self.is_flag_enabled("express_delivery_enabled", identity=identity, traits=traits)

    def get_festive_bundle_price(self, identity: Optional[str] = None) -> float:
        val = self.get_flag_value("festive_bundle_price", identity=identity)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 999.0

    def evaluate_vip_express_delivery(self, customer_id: Optional[str], is_vip: bool) -> Dict[str, Any]:
        """
        Evaluate express delivery with live Flagsmith identity traits.
        VIP customers are tagged with trait: {"tier": "VIP"} which triggers 'vip_festive_buyers'.
        Non-VIP customers have trait: {"tier": "STANDARD"}.

        Server-side Business Rules:
        - During Surge Survival Mode:
            * VIP customers retain express delivery eligibility (if base express delivery is enabled)
            * Non-VIP customers have express delivery disabled to shed load
        - Non-Surge Mode:
            * Governed by base express feature flag state
        """
        traits = {"tier": "VIP"} if is_vip else {"tier": "STANDARD"}
        identifier = customer_id or ("vip-customer-eval" if is_vip else "standard-customer-eval")

        surge_active = self.get_surge_mode()

        # Retrieve evaluated feature flag for identity
        if "express_delivery_enabled" in self.local_overrides:
            raw_express = self.local_overrides["express_delivery_enabled"]
            source = "local_override"
        elif self.client:
            try:
                identity_flags = self.client.get_identity_flags(identifier=identifier, traits=traits)
                raw_express = identity_flags.is_feature_enabled("express_delivery_enabled")
                source = "flagsmith_live_identity"
            except Exception as e:
                logger.warn("Flagsmith identity flag check failed, using fallback", error=type(e).__name__)
                raw_express = self.local_overrides.get("express_delivery_enabled", DEFAULT_FLAGS.get("express_delivery_enabled", True))
                source = "flagsmith_fallback"
        else:
            raw_express = self.local_overrides.get("express_delivery_enabled", DEFAULT_FLAGS.get("express_delivery_enabled", True))
            source = "local_evaluation"

        # Apply server-side business rules
        if surge_active:
            allowed = bool(is_vip and raw_express)
            decision_rule = "surge_vip_priority" if is_vip else "surge_non_vip_load_shed"
        else:
            allowed = bool(raw_express)
            decision_rule = "standard_delivery_policy"

        return {
            "allowed": allowed,
            "is_vip": is_vip,
            "traits": traits,
            "surge_active": surge_active,
            "raw_feature_enabled": raw_express,
            "decision_rule": decision_rule,
            "source": source,
            "segment": "vip_festive_buyers" if is_vip else "standard_buyers"
        }

    def should_allow_express(self, customer_id: Optional[str], is_vip: bool) -> bool:
        """
        Canonical server-side express delivery gate.
        Enforces VIP surge rules regardless of client state.
        """
        eval_result = self.evaluate_vip_express_delivery(customer_id, is_vip)
        return eval_result["allowed"]

    async def update_feature_state_remote(
        self,
        enabled: bool,
        feature_name: str = "surge_survival_mode",
        feature_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute real HTTP PATCH against the official Flagsmith Management API.
        When admin key is configured:
        1. Queries environment feature state for the specific target feature
        2. Issues PATCH request with {"enabled": enabled}
        3. Reads updated state back to confirm remote change (read-after-write)
        When admin key is absent:
        - Falls back to local override and explicitly reports status as 'LOCAL_OVERRIDE'
        When remote call fails:
        - Returns visible error and status 'UNAVAILABLE' without pretending success
        """
        if feature_id:
            target_feature_id = feature_id
        elif feature_name == "surge_survival_mode":
            target_feature_id = self.settings.flagsmith_surge_mode_feature_id or "299379"
        elif feature_name == "express_delivery_enabled":
            target_feature_id = self.settings.flagsmith_express_delivery_feature_id or "299380"
        else:
            target_feature_id = None

        if not target_feature_id:
            logger.error("Flagsmith update failed: missing feature ID", feature_name=feature_name)
            return {
                "success": False,
                "enabled": self.is_flag_enabled(feature_name),
                "source": "remote_failed",
                "status": "UNAVAILABLE",
                "feature_name": feature_name,
                "error": f"Missing feature ID for flag '{feature_name}'"
            }

        admin_key = self.settings.flagsmith_admin_key
        env_key = self.settings.flagsmith_environment_key

        if not admin_key or admin_key.startswith("your-"):
            # Explicit local fallback
            self.local_overrides[feature_name] = enabled
            logger.info("Flagsmith admin key absent; applied local override", feature=feature_name, enabled=enabled)
            return {
                "success": True,
                "enabled": enabled,
                "source": "local_override",
                "status": "LOCAL_OVERRIDE",
                "feature_name": feature_name,
                "feature_id": target_feature_id,
                "message": f"FLAGSMITH_ADMIN_API_KEY absent; applied local in-memory override for {feature_name}"
            }

        auth_val = f"Api-Key {admin_key}" if ("." in admin_key or admin_key.startswith("Api-Key")) else f"Token {admin_key}"
        headers = {
            "Authorization": auth_val,
            "Content-Type": "application/json"
        }

        # Official Flagsmith Management API endpoint for environment feature states
        base_api = "https://api.flagsmith.com/api/v1"
        search_url = f"{base_api}/environments/{env_key}/featurestates/?feature={target_feature_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                get_resp = await client.get(search_url, headers=headers)

                # Fallback to hyphenated endpoint if 404
                if get_resp.status_code == 404:
                    alt_url = f"{base_api}/environments/{env_key}/feature-states/?feature={target_feature_id}"
                    alt_resp = await client.get(alt_url, headers=headers)
                    if alt_resp.status_code == 200:
                        get_resp = alt_resp

                # If still 404 and env_key is a server key (ser.xxx) or alias, discover client env key from projects
                if get_resp.status_code == 404:
                    try:
                        proj_resp = await client.get(f"{base_api}/projects/", headers=headers)
                        if proj_resp.status_code == 200:
                            for p in proj_resp.json():
                                pe_resp = await client.get(f"{base_api}/projects/{p['id']}/environments/", headers=headers)
                                if pe_resp.status_code == 200:
                                    envs = pe_resp.json()
                                    if envs:
                                        m = next((e for e in envs if e.get("api_key") == env_key or e.get("name") == "Development"), envs[0])
                                        resolved_key = m.get("api_key")
                                        if resolved_key and resolved_key != env_key:
                                            res_url = f"{base_api}/environments/{resolved_key}/featurestates/?feature={target_feature_id}"
                                            res_resp = await client.get(res_url, headers=headers)
                                            if res_resp.status_code == 200:
                                                get_resp = res_resp
                                                env_key = resolved_key
                                                break
                    except Exception as discover_err:
                        logger.warn("Flagsmith environment discovery error", error=str(discover_err))

                if get_resp.status_code in (401, 403):
                    logger.error("Flagsmith Management API unauthorized", status_code=get_resp.status_code)
                    self.local_overrides[feature_name] = enabled
                    return {
                        "success": False,
                        "enabled": enabled,
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": get_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith Management API returned HTTP {get_resp.status_code}. Key lacks permission."
                    }

                if get_resp.status_code == 404:
                    logger.error("Flagsmith environment or feature not found", status_code=404)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": 404,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Environment or feature not found on Flagsmith (HTTP 404)"
                    }

                if get_resp.status_code != 200:
                    logger.error("Flagsmith Management API search failed", status_code=get_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": get_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith feature state query returned HTTP {get_resp.status_code}"
                    }

                results = get_resp.json().get("results", [])
                if not results:
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Feature ID {target_feature_id} not found in environment {env_key}"
                    }

                feature_state_id = results[0]["id"]
                patch_url = f"{base_api}/environments/{env_key}/featurestates/{feature_state_id}/"

                # Apply PATCH
                patch_resp = await client.patch(patch_url, headers=headers, json={"enabled": enabled})

                # If environment uses v2 feature versioning, gracefully execute versioning workflow
                if patch_resp.status_code == 400 and "v2 feature versioning" in patch_resp.text:
                    env_meta_resp = await client.get(f"{base_api}/environments/{env_key}/", headers=headers)
                    env_data = env_meta_resp.json() if env_meta_resp.status_code == 200 else {}
                    env_id = env_data.get("id")
                    if not env_id:
                        proj_resp = await client.get(f"{base_api}/projects/", headers=headers)
                        if proj_resp.status_code == 200:
                            for p in proj_resp.json():
                                pe_resp = await client.get(f"{base_api}/projects/{p['id']}/environments/", headers=headers)
                                if pe_resp.status_code == 200:
                                    envs = pe_resp.json()
                                    if envs:
                                        m = next((e for e in envs if e.get("api_key") == env_key or e.get("name") == "Development"), envs[0])
                                        env_id = m.get("id")
                                        break

                    if env_id:
                        draft_url = f"{base_api}/environments/{env_id}/features/{target_feature_id}/versions/"
                        draft_resp = await client.post(draft_url, headers=headers, json={})
                        if draft_resp.status_code in (200, 201):
                            draft_uuid = draft_resp.json().get("uuid")
                            draft_fs_url = f"{base_api}/environments/{env_id}/features/{target_feature_id}/versions/{draft_uuid}/featurestates/"
                            draft_fs_resp = await client.get(draft_fs_url, headers=headers)
                            if draft_fs_resp.status_code == 200:
                                fs_list = draft_fs_resp.json()
                                fs_items = fs_list if isinstance(fs_list, list) else fs_list.get("results", [])
                                if fs_items:
                                    draft_fs_id = fs_items[0]["id"]
                                    patch_draft_url = f"{base_api}/environments/{env_id}/features/{target_feature_id}/versions/{draft_uuid}/featurestates/{draft_fs_id}/"
                                    patch_draft_resp = await client.patch(patch_draft_url, headers=headers, json={"enabled": enabled})
                                    if patch_draft_resp.status_code in (200, 201):
                                        pub_url = f"{base_api}/environments/{env_id}/features/{target_feature_id}/versions/{draft_uuid}/publish/"
                                        pub_resp = await client.post(pub_url, headers=headers, json={})
                                        if pub_resp.status_code in (200, 201):
                                            self.local_overrides[feature_name] = enabled
                                            logger.info("Flagsmith v2 versioning update published and confirmed", feature=feature_name, enabled=enabled, version_uuid=draft_uuid)
                                            return {
                                                "success": True,
                                                "enabled": enabled,
                                                "source": "flagsmith_remote_admin",
                                                "status": "LIVE",
                                                "feature_name": feature_name,
                                                "feature_id": target_feature_id,
                                                "version_uuid": draft_uuid,
                                                "message": f"Successfully updated feature '{feature_name}' ({target_feature_id}) to {enabled} via Flagsmith Management API (v2 versioning)"
                                            }

                if patch_resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": patch_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith PATCH returned HTTP {patch_resp.status_code}"
                    }

                # Confirm remote change via read-after-write
                confirm_resp = await client.get(patch_url, headers=headers)
                if confirm_resp.status_code != 200:
                    return {
                        "success": False,
                        "enabled": enabled,
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": "Failed to read-after-write confirm remote feature state"
                    }

                updated_state = confirm_resp.json().get("enabled")
                if updated_state != enabled:
                    logger.error("Read-after-write mismatch on Flagsmith feature state", expected=enabled, actual=updated_state)
                    return {
                        "success": False,
                        "enabled": updated_state,
                        "source": "remote_mismatch",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Read-after-write mismatch: expected {enabled}, but remote returned {updated_state}"
                    }

                # Keep local state in sync with confirmed remote state
                self.local_overrides[feature_name] = updated_state
                logger.info("Flagsmith Management API update confirmed", feature=feature_name, enabled=updated_state, feature_id=target_feature_id)

                return {
                    "success": True,
                    "enabled": updated_state,
                    "source": "flagsmith_remote_admin",
                    "status": "LIVE",
                    "feature_name": feature_name,
                    "feature_id": target_feature_id,
                    "feature_state_id": feature_state_id,
                    "message": f"Successfully updated feature '{feature_name}' ({target_feature_id}) to {updated_state} via Flagsmith Management API"
                }

        except Exception as e:
            logger.error("Flagsmith Management API network error", error=type(e).__name__)
            return {
                "success": False,
                "enabled": self.is_flag_enabled(feature_name),
                "source": "remote_failed",
                "status": "UNAVAILABLE",
                "feature_name": feature_name,
                "feature_id": target_feature_id,
                "error": f"Network exception contacting Flagsmith Management API: {type(e).__name__}"
            }

    async def update_surge_mode_remote(self, enabled: bool) -> Dict[str, Any]:
        """
        Triggered when operator toggles Surge Survival Mode.
        Target flag: surge_survival_mode (Feature ID: 299379).
        Does NOT alter express_delivery_enabled; surge load-shedding is enforced
        dynamically via server-side VIP evaluation.
        """
        self.toggle_surge_mode(enabled)
        feature_id = self.settings.flagsmith_surge_mode_feature_id or "299379"
        result = await self.update_feature_state_remote(
            enabled=enabled,
            feature_name="surge_survival_mode",
            feature_id=feature_id
        )
        result["surge_mode_active"] = enabled
        return result

    def get_all_flags(self, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return full map of flags and business rules"""
        source = "flagsmith_live" if self.client else "local_fallback"
        return {
            "surge_survival_mode": {
                "enabled": self.get_surge_mode(),
                "value": self.get_surge_mode(),
                "source": "local_override" if "surge_survival_mode" in self.local_overrides else source
            },
            "express_delivery_enabled": {
                "enabled": self.get_express_delivery_enabled(identity, traits),
                "value": self.get_express_delivery_enabled(identity, traits),
                "feature_id": self.settings.flagsmith_express_delivery_feature_id,
                "source": "local_override" if "express_delivery_enabled" in self.local_overrides else source
            },
            "festive_bundle_price": {
                "enabled": True,
                "value": self.get_festive_bundle_price(identity),
                "source": source
            },
            "sarvam_ai_routing": {
                "enabled": True,
                "value": self.get_flag_value("sarvam_ai_routing", identity=identity),
                "source": source
            }
        }


flagsmith_service = FlagsmithService()
