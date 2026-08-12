"""Load the local Markdown policy into stable section-level chunks."""

from __future__ import annotations

import re
from pathlib import Path

from ..models.policy import PolicyChunk

_SECTION_PATTERN = re.compile(
    r"^##\s+Section\s+(?P<number>\d+)\s*:\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)


class PolicyDocumentError(Exception):
    """Base error for controlled policy loading failures."""

    public_detail = "The policy document could not be loaded."


class PolicyDocumentMissingError(PolicyDocumentError):
    """The configured policy document does not exist."""

    public_detail = "The policy document is unavailable."


class PolicyDocumentMalformedError(PolicyDocumentError):
    """The policy document is empty or has no valid sections."""

    public_detail = "The policy document is invalid."


class PolicyDocumentLoader:
    """Create one typed chunk per `## Section N: Title` heading."""

    def load_file(self, path: str | Path) -> list[PolicyChunk]:
        document_path = Path(path)
        try:
            content = document_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise PolicyDocumentMissingError from exc
        except OSError as exc:
            raise PolicyDocumentMalformedError from exc
        return self.load_text(content, source_file=document_path.name)

    def load_text(self, content: str, *, source_file: str = "sample_policy.md") -> list[PolicyChunk]:
        if not isinstance(content, str) or not content.strip():
            raise PolicyDocumentMalformedError

        matches = list(_SECTION_PATTERN.finditer(content))
        if not matches:
            raise PolicyDocumentMalformedError

        safe_source_file = Path(source_file).name
        if not safe_source_file or safe_source_file in {".", ".."}:
            raise PolicyDocumentMalformedError

        chunks: list[PolicyChunk] = []
        for index, match in enumerate(matches):
            section_number = int(match.group("number"))
            section_title = match.group("title").strip()
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            section_text = content[start:end].strip()
            heading_line = match.group(0).strip()
            body = section_text[len(heading_line) :].strip()
            if not section_title or not body:
                raise PolicyDocumentMalformedError

            chunks.append(
                PolicyChunk(
                    section_id=f"section-{section_number}",
                    section_title=section_title,
                    text=section_text,
                    source_file=safe_source_file,
                    citation=(
                        f"{safe_source_file} — Section {section_number}: "
                        f"{section_title}"
                    ),
                )
            )

        if not chunks:
            raise PolicyDocumentMalformedError
        return chunks
