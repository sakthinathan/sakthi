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
        Execute authenticated HTTP requests against the official Flagsmith Management API (v2 versioning).

        Strict Requirements:
        - Requires explicit FLAGSMITH_ADMIN_API_KEY and FLAGSMITH_ENVIRONMENT_ID.
        - Never uses SDK client key as Management API environment ID.
        - Never guesses or auto-selects environments from /projects/.
        - Queries existing draft versions to reuse rather than creating redundant drafts.
        - Updates draft feature state via PATCH.
        - Publishes version via POST publish.
        - CONFIRMS the published change by querying the Edge API with the SDK environment key.
        - Returns status 'LIVE' ONLY when the Edge API returns the requested value.
        - If Edge API fails, unreachable, or returns mismatch, returns 'UNAVAILABLE' or 'REMOTE_MISMATCH'
          and does NOT update local override.
        """
        if feature_id:
            target_feature_id = str(feature_id).strip()
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
        env_id = self.settings.flagsmith_environment_id
        sdk_key = self.settings.flagsmith_environment_key

        # If admin key is missing or dummy placeholder, report LOCAL_OVERRIDE
        if not admin_key or admin_key.startswith("your-"):
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

        # Strict validation: environment ID must be explicitly configured
        if not env_id or str(env_id).startswith("your-") or not str(env_id).strip():
            logger.error("Flagsmith update failed: FLAGSMITH_ENVIRONMENT_ID not configured")
            return {
                "success": False,
                "enabled": self.is_flag_enabled(feature_name),
                "source": "remote_failed",
                "status": "UNAVAILABLE",
                "feature_name": feature_name,
                "feature_id": target_feature_id,
                "error": "FLAGSMITH_ENVIRONMENT_ID is not configured. An explicit numeric environment ID is required for Management API operations."
            }

        clean_env_id = str(env_id).strip()

        # Build auth header - never expose secret key in logs or messages
        auth_val = f"Api-Key {admin_key}" if ("." in admin_key or admin_key.startswith("Api-Key")) else f"Token {admin_key}"
        headers = {
            "Authorization": auth_val,
            "Content-Type": "application/json"
        }

        base_api = "https://api.flagsmith.com/api/v1"
        versions_url = f"{base_api}/environments/{clean_env_id}/features/{target_feature_id}/versions/"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Inspect existing versions to verify permissions and avoid duplicate draft creation
                list_resp = await client.get(versions_url, headers=headers)

                if list_resp.status_code in (401, 403):
                    logger.error("Flagsmith Management API unauthorized", status_code=list_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": list_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith Management API returned HTTP {list_resp.status_code}. Key lacks write permission."
                    }

                if list_resp.status_code == 404:
                    logger.error("Flagsmith environment ID or feature ID not found", env_id=clean_env_id, feature_id=target_feature_id)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": 404,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Environment ID '{clean_env_id}' or feature ID '{target_feature_id}' not found on Flagsmith (HTTP 404)"
                    }

                if list_resp.status_code != 200:
                    logger.error("Flagsmith Management API versions query failed", status_code=list_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": list_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith versions query returned HTTP {list_resp.status_code}"
                    }

                # 2. Check for an existing unpublished draft version to avoid duplicate drafts
                draft_uuid = None
                versions_data = list_resp.json()
                results = versions_data.get("results", versions_data) if isinstance(versions_data, dict) else versions_data
                if isinstance(results, list):
                    for v in results:
                        if isinstance(v, dict) and v.get("published") is False and v.get("uuid"):
                            draft_uuid = v["uuid"]
                            break

                # If no existing draft, create one
                if not draft_uuid:
                    create_resp = await client.post(versions_url, headers=headers, json={})
                    if create_resp.status_code not in (200, 201):
                        logger.error("Flagsmith draft version creation failed", status_code=create_resp.status_code)
                        return {
                            "success": False,
                            "enabled": self.is_flag_enabled(feature_name),
                            "source": "remote_failed",
                            "status": "UNAVAILABLE",
                            "status_code": create_resp.status_code,
                            "feature_name": feature_name,
                            "feature_id": target_feature_id,
                            "error": f"Failed to create draft version (HTTP {create_resp.status_code})"
                        }
                    draft_uuid = create_resp.json().get("uuid")

                if not draft_uuid:
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": "Failed to obtain valid draft version UUID from Flagsmith"
                    }

                # 3. Retrieve feature states inside this draft version
                draft_fs_url = f"{base_api}/environments/{clean_env_id}/features/{target_feature_id}/versions/{draft_uuid}/featurestates/"
                fs_resp = await client.get(draft_fs_url, headers=headers)
                if fs_resp.status_code != 200:
                    logger.error("Flagsmith draft feature states lookup failed", status_code=fs_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": fs_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Failed to retrieve draft feature states (HTTP {fs_resp.status_code})"
                    }

                fs_data = fs_resp.json()
                fs_items = fs_data if isinstance(fs_data, list) else fs_data.get("results", [])
                if not fs_items:
                    logger.error("No feature states found in Flagsmith draft version")
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": "No feature state entries found in draft version"
                    }

                draft_fs_id = fs_items[0].get("id")
                if not draft_fs_id:
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": "Draft feature state missing ID"
                    }

                # 4. Update the draft feature state
                patch_fs_url = f"{base_api}/environments/{clean_env_id}/features/{target_feature_id}/versions/{draft_uuid}/featurestates/{draft_fs_id}/"
                patch_resp = await client.patch(patch_fs_url, headers=headers, json={"enabled": enabled})
                if patch_resp.status_code not in (200, 201):
                    logger.error("Flagsmith draft feature state PATCH failed", status_code=patch_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": patch_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Draft feature state PATCH failed (HTTP {patch_resp.status_code})"
                    }

                # 5. Publish the draft version
                pub_url = f"{base_api}/environments/{clean_env_id}/features/{target_feature_id}/versions/{draft_uuid}/publish/"
                pub_resp = await client.post(pub_url, headers=headers, json={})
                if pub_resp.status_code not in (200, 201):
                    logger.error("Flagsmith version publish failed", status_code=pub_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_failed",
                        "status": "UNAVAILABLE",
                        "status_code": pub_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "error": f"Flagsmith version publish failed (HTTP {pub_resp.status_code})"
                    }

                # 6. CRITICAL: Confirm published value via Edge API evaluation
                if not sdk_key:
                    logger.warn("SDK environment key absent; cannot confirm via Edge API")
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_unconfirmed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": "Version published on Management API but cannot confirm: FLAGSMITH_ENV_KEY is absent"
                    }

                edge_url = "https://edge.api.flagsmith.com/api/v1/flags/"
                edge_headers = {"X-Environment-Key": sdk_key}
                try:
                    edge_resp = await client.get(edge_url, headers=edge_headers)
                except Exception as edge_err:
                    logger.error("Flagsmith Edge API confirmation network error", error=type(edge_err).__name__)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_unconfirmed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": f"Version published but Edge API confirmation failed: {type(edge_err).__name__}"
                    }

                if edge_resp.status_code != 200:
                    logger.error("Flagsmith Edge API confirmation returned non-200", status_code=edge_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_unconfirmed",
                        "status": "UNAVAILABLE",
                        "status_code": edge_resp.status_code,
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": f"Version published but Edge API returned HTTP {edge_resp.status_code}"
                    }

                # Parse Edge API flags
                edge_flags = edge_resp.json()
                confirmed_val = None
                found_flag = False
                if isinstance(edge_flags, list):
                    for f in edge_flags:
                        feat_info = f.get("feature", {})
                        if str(feat_info.get("id")) == str(target_feature_id) or feat_info.get("name") == feature_name:
                            confirmed_val = f.get("enabled")
                            found_flag = True
                            break

                if not found_flag:
                    logger.error("Flagsmith Edge API confirmation flag not found", feature=feature_name)
                    return {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_unconfirmed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": f"Feature '{feature_name}' not found in Edge API flags"
                    }

                if confirmed_val != enabled:
                    logger.error("Flagsmith Edge confirmation mismatch", expected=enabled, actual=confirmed_val)
                    return {
                        "success": False,
                        "enabled": confirmed_val,
                        "source": "remote_mismatch",
                        "status": "REMOTE_MISMATCH",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": f"Edge API confirmation mismatch: expected {enabled}, but Edge returned {confirmed_val}"
                    }

                # 7. Success: Edge API verified and matches! Sync local state and return LIVE
                self.local_overrides[feature_name] = confirmed_val
                logger.info("Flagsmith v2 update confirmed via Edge API", feature=feature_name, enabled=confirmed_val, version_uuid=draft_uuid)
                return {
                    "success": True,
                    "enabled": confirmed_val,
                    "source": "flagsmith_remote_admin",
                    "status": "LIVE",
                    "feature_name": feature_name,
                    "feature_id": target_feature_id,
                    "version_uuid": draft_uuid,
                    "message": f"Successfully updated feature '{feature_name}' ({target_feature_id}) to {confirmed_val} via Flagsmith Management API and confirmed via Edge API"
                }

        except httpx.HTTPError as e:
            logger.error("Flagsmith Management API HTTP exception", error=type(e).__name__)
            return {
                "success": False,
                "enabled": self.is_flag_enabled(feature_name),
                "source": "remote_failed",
                "status": "UNAVAILABLE",
                "feature_name": feature_name,
                "feature_id": target_feature_id,
                "error": f"HTTP error contacting Flagsmith Management API: {type(e).__name__}"
            }
        except Exception as e:
            logger.error("Flagsmith Management API unexpected exception", error=type(e).__name__)
            return {
                "success": False,
                "enabled": self.is_flag_enabled(feature_name),
                "source": "remote_failed",
                "status": "UNAVAILABLE",
                "feature_name": feature_name,
                "feature_id": target_feature_id,
                "error": f"Unexpected error contacting Flagsmith Management API: {type(e).__name__}"
            }

    async def update_surge_mode_remote(self, enabled: bool) -> Dict[str, Any]:
        """
        Triggered when operator toggles Surge Survival Mode.
        Target flag: surge_survival_mode (Feature ID: 299379).
        Does NOT alter express_delivery_enabled; surge load-shedding is enforced
        dynamically via server-side VIP evaluation.
        """
        feature_id = self.settings.flagsmith_surge_mode_feature_id or "299379"
        result = await self.update_feature_state_remote(
            enabled=enabled,
            feature_name="surge_survival_mode",
            feature_id=feature_id
        )
        if result.get("success"):
            self.toggle_surge_mode(enabled)
            result["surge_mode_active"] = enabled
        else:
            result["surge_mode_active"] = self.get_surge_mode()
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
