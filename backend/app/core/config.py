"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API process.

    Operational values are centralized here and can be overridden through environment
    variables. The defaults keep local tests and development runnable without a secret;
    deployments should provide their explicit values through the environment.
    """

    app_name: str = "OmniCare Financial Customer Assistant"
    app_version: str = "0.1.0"
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str | None = None
    deepseek_timeout_seconds: float = 30.0
    policy_file_path: str = "../data/sample_policy.md"
    claims_file_path: str = "../data/mock_claims.json"

    user_id_max_length: int = 128
    message_max_length: int = 8_000
    source_max_length: int = 512
    max_sources: int = 20
    tool_name_max_length: int = 64
    tool_status_max_length: int = 32
    tool_arguments_max_length: int = 1_000
    tool_result_max_length: int = 2_000
    max_tool_calls: int = 20

    claim_id_max_length: int = 64
    policy_number_max_length: int = 128
    claim_type_max_length: int = 128
    claim_status_max_length: int = 64
    claim_description_max_length: int = 4_000
    claim_amount_min: float = 0.0
    claim_amount_decimal_places: int = 2
    initial_claim_status: str = "Submitted"
    claim_id_prefix: str = "CLM-"
    claim_id_random_hex_length: int = 8
    claim_id_generation_attempts: int = 5
    request_id_max_length: int = 64
    policy_section_id_max_length: int = 64
    policy_section_title_max_length: int = 256
    policy_chunk_text_max_length: int = 12_000
    policy_source_file_max_length: int = 256
    policy_citation_max_length: int = 512
    policy_index_path: str = "../runtime/chroma"
    policy_collection_name: str = "omnicare_policy"
    policy_embedding_dimension: int = 384
    policy_retrieval_top_k: int = 2
    policy_retrieval_min_relevance: float = 0.15
    policy_query_max_length: int = 512
    policy_embedding_stopwords: str = "a,an,and,are,as,at,be,by,can,does,for,from,how,in,is,it,much,of,on,or,policy,the,to,what,when,where,with,available,cover,covered,coverage,damage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "user_id_max_length",
        "message_max_length",
        "source_max_length",
        "max_sources",
        "tool_name_max_length",
        "tool_status_max_length",
        "tool_arguments_max_length",
        "tool_result_max_length",
        "max_tool_calls",
        "claim_id_max_length",
        "policy_number_max_length",
        "claim_type_max_length",
        "claim_status_max_length",
        "claim_description_max_length",
        "claim_id_random_hex_length",
        "claim_id_generation_attempts",
        "request_id_max_length",
        "policy_section_id_max_length",
        "policy_section_title_max_length",
        "policy_chunk_text_max_length",
        "policy_source_file_max_length",
        "policy_citation_max_length",
        "policy_embedding_dimension",
        "policy_retrieval_top_k",
        "policy_query_max_length",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("configured length and collection limits must be positive")
        return value

    @field_validator("deepseek_timeout_seconds")
    @classmethod
    def validate_deepseek_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("deepseek_timeout_seconds must be positive")
        return value

    @field_validator("policy_retrieval_min_relevance")
    @classmethod
    def validate_relevance_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("policy_retrieval_min_relevance must be between 0 and 1")
        return value

    @field_validator("claim_amount_min")
    @classmethod
    def validate_minimum_amount(cls, value: float) -> float:
        if value < 0:
            raise ValueError("claim_amount_min must not be negative")
        return value

    @field_validator("claim_amount_decimal_places")
    @classmethod
    def validate_decimal_places(cls, value: int) -> int:
        if value < 0:
            raise ValueError("claim_amount_decimal_places must not be negative")
        return value

    @field_validator("claim_id_prefix")
    @classmethod
    def validate_claim_id_prefix(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("claim_id_prefix must not be blank")
        return normalized

    @field_validator("initial_claim_status")
    @classmethod
    def validate_initial_status(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("initial_claim_status must not be blank")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object without provider or file I/O."""

    return Settings()
