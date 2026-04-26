"""publish.py - Draft-to-post publishing pipeline for Jekyll/Chirpy blog."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class PublishError(Exception):
    """Base class for all publish pipeline errors. Always exits with non-zero code."""

    exit_code: int = 1

    def __init__(self, message: str, *, suggestion: str | None = None) -> None:
        self._message = message
        self._suggestion = suggestion
        super().__init__(message)

    def __str__(self) -> str:
        if self._suggestion:
            return f"{self._message}\n  suggestion: {self._suggestion}"
        return self._message


class DraftNotFoundError(PublishError):
    pass


class DraftHasFrontMatterError(PublishError):
    pass


class InvalidSlugError(PublishError):
    pass


class TargetPostExistsError(PublishError):
    pass


class ImageSourceMissingError(PublishError):
    pass


class ImageNameConflictError(PublishError):
    pass


class ConfigParseError(PublishError):
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PublishConfig:
    """Strongly-typed mirror of _data/publish.yml with safe defaults for missing keys."""

    default_categories: list[str]
    default_tags: list[str]
    default_image_path: str
    default_description: str
    desc_max_length: int
    desc_strip_markdown: bool
    images_posts_dir: Path
    images_url_prefix: str
    posts_dir: Path
    slug_pattern: str
    fail_on_existing_post: bool

    @classmethod
    def from_yaml(cls, path: Path) -> "PublishConfig":
        """Load config from a YAML file at *path*.

        Raises ConfigParseError if the file is missing or YAML is malformed.
        Missing keys fall back to safe defaults without raising.
        """
        if not path.exists():
            raise ConfigParseError(
                f"config not found: {path}",
                suggestion=f"create the file at {path} or check the path",
            )

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigParseError(
                f"yaml parse error in {path}: {exc}",
                suggestion="check the file for indentation or syntax errors (line numbers above)",
            ) from exc

        # Normalise None (empty file) to an empty dict
        if raw is None:
            raw = {}

        defaults = raw.get("defaults") or {}
        description_cfg = raw.get("description") or {}
        images_cfg = raw.get("images") or {}
        validation_cfg = raw.get("validation") or {}

        # Nested image key inside defaults: { image: { path: "..." } }
        image_block = defaults.get("image") or {}

        return cls(
            default_categories=list(defaults.get("categories") or []),
            default_tags=list(defaults.get("tags") or []),
            default_image_path=image_block.get("path", "/assets/img/default.jpg"),
            default_description=defaults.get("description", ""),
            desc_max_length=int(description_cfg.get("max_length", 160)),
            desc_strip_markdown=bool(description_cfg.get("strip_markdown", True)),
            images_posts_dir=Path(images_cfg.get("posts_dir", "assets/img/posts")),
            images_url_prefix=str(images_cfg.get("url_prefix", "/assets/img/posts")),
            posts_dir=Path(raw.get("posts_dir", "_posts")),
            slug_pattern=str(
                validation_cfg.get("slug_pattern", "^[a-z0-9][a-z0-9-]*$")
            ),
            fail_on_existing_post=bool(
                validation_cfg.get("fail_on_existing_post", True)
            ),
        )


# ---------------------------------------------------------------------------
# Module entry point stub (replaced in later steps)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit("publish.py: not yet implemented (Step 1)")
