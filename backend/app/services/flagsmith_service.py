"""
Flagsmith Integration & Business Rules Service
Integrates Flagsmith SDK with live evaluation, fallback modes, and VIP segment rules.

Flags:
- surge_survival_mode: bool
- express_delivery_enabled: bool
- festive_bundle_price: float / string
- sarvam_ai_routing: string

VIP Segment:
- vip_festive_buyers
"""
from typing import Dict, Any, Optional
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
                logger.info("Flagsmith SDK initialized successfully", env_key=self.settings.flagsmith_environment_key[:8] + "...")
            except Exception as e:
                logger.error("Failed to initialize Flagsmith SDK, falling back to local evaluation", error=str(e))
                self.client = None
        else:
            logger.info("Flagsmith environment key not configured; using local resilient rule engine")

    def get_flag_value(self, flag_name: str, identity: Optional[str] = None, traits: Optional[Dict[str, Any]] = None) -> Any:
        """Evaluate flag value for environment or specific customer identity"""
        # Check local runtime overrides first (e.g. operator toggle during surge)
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
                logger.warning("Flagsmith API call failed, falling back to default", flag=flag_name, error=str(e))

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
                logger.warning("Flagsmith evaluation error, falling back", flag=flag_name, error=str(e))

        return bool(DEFAULT_FLAGS.get(flag_name, False))

    def get_surge_mode(self) -> bool:
        """Check if surge survival mode is active"""
        return self.is_flag_enabled("surge_survival_mode")

    def toggle_surge_mode(self, enabled: bool) -> bool:
        """Operator toggle for surge mode"""
        self.local_overrides["surge_survival_mode"] = enabled
        logger.info("Surge survival mode state updated", enabled=enabled)
        return enabled

    def get_express_delivery_enabled(self, identity: Optional[str] = None) -> bool:
        return self.is_flag_enabled("express_delivery_enabled", identity=identity)

    def get_festive_bundle_price(self, identity: Optional[str] = None) -> float:
        val = self.get_flag_value("festive_bundle_price", identity=identity)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 999.0

    def should_allow_express(self, customer_id: Optional[str], is_vip: bool) -> bool:
        """
        CRITICAL BUSINESS RULE:
        During surge conditions:
        - VIP customers retain express delivery
        - Non-VIP customers have express delivery disabled
        - Server-side strictly enforced
        """
        surge_active = self.get_surge_mode()
        base_express = self.get_express_delivery_enabled(identity=customer_id)

        if not base_express:
            return False

        if surge_active:
            # During surge, ONLY VIPs retain express delivery
            return is_vip

        return True

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
                "enabled": self.get_express_delivery_enabled(identity),
                "value": self.get_express_delivery_enabled(identity),
                "source": source
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
