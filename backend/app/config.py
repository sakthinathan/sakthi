"""
Centralized application configuration with Pydantic Settings.
Loads configuration from .env with secure credential validation, masking, and environment distinction.
"""
import os
import re
from pathlib import Path
from functools import lru_cache
from typing import Optional, List, Dict, Any
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator


class Settings(BaseSettings):
    """
    Validated application settings.
    Credentials and secrets are strictly masked from string representation and serialization.
    """

    # --- Application Environment ---
    app_env: str = Field("development", description="Environment mode: development, test, or production")
    app_debug: bool = Field(True, description="Enable debug mode (automatically disabled in production)")
    app_secret_key: str = Field("dev-secret-key-change-in-production", description="Secret key for cryptographic operations")
    app_host: str = Field("0.0.0.0", description="Bind host")
    app_port: int = Field(8000, description="Bind port")
    frontend_url: str = Field("http://localhost:5173", description="Frontend origin for CORS")

    # --- Google Cloud and APIs ---
    gcp_project_id: Optional[str] = Field(None, validation_alias="GCP_PROJECT_ID")
    gcp_region_raw: Optional[str] = Field(None, validation_alias="GCP_REGION")
    google_maps_aqi_addr_api_key: Optional[str] = Field(None, validation_alias="GOOGLE_MAPS_AQI_ADDR_API_KEY")
    google_maps_api_key_legacy: Optional[str] = Field(None, validation_alias="GOOGLE_MAPS_API_KEY")

    # --- Gemini API ---
    gemini_api_key: Optional[str] = Field(None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-flash-latest", validation_alias="GEMINI_MODEL")

    # --- Cloud SQL PostgreSQL ---
    db_host: Optional[str] = Field(None, validation_alias="DB_HOST")
    db_port: int = Field(5432, validation_alias="DB_PORT")
    db_name: str = Field("utsavops", validation_alias="DB_NAME")
    db_user: Optional[str] = Field(None, validation_alias="DB_USER")
    db_password: Optional[str] = Field(None, validation_alias="DB_PASSWORD")
    raw_database_url: Optional[str] = Field(None, validation_alias="DATABASE_URL")

    # Database connection pool settings
    db_pool_size: int = Field(10, description="SQLAlchemy connection pool size")
    db_max_overflow: int = Field(20, description="Maximum overflow connections")
    db_pool_timeout: int = Field(30, description="Pool connection timeout in seconds")
    db_pool_recycle: int = Field(1800, description="Recycle connections after 30 minutes")
    db_command_timeout: int = Field(15, description="AsyncPG command timeout in seconds")

    # --- Sarvam AI ---
    sarvam_api_key: Optional[str] = Field(None, validation_alias="SARVAM_API_KEY")
    sarvam_base_url: str = Field("https://api.sarvam.ai", validation_alias="SARVAM_BASE_URL")

    # --- Flagsmith ---
    flagsmith_env_key: Optional[str] = Field(None, validation_alias="FLAGSMITH_ENV_KEY")
    flagsmith_environment_key_legacy: Optional[str] = Field(None, validation_alias="FLAGSMITH_ENVIRONMENT_KEY")
    flagsmith_express_delivery_feature_id: Optional[str] = Field("299380", validation_alias="FLAGSMITH_EXPRESS_DELIVERY_FEATURE_ID")
    flagsmith_admin_api_key: Optional[str] = Field(None, validation_alias="FLAGSMITH_ADMIN_API_KEY")
    nudgebee_circuit_breaker_key: Optional[str] = Field(None, validation_alias="NUDGEBEE_CIRCUIT_BREAKER_KEY")
    flagsmith_api_token_legacy: Optional[str] = Field(None, validation_alias="FLAGSMITH_API_TOKEN")
    flagsmith_server_url: str = Field("https://edge.api.flagsmith.com/api/v1/", validation_alias="FLAGSMITH_SERVER_URL")

    # --- NudgeBee & Kubernetes ---
    nudgebee_vm_name: Optional[str] = Field(None, validation_alias="NUDGEEBEE_VM_NAME")
    nudgebee_secret_name: Optional[str] = Field(None, validation_alias="NUDGEEBEE_SECRET_NAME")
    nudgebee_extra_token: Optional[str] = Field(None, validation_alias="NUDGEEBEE_EXTRA_TOKEN")
    nudgebee_api_url: Optional[str] = Field(None, validation_alias="NUDGEBEE_API_URL")
    nudgebee_api_key: Optional[str] = Field(None, validation_alias="NUDGEBEE_API_KEY")

    k8s_namespace: str = Field("utsavops", validation_alias="K8S_NAMESPACE")
    k8s_in_cluster: bool = Field(False, validation_alias="K8S_IN_CLUSTER")
    kubeconfig_path: Optional[str] = Field(None, validation_alias="KUBECONFIG_PATH")

    # Paths
    upload_dir: str = str(Path(__file__).parent.parent / "uploads")

    # --- Computed / Unified Properties ---

    @property
    def google_maps_api_key(self) -> Optional[str]:
        """Unified Google Maps / Address / AQI API Key"""
        return self.google_maps_aqi_addr_api_key or self.google_maps_api_key_legacy

    @property
    def flagsmith_environment_key(self) -> Optional[str]:
        """Unified Flagsmith Environment Client Key"""
        return self.flagsmith_env_key or self.flagsmith_environment_key_legacy

    @property
    def flagsmith_admin_key(self) -> Optional[str]:
        """Unified Flagsmith Server-side Admin / Circuit-Breaker API Key"""
        return (
            self.flagsmith_admin_api_key
            or self.nudgebee_circuit_breaker_key
            or self.flagsmith_api_token_legacy
        )

    @property
    def gcp_region(self) -> Optional[str]:
        """
        Normalized GCP Region (e.g. 'asia-south1').
        Distinguishes between a regional location and an availability zone (e.g. 'asia-south1-a').
        Cloud SQL instances reside in regions, while GCE compute instances reside in zones.
        """
        if not self.gcp_region_raw:
            return None
        # Strip trailing zone letter (e.g. 'asia-south1-a' -> 'asia-south1')
        match = re.match(r"^([a-z0-9\-]+)-[a-z]$", self.gcp_region_raw)
        if match:
            return match.group(1)
        return self.gcp_region_raw

    @property
    def gcp_zone(self) -> Optional[str]:
        """Full availability zone if specified (e.g. 'asia-south1-a')"""
        return self.gcp_region_raw

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env.lower() == "test"

    @property
    def has_sarvam(self) -> bool:
        return bool(self.sarvam_api_key and not self.sarvam_api_key.startswith("your-"))

    @property
    def has_flagsmith(self) -> bool:
        key = self.flagsmith_environment_key
        return bool(key and not key.startswith("your-"))

    @property
    def has_flagsmith_admin(self) -> bool:
        key = self.flagsmith_admin_key
        return bool(key and not key.startswith("your-"))

    @property
    def has_google_maps(self) -> bool:
        key = self.google_maps_api_key
        return bool(key and not key.startswith("your-"))

    @property
    def has_gemini(self) -> bool:
        key = self.gemini_api_key
        return bool(key and not key.startswith("your-"))

    @property
    def has_nudgebee_config(self) -> bool:
        return bool(self.nudgebee_vm_name and self.nudgebee_secret_name)

    @property
    def has_nudgebee(self) -> bool:
        return self.has_nudgebee_config

    @property
    def database_url(self) -> str:
        """
        Constructs a secure, properly URL-encoded PostgreSQL connection string using asyncpg driver.
        Falls back to local SQLite if no Cloud SQL host is configured.
        """
        if self.db_host and self.db_user and self.db_password:
            encoded_password = quote_plus(self.db_password)
            encoded_user = quote_plus(self.db_user)
            return (
                f"postgresql+asyncpg://{encoded_user}:{encoded_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}"
            )

        if self.raw_database_url:
            # Upgrade standard postgresql:// to async driver postgresql+asyncpg://
            if self.raw_database_url.startswith("postgresql://"):
                return self.raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.raw_database_url

        # Default development fallback
        return "sqlite+aiosqlite:///./utsavops.db"

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    def validate_production_readiness(self) -> List[str]:
        """
        Validates mandatory environment variables when operating in production.
        Returns a list of missing requirement messages.
        """
        missing = []
        if self.is_production:
            if not self.db_host and not self.raw_database_url:
                missing.append("Cloud SQL connection details (DB_HOST, DB_USER, DB_PASSWORD) or DATABASE_URL")
            if not self.google_maps_api_key:
                missing.append("GOOGLE_MAPS_AQI_ADDR_API_KEY")
            if not self.sarvam_api_key:
                missing.append("SARVAM_API_KEY")
            if not self.flagsmith_environment_key:
                missing.append("FLAGSMITH_ENV_KEY")
            if not self.gemini_api_key:
                missing.append("GEMINI_API_KEY")
        return missing

    def __repr__(self) -> str:
        """Redact all credentials from debug string representations"""
        return (
            f"<Settings env={self.app_env} debug={self.app_debug} "
            f"db_host={self.db_host or 'local_sqlite'} "
            f"gcp_region={self.gcp_region} "
            f"sarvam={'[CONFIGURED]' if self.has_sarvam else '[FALLBACK]'} "
            f"flagsmith={'[CONFIGURED]' if self.has_flagsmith else '[FALLBACK]'} "
            f"google_apis={'[CONFIGURED]' if self.has_google_maps else '[FALLBACK]'} "
            f"gemini={'[CONFIGURED]' if self.has_gemini else '[FALLBACK]'}>"
        )

    model_config = {
        "env_file": [".env", "../.env"],
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    settings = Settings()
    if settings.is_production:
        missing = settings.validate_production_readiness()
        if missing:
            raise ValueError(
                f"Production environment validation failed! Missing required settings: {', '.join(missing)}"
            )
    return settings
