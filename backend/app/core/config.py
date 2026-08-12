"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API process.

    Provider and data-path settings are declared here so later stories can reuse the
    same configuration boundary without creating clients or reading files at import
    time. Secrets are represented as ``SecretStr`` and are never logged by this layer.
    """

    app_name: str = "OmniCare Financial Customer Assistant"
    app_version: str = "0.1.0"
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str | None = None
    policy_file_path: str = "../data/sample_policy.md"
    claims_file_path: str = "../data/mock_claims.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object without performing I/O beyond env loading."""

    return Settings()
