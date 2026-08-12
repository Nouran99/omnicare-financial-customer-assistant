"""Typed policy evidence models with trusted citation metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import get_settings


def _trimmed(value: str, *, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


class PolicyChunk(BaseModel):
    """One section-level unit of policy evidence."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(...)
    section_title: str = Field(...)
    text: str = Field(...)
    source_file: str = Field(...)
    citation: str = Field(...)

    @field_validator("section_id")
    @classmethod
    def validate_section_id(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="section_id",
            max_length=get_settings().policy_section_id_max_length,
        )

    @field_validator("section_title")
    @classmethod
    def validate_section_title(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="section_title",
            max_length=get_settings().policy_section_title_max_length,
        )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="text",
            max_length=get_settings().policy_chunk_text_max_length,
        )

    @field_validator("source_file")
    @classmethod
    def validate_source_file(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="source_file",
            max_length=get_settings().policy_source_file_max_length,
        )

    @field_validator("citation")
    @classmethod
    def validate_citation(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="citation",
            max_length=get_settings().policy_citation_max_length,
        )
