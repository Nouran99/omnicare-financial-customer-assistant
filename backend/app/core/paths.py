"""Runtime path resolution for configuration-driven local data and storage paths."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root from this module's stable package location."""

    return Path(__file__).resolve().parents[3]


def resolve_configured_path(
    configured_path: str | Path,
    *,
    base_dir: Path | None = None,
    root_dir: Path | None = None,
) -> Path:
    """Resolve a configured path consistently across local and container cwd values.

    Absolute paths remain authoritative. Relative paths first honor the current
    runtime directory, then the repository root. A leading ``..`` configuration
    is also interpreted relative to the repository root so the existing
    ``../data`` and ``../runtime`` local defaults work when commands run from
    the repository root while remaining compatible with a backend working
    directory in Compose.
    """

    raw_path = Path(configured_path).expanduser()
    if raw_path.is_absolute():
        return raw_path

    runtime_base = base_dir or Path.cwd()
    repository_root = root_dir or project_root()
    candidates: list[Path] = [runtime_base / raw_path]
    if raw_path.parts and raw_path.parts[0] == "..":
        candidates.insert(0, repository_root.joinpath(*raw_path.parts[1:]))
    candidates.append(repository_root / raw_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    for candidate in candidates:
        if candidate.parent.exists():
            return candidate
    return candidates[0]
