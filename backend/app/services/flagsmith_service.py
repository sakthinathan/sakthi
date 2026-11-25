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
from typing import Dict, Any, Optional, Tuple
import asyncio
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
        self._update_locks: Dict[Tuple[int, str, str], asyncio.Lock] = {}

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

    def _get_feature_lock(self, env_id: str, feature_id: str) -> asyncio.Lock:
        """Return a per-(event_loop, env_id, feature_id) lock to serialize concurrent draft mutations."""
        if not hasattr(self, "_update_locks"):
            self._update_locks = {}
        loop_id = id(asyncio.get_running_loop())
        key = (loop_id, env_id, feature_id)
        if key not in self._update_locks:
            self._update_locks[key] = asyncio.Lock()
        return self._update_locks[key]

    @staticmethod
    def _format_management_auth_header(admin_key: str) -> str:
        """
        Format the official Flagsmith Management API Authorization header:
        `Api-Key <token>`, without duplicating an existing `Api-Key` prefix
        and without falling back to `Token`.
        """
        cleaned = admin_key.strip()
        if cleaned.lower().startswith("api-key "):
            token = cleaned[8:].strip()
            return f"Api-Key {token}"
        if cleaned.lower().startswith("api-key"):
            remainder = cleaned[7:].strip()
            if remainder:
                return f"Api-Key {remainder}"
        return f"Api-Key {cleaned}"

    @staticmethod
    def _select_environment_feature_state(
        fs_data: Any,
        target_feature_id: str,
        clean_env_id: str,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Explicitly select the single environment-level feature state for target_feature_id.
        Rejects identity-specific, segment-specific, wrong-feature, wrong-environment,
        missing, or ambiguous entries.
        """
        if isinstance(fs_data, list):
            fs_items = fs_data
        elif isinstance(fs_data, dict) and isinstance(fs_data.get("results"), list):
            fs_items = fs_data["results"]
        else:
            return None, "Malformed draft feature states response from Flagsmith"

        if not fs_items:
            return None, "No feature state entries found in draft version"

        env_matches = []
        for item in fs_items:
            if not isinstance(item, dict):
                return None, "Malformed feature state entry in draft version"

            # Validate feature ID
            feat_val = item.get("feature")
            item_feat_id = feat_val.get("id") if isinstance(feat_val, dict) else feat_val
            if item_feat_id is None or str(item_feat_id) != str(target_feature_id):
                continue

            # Exclude identity-specific and segment-specific feature states
            if item.get("identity") is not None:
                continue
            if item.get("feature_segment") is not None or item.get("segment") is not None:
                continue

            # Validate environment ID if included in payload
            env_val = item.get("environment")
            if env_val is not None:
                item_env_id = env_val.get("id") if isinstance(env_val, dict) else env_val
                if item_env_id is not None and str(item_env_id) != str(clean_env_id):
                    continue

            if item.get("id") is None:
                return None, "Environment-level feature state missing ID"

            env_matches.append(item)

        if not env_matches:
            return None, f"No environment-level feature state found for feature ID '{target_feature_id}' in draft version"

        if len(env_matches) > 1:
            return None, f"Ambiguous draft response: {len(env_matches)} environment-level feature states found for feature ID '{target_feature_id}'"

        return env_matches[0]["id"], None

    async def update_feature_state_remote(
        self,
        enabled: bool,
        feature_name: str = "surge_survival_mode",
        feature_id: Optional[str] = None,
        edge_confirm_attempts: int = 1,
        edge_confirm_delay_s: float = 0.25,
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

        # Build auth header - always use official Flagsmith Api-Key format; never expose secret key
        auth_val = self._format_management_auth_header(admin_key)
        headers = {
            "Authorization": auth_val,
            "Content-Type": "application/json"
        }

        base_api = "https://api.flagsmith.com/api/v1"
        versions_url = f"{base_api}/environments/{clean_env_id}/features/{target_feature_id}/versions/"

        try:
            async with self._get_feature_lock(clean_env_id, target_feature_id):
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

                    # 2. Check for existing unpublished draft versions; never silently pick among multiple drafts
                    versions_data = list_resp.json()
                    if isinstance(versions_data, list):
                        results = versions_data
                    elif isinstance(versions_data, dict) and isinstance(versions_data.get("results"), list):
                        results = versions_data["results"]
                    else:
                        logger.error("Malformed Flagsmith versions response")
                        return {
                            "success": False,
                            "enabled": self.is_flag_enabled(feature_name),
                            "source": "remote_failed",
                            "status": "UNAVAILABLE",
                            "feature_name": feature_name,
                            "feature_id": target_feature_id,
                            "error": "Malformed Flagsmith versions response"
                        }

                    unpublished_drafts = [
                        v for v in results
                        if isinstance(v, dict) and v.get("published") is False and v.get("uuid")
                    ]
                    if len(unpublished_drafts) > 1:
                        logger.error(
                            "Multiple unpublished Flagsmith drafts found",
                            feature_id=target_feature_id,
                            draft_count=len(unpublished_drafts),
                        )
                        return {
                            "success": False,
                            "enabled": self.is_flag_enabled(feature_name),
                            "source": "remote_failed",
                            "status": "UNAVAILABLE",
                            "feature_name": feature_name,
                            "feature_id": target_feature_id,
                            "error": f"Multiple unpublished draft versions ({len(unpublished_drafts)}) exist for feature '{feature_name}'. Resolve drafts before mutating."
                        }

                    draft_uuid = unpublished_drafts[0]["uuid"] if len(unpublished_drafts) == 1 else None

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
                        created_data = create_resp.json()
                        draft_uuid = created_data.get("uuid") if isinstance(created_data, dict) else None

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

                    # 3. Retrieve feature states inside this draft version and select environment-level state
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

                    draft_fs_id, selection_error = self._select_environment_feature_state(
                        fs_resp.json(),
                        target_feature_id=target_feature_id,
                        clean_env_id=clean_env_id,
                    )
                    if selection_error or not draft_fs_id:
                        logger.error("Flagsmith draft feature state selection failed", reason=selection_error)
                        return {
                            "success": False,
                            "enabled": self.is_flag_enabled(feature_name),
                            "source": "remote_failed",
                            "status": "UNAVAILABLE",
                            "feature_name": feature_name,
                            "feature_id": target_feature_id,
                            "error": selection_error or "Unable to identify environment-level feature state"
                        }

                    # 4. Update the environment-level draft feature state
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
                    attempts = max(1, int(edge_confirm_attempts))
                    last_failure: Optional[Dict[str, Any]] = None

                    for attempt in range(attempts):
                        if attempt > 0 and edge_confirm_delay_s > 0:
                            await asyncio.sleep(edge_confirm_delay_s)

                        try:
                            edge_resp = await client.get(edge_url, headers=edge_headers)
                        except Exception as edge_err:
                            logger.error("Flagsmith Edge API confirmation network error", error=type(edge_err).__name__)
                            last_failure = {
                                "success": False,
                                "enabled": self.is_flag_enabled(feature_name),
                                "source": "remote_unconfirmed",
                                "status": "UNAVAILABLE",
                                "feature_name": feature_name,
                                "feature_id": target_feature_id,
                                "version_uuid": draft_uuid,
                                "error": f"Version published but Edge API confirmation failed: {type(edge_err).__name__}"
                            }
                            continue

                        if edge_resp.status_code != 200:
                            logger.error("Flagsmith Edge API confirmation returned non-200", status_code=edge_resp.status_code)
                            last_failure = {
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
                            continue

                        edge_flags = edge_resp.json()
                        confirmed_val = None
                        found_flag = False
                        if isinstance(edge_flags, list):
                            for f in edge_flags:
                                if not isinstance(f, dict):
                                    continue
                                feat_info = f.get("feature", {})
                                if not isinstance(feat_info, dict):
                                    continue
                                if str(feat_info.get("id")) == str(target_feature_id) or feat_info.get("name") == feature_name:
                                    confirmed_val = f.get("enabled")
                                    found_flag = True
                                    break

                        if not found_flag:
                            logger.error("Flagsmith Edge API confirmation flag not found", feature=feature_name)
                            last_failure = {
                                "success": False,
                                "enabled": self.is_flag_enabled(feature_name),
                                "source": "remote_unconfirmed",
                                "status": "UNAVAILABLE",
                                "feature_name": feature_name,
                                "feature_id": target_feature_id,
                                "version_uuid": draft_uuid,
                                "error": f"Feature '{feature_name}' not found in Edge API flags"
                            }
                            continue

                        if confirmed_val != enabled:
                            logger.error("Flagsmith Edge confirmation mismatch", expected=enabled, actual=confirmed_val)
                            last_failure = {
                                "success": False,
                                "enabled": confirmed_val,
                                "source": "remote_mismatch",
                                "status": "REMOTE_MISMATCH",
                                "feature_name": feature_name,
                                "feature_id": target_feature_id,
                                "version_uuid": draft_uuid,
                                "error": f"Edge API confirmation mismatch: expected {enabled}, but Edge returned {confirmed_val}"
                            }
                            continue

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

                    return last_failure or {
                        "success": False,
                        "enabled": self.is_flag_enabled(feature_name),
                        "source": "remote_unconfirmed",
                        "status": "UNAVAILABLE",
                        "feature_name": feature_name,
                        "feature_id": target_feature_id,
                        "version_uuid": draft_uuid,
                        "error": "Edge API confirmation failed"
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
