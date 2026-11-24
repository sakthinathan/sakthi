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
        if flag_name in self.local_overrides:
            return self.local_overrides[flag_name]

        if self.client:
            try:
                if identity:
                    identity_flags = self.client.get_identity_flags(identifier=identity, traits=traits or {})
                    return identity_flags.get_feature_value(flag_name)
                else:
                    env_flags = self.client.get_environment_flags()
                    return env_flags.get_feature_value(flag_name)
            except Exception as e:
                logger.warn("Flagsmith API call failed, falling back to default", flag=flag_name, error=type(e).__name__)

        return DEFAULT_FLAGS.get(flag_name)

    def is_flag_enabled(self, flag_name: str, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> bool:
        """Check if flag is enabled"""
        if flag_name in self.local_overrides:
            return bool(self.local_overrides[flag_name])

        if self.client:
            try:
                if identity:
                    identity_flags = self.client.get_identity_flags(identifier=identity, traits=traits or {})
                    return identity_flags.is_feature_enabled(flag_name)
                else:
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
            * VIP customers retain express delivery eligibility
            * Non-VIP customers have express delivery disabled to shed load
        - Non-Surge Mode:
            * Governed by base feature flag state
        """
        traits = {"tier": "VIP"} if is_vip else {"tier": "STANDARD"}
        identifier = customer_id or ("vip-customer-eval" if is_vip else "standard-customer-eval")

        surge_active = self.get_surge_mode()

        # Retrieve evaluated feature flag for identity
        if self.client:
            try:
                identity_flags = self.client.get_identity_flags(identifier=identifier, traits=traits)
                raw_express = identity_flags.is_feature_enabled("express_delivery_enabled")
                source = "flagsmith_live_identity"
            except Exception as e:
                logger.warn("Flagsmith identity flag check failed, using fallback", error=type(e).__name__)
                raw_express = self.get_express_delivery_enabled(identifier)
                source = "flagsmith_fallback"
        else:
            raw_express = self.get_express_delivery_enabled(identifier)
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
        feature_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute real HTTP PATCH against the official Flagsmith Management API.
        When admin key is configured:
        1. Queries environment feature state
        2. Issues PATCH request with {"enabled": enabled}
        3. Reads updated state back to confirm remote change
        When admin key is absent:
        - Falls back to local override and explicitly reports source as 'local_override'
        When remote call fails:
        - Returns visible error without pretending success
        """
        target_feature_id = feature_id or self.settings.flagsmith_express_delivery_feature_id or "299380"
        admin_key = self.settings.flagsmith_admin_key
        env_key = self.settings.flagsmith_environment_key

        if not admin_key or admin_key.startswith("your-"):
            # Explicit local fallback
            self.local_overrides["express_delivery_enabled"] = enabled
            logger.info("Flagsmith admin key absent; applied local override", enabled=enabled)
            return {
                "success": True,
                "enabled": enabled,
                "source": "local_override",
                "feature_id": target_feature_id,
                "message": "FLAGSMITH_ADMIN_API_KEY absent; applied local in-memory override"
            }

        headers = {
            "Authorization": f"Token {admin_key}",
            "Content-Type": "application/json"
        }

        # Official Flagsmith Management API endpoint for environment feature states
        base_api = "https://api.flagsmith.com/api/v1"
        search_url = f"{base_api}/environments/{env_key}/feature-states/?feature={target_feature_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                get_resp = await client.get(search_url, headers=headers)

                if get_resp.status_code == 401:
                    logger.error("Flagsmith Management API returned 401 Unauthorized")
                    return {
                        "success": False,
                        "enabled": self.get_express_delivery_enabled(),
                        "source": "remote_failed",
                        "status_code": 401,
                        "error": "Flagsmith Management API returned 401 Unauthorized. Invalid or expired admin key."
                    }

                if get_resp.status_code != 200:
                    logger.error("Flagsmith Management API feature search failed", status_code=get_resp.status_code)
                    return {
                        "success": False,
                        "enabled": self.get_express_delivery_enabled(),
                        "source": "remote_failed",
                        "status_code": get_resp.status_code,
                        "error": f"Flagsmith feature state query returned HTTP {get_resp.status_code}"
                    }

                results = get_resp.json().get("results", [])
                if not results:
                    return {
                        "success": False,
                        "enabled": self.get_express_delivery_enabled(),
                        "source": "remote_failed",
                        "error": f"Feature ID {target_feature_id} not found in environment {env_key}"
                    }

                feature_state_id = results[0]["id"]
                patch_url = f"{base_api}/environments/{env_key}/feature-states/{feature_state_id}/"

                # Apply PATCH
                patch_resp = await client.patch(patch_url, headers=headers, json={"enabled": enabled})
                if patch_resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "enabled": self.get_express_delivery_enabled(),
                        "source": "remote_failed",
                        "status_code": patch_resp.status_code,
                        "error": f"Flagsmith PATCH returned HTTP {patch_resp.status_code}"
                    }

                # Confirm remote change
                confirm_resp = await client.get(patch_url, headers=headers)
                updated_state = confirm_resp.json().get("enabled")

                # Keep local state in sync with confirmed remote state
                self.local_overrides["express_delivery_enabled"] = updated_state
                logger.info("Flagsmith Management API update confirmed", enabled=updated_state, feature_id=target_feature_id)

                return {
                    "success": True,
                    "enabled": updated_state,
                    "source": "flagsmith_remote_admin",
                    "feature_id": target_feature_id,
                    "feature_state_id": feature_state_id,
                    "message": f"Successfully updated feature {target_feature_id} state to {updated_state} via Flagsmith Management API"
                }

        except Exception as e:
            logger.error("Flagsmith Management API network error", error=type(e).__name__)
            return {
                "success": False,
                "enabled": self.get_express_delivery_enabled(),
                "source": "remote_failed",
                "error": f"Network exception contacting Flagsmith Management API: {type(e).__name__}"
            }

    async def update_surge_mode_remote(self, enabled: bool) -> Dict[str, Any]:
        """
        Triggered during surge or AIOps remediation.
        Updates surge mode and coordinates express delivery shedding.
        """
        self.toggle_surge_mode(enabled)
        # In surge mode, shed non-critical load remotely via Flagsmith
        result = await self.update_feature_state_remote(enabled=not enabled)
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
