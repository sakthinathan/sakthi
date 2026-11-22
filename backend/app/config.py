"""
Centralized application configuration.
All settings loaded from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "dev-secret-key-change-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Database
    database_url: str = "sqlite+aiosqlite:///./utsavops.db"

    # Sarvam AI
    sarvam_api_key: Optional[str] = None
    sarvam_base_url: str = "https://api.sarvam.ai"

    # Flagsmith
    flagsmith_server_url: str = "https://edge.api.flagsmith.com/api/v1/"
    flagsmith_environment_key: Optional[str] = None
    flagsmith_api_token: Optional[str] = None

    # Google APIs
    google_maps_api_key: Optional[str] = None

    # NudgeBee
    nudgebee_api_url: Optional[str] = None
    nudgebee_api_key: Optional[str] = None

    # Kubernetes
    k8s_namespace: str = "utsavops"
    k8s_in_cluster: bool = False
    kubeconfig_path: Optional[str] = None

    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    # Paths
    upload_dir: str = str(Path(__file__).parent.parent / "uploads")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def has_sarvam(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def has_flagsmith(self) -> bool:
        return bool(self.flagsmith_environment_key)

    @property
    def has_google_maps(self) -> bool:
        return bool(self.google_maps_api_key)

    @property
    def has_nudgebee(self) -> bool:
        return bool(self.nudgebee_api_url and self.nudgebee_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
