"""publish.py - Draft-to-post publishing pipeline for Jekyll/Chirpy blog."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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

        images_posts_dir = Path(images_cfg.get("posts_dir", "assets/img/posts"))
        if images_posts_dir.is_absolute():
            raise ConfigParseError(
                f"images.posts_dir must be relative to repo root, got absolute path: {images_posts_dir}",
                suggestion="use a relative path such as 'assets/img/posts'",
            )

        return cls(
            default_categories=list(defaults.get("categories") or []),
            default_tags=list(defaults.get("tags") or []),
            default_image_path=image_block.get("path", "/assets/img/default.jpg"),
            default_description=defaults.get("description", ""),
            desc_max_length=int(description_cfg.get("max_length", 160)),
            desc_strip_markdown=bool(description_cfg.get("strip_markdown", True)),
            images_posts_dir=images_posts_dir,
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
# ImageMove
# ---------------------------------------------------------------------------


@dataclass
class ImageMove:
    """Single image copy instruction produced by process_images."""

    source: Path        # absolute path to the draft-side source file
    target: Path        # destination: assets/img/posts/<slug>/<basename>
    new_url: str        # rewritten URL: /assets/img/posts/<slug>/<basename>
    skip_copy: bool = False  # True when target already exists with identical content


# ---------------------------------------------------------------------------
# PublishContext
# ---------------------------------------------------------------------------

# Slug validation pattern used at CLI parse time (Step 7 can make this config-driven).
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Date formats accepted by --date
_DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]


@dataclass
class PublishContext:
    """Pipeline-wide data carrier. Populated incrementally by each pipeline step."""

    # CLI inputs
    draft_file: Path                        # absolute path; existence not checked here
    slug: str
    src_dir: Path
    cli_categories: Optional[list[str]]     # None = use default; [] = force empty
    cli_tags: Optional[list[str]]
    cli_image: Optional[str]
    cli_description: Optional[str]
    cli_date: Optional[datetime]
    dry_run: bool
    force: bool
    verbose: bool

    # Config (populated by load_config in a later step)
    config: Optional["PublishConfig"] = None

    # Computed results (filled by subsequent pipeline steps)
    title: str = ""
    description: str = ""
    publish_date: datetime = field(
        default_factory=lambda: datetime.now().astimezone()
    )
    image_plan: list = field(default_factory=list)   # list[ImageMove] in later step
    rewritten_body: str = ""
    front_matter: dict = field(default_factory=dict)
    target_post_path: Path = field(default_factory=Path)
    raw_body: str = ""                               # populated by load_draft


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def parse_list(s: str) -> list[str]:
    """Parse a comma-separated string into a list. Empty string returns []."""
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_date(s: str) -> datetime:
    """Parse a date string in one of the accepted formats and attach local timezone."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).astimezone()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"invalid date '{s}'; expected YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS"
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="publish.py",
        description="Publish a draft Markdown file as a Jekyll/Chirpy post.",
    )
    p.add_argument("--file", metavar="FILE",
                   help="Draft filename (with or without .md extension)")
    p.add_argument("--slug", metavar="SLUG",
                   help="URL slug for the published post")
    p.add_argument("--categories", metavar="CATEGORIES", default=None,
                   help="Comma-separated categories; empty string forces empty list")
    p.add_argument("--tags", metavar="TAGS", default=None,
                   help="Comma-separated tags; empty string forces empty list")
    p.add_argument("--image", metavar="IMAGE", default=None,
                   help="Cover image path; empty string forces no image")
    p.add_argument("--description", metavar="DESCRIPTION", default=None,
                   help="Post description; empty string forces no auto-extraction")
    p.add_argument("--date", metavar="DATE", default=None, type=_parse_date,
                   help="Publish date (YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS)")
    p.add_argument("--src", metavar="SRC", default="_drafts",
                   help="Source drafts directory (default: _drafts)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print planned actions without writing any files")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing post without prompting")
    p.add_argument("--verbose", action="store_true",
                   help="Enable verbose logging")
    p.add_argument("--list", action="store_true",
                   help="List all drafts in the source directory and exit")
    return p


def list_drafts(src_dir: Path) -> None:
    """Print all .md files in src_dir to stdout, sorted alphabetically."""
    files = sorted(
        p.name
        for p in src_dir.iterdir()
        if p.suffix == ".md" and p.name != ".gitkeep"
    )
    for name in files:
        print(name)


def parse_args(argv: list[str]) -> Optional["PublishContext"]:
    """Parse CLI arguments and return a PublishContext.

    Returns None if --list mode was handled (caller should return 0).
    Raises InvalidSlugError for invalid slug patterns.
    Raises SystemExit(2) for missing required arguments (argparse default behavior).
    """
    parser = _build_argument_parser()
    ns = parser.parse_args(argv)

    # Resolve src_dir to absolute path relative to cwd
    src_dir = Path(ns.src).resolve()

    # --list mode: print drafts and return None to signal early exit
    if ns.list:
        list_drafts(src_dir)
        return None

    # Validate required args manually (so --list does not require --file/--slug)
    missing = []
    if ns.file is None:
        missing.append("--file")
    if ns.slug is None:
        missing.append("--slug")
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")

    # Validate slug pattern
    if not _SLUG_PATTERN.match(ns.slug):
        raise InvalidSlugError(
            f"invalid slug '{ns.slug}' (pattern: {_SLUG_PATTERN.pattern})",
            suggestion="use lowercase letters, digits, and dashes only",
        )

    # Resolve draft_file
    raw_file = ns.file
    if not raw_file.endswith(".md"):
        raw_file = raw_file + ".md"
    file_path = Path(raw_file)
    if file_path.is_absolute():
        draft_file = file_path
    else:
        draft_file = (src_dir / file_path).resolve()

    # Parse list-type args: None when not provided, list when provided (even if empty)
    def _parse_list_arg(val: Optional[str]) -> Optional[list[str]]:
        if val is None:
            return None
        return parse_list(val)

    return PublishContext(
        draft_file=draft_file,
        slug=ns.slug,
        src_dir=src_dir,
        cli_categories=_parse_list_arg(ns.categories),
        cli_tags=_parse_list_arg(ns.tags),
        cli_image=ns.image,
        cli_description=ns.description,
        cli_date=ns.date,
        dry_run=ns.dry_run,
        force=ns.force,
        verbose=ns.verbose,
    )


# ---------------------------------------------------------------------------
# Pipeline steps: draft loading and title resolution
# ---------------------------------------------------------------------------


def load_draft(ctx: "PublishContext") -> None:
    """Read the draft file into ctx.raw_body and validate the zero-front-matter contract.

    Raises DraftNotFoundError if the file does not exist, listing available drafts.
    Raises DraftHasFrontMatterError if the file begins with a YAML front matter block.
    """
    if not ctx.draft_file.exists():
        # Build the list of available .md files in src_dir
        available = sorted(
            p.name
            for p in ctx.src_dir.iterdir()
            if p.suffix == ".md" and p.name != ".gitkeep"
        ) if ctx.src_dir.exists() else []

        if available:
            listing = "\n".join(available)
            suggestion = f"available drafts in {ctx.src_dir}:\n{listing}"
        else:
            suggestion = f"_drafts/ is empty; add a draft file to {ctx.src_dir} first"

        raise DraftNotFoundError(
            f"draft not found: {ctx.draft_file}",
            suggestion=suggestion,
        )

    raw = ctx.draft_file.read_text(encoding="utf-8")

    # Check for front matter: skip BOM, skip leading blank lines, check first non-empty line
    text = raw.lstrip("﻿")  # strip UTF-8 BOM if present
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            continue
        if stripped == "---":
            raise DraftHasFrontMatterError(
                "draft must not contain front matter",
                suggestion=(
                    "remove the `---` block; meta is generated by the publisher"
                ),
            )
        # First non-empty line is not ---, no front matter present
        break

    ctx.raw_body = raw


def resolve_title(ctx: "PublishContext") -> None:
    """Set ctx.title to the stem of ctx.draft_file (filename without the .md extension).

    Preserves Chinese characters, spaces, and mixed punctuation as-is.
    """
    ctx.title = ctx.draft_file.stem


# ---------------------------------------------------------------------------
# Pipeline steps: description extraction
# ---------------------------------------------------------------------------


def strip_markdown_inline(s: str) -> str:
    """Remove inline markdown marks from *s*, preserving the visible text.

    Handles: [text](url) links, `code`, **bold**, *italic*, ***both***,
    __bold__, _italic_.  Applied in order: links first, then code spans,
    then asterisk sequences (longest first), then underscore sequences.
    """
    # Links: [text](url); URL allows one level of nested parentheses
    s = re.sub(r"\[([^\]]+)\]\([^()]*(?:\([^()]*\)[^()]*)*\)", r"\1", s)
    # Inline code: `code` -> code
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Asterisk emphasis: triple, then double, then single (longest first).
    # Double-star pattern uses (.+?) to allow a single * inside **text**.
    s = re.sub(r"\*\*\*([^*]+)\*\*\*", r"\1", s)
    s = re.sub(r"\*\*(?!\*)(.+?)(?<!\*)\*\*(?!\*)", r"\1", s)
    s = re.sub(r"\*([^*]+)\*",         r"\1", s)
    # Underscore emphasis: only when surrounded by non-word chars
    s = re.sub(r"(?<!\w)_{1,2}([^_]+)_{1,2}(?!\w)", r"\1", s)
    return s.strip()


def extract_description(ctx: "PublishContext") -> None:
    """Fill ctx.description according to PRD 3.4 priority rules.

    Priority order:
    1. CLI explicit value (ctx.cli_description is not None) -- used verbatim,
       empty string is treated as force-clear (no extraction).
    2. Config default (ctx.config.default_description != "") -- used as-is.
    3. Auto-extract from ctx.raw_body:
       - Skip leading blank lines.
       - If first non-empty line starts with '# ', skip it (H1 title).
       - Skip blank lines after H1.
       - Collect the first consecutive non-empty paragraph, join with spaces.
       - Strip inline markdown if ctx.config.desc_strip_markdown is True.
       - Truncate to ctx.config.desc_max_length characters and rstrip.
    4. If no extractable content found, set "" and emit a stderr warning.
    """
    # Priority 1: CLI explicit value (includes empty string as force-clear)
    if ctx.cli_description is not None:
        ctx.description = ctx.cli_description
        return

    # Priority 2: non-empty config default
    if ctx.config.default_description != "":
        ctx.description = ctx.config.default_description
        return

    # Priority 3: auto-extract from raw body
    lines = ctx.raw_body.splitlines()
    idx = 0
    total = len(lines)

    # Skip leading blank lines
    while idx < total and lines[idx].strip() == "":
        idx += 1

    # Skip H1 line if present
    if idx < total and lines[idx].startswith("# "):
        idx += 1

    # Skip blank lines after H1
    while idx < total and lines[idx].strip() == "":
        idx += 1

    # Collect first consecutive non-empty paragraph
    para_lines: list[str] = []
    while idx < total and lines[idx].strip() != "":
        para_lines.append(lines[idx].strip())
        idx += 1

    if not para_lines:
        # Priority 4: no extractable content
        ctx.description = ""
        print("warning: draft has no extractable description", file=sys.stderr)
        return

    text = " ".join(para_lines)

    # Optionally strip inline markdown
    if ctx.config.desc_strip_markdown:
        text = strip_markdown_inline(text)

    # Truncate to max_length and remove trailing whitespace
    max_len = ctx.config.desc_max_length
    if len(text) > max_len:
        text = text[:max_len].rstrip()

    ctx.description = text


# ---------------------------------------------------------------------------
# Image processing helpers
# ---------------------------------------------------------------------------

# Matches markdown image syntax: ![alt](path) or ![alt](path "title")
# path uses [^)\s]+ to exclude whitespace and closing paren (no nested parens supported)
MD_IMG = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)

# Matches HTML <img src="path"> with optional other attributes; case-insensitive
HTML_IMG = re.compile(
    r'<img\s+[^>]*?src=(["\'])(?P<path>[^"\']+)\1[^>]*>',
    re.IGNORECASE,
)


def classify_path(p: str) -> str:
    """Classify an image path as 'remote', 'absolute', or 'relative'.

    remote   -> starts with http:// or https://
    absolute -> starts with / or ~
    relative -> everything else
    """
    if re.match(r"^https?://", p):
        return "remote"
    if p.startswith("/") or p.startswith("~"):
        return "absolute"
    return "relative"


def hashes_equal(a: Path, b: Path, chunk: int = 65536) -> bool:
    """Return True if files *a* and *b* have the same SHA-1 digest.

    Reads both files in streaming chunks to avoid loading large images into memory.
    """
    def _sha1(p: Path) -> str:
        m = hashlib.sha1()
        with p.open("rb") as f:
            for blk in iter(lambda: f.read(chunk), b""):
                m.update(blk)
        return m.hexdigest()

    return _sha1(a) == _sha1(b)


def process_images(ctx: "PublishContext") -> None:
    """Scan ctx.raw_body for image references, build ctx.image_plan, rewrite ctx.rewritten_body.

    Processing rules:
    - remote URLs (http/https): left untouched, not added to image_plan
    - relative paths: left untouched, not added to image_plan
    - absolute paths (/ or ~): expanded, resolved, added to image_plan, link rewritten

    Raises ImageSourceMissingError if any absolute-path source does not exist on disk.
    Raises ImageNameConflictError if a target already exists with different content.

    Does NOT copy files -- copying is handled in commit_filesystem (Step 7).
    """
    config = ctx.config
    repo_root = ctx.src_dir.parent

    # Collect all matches from both syntaxes
    all_matches: list[tuple[re.Match, str]] = []
    for m in MD_IMG.finditer(ctx.raw_body):
        all_matches.append((m, "md"))
    for m in HTML_IMG.finditer(ctx.raw_body):
        all_matches.append((m, "html"))

    # First pass: resolve all absolute paths, check existence, detect conflicts
    # seen_source maps resolved source Path -> ImageMove (for dedup)
    seen_source: dict[Path, ImageMove] = {}
    missing: list[str] = []

    for m, syntax in all_matches:
        raw_path = m.group("path")
        kind = classify_path(raw_path)

        if kind != "absolute":
            continue

        # Expand ~ and resolve to absolute path
        expanded = os.path.expanduser(raw_path)
        source = Path(expanded).resolve()

        if source in seen_source:
            # Already processed this source; skip duplicate resolution
            continue

        if not source.exists():
            missing.append(raw_path)
            continue

        basename = source.name
        target = repo_root / config.images_posts_dir / ctx.slug / basename
        new_url = f"{config.images_url_prefix}/{ctx.slug}/{basename}"

        skip_copy = False
        if target.exists():
            if hashes_equal(source, target):
                skip_copy = True
            else:
                raise ImageNameConflictError(
                    f"image name conflict: source '{source}' vs existing target '{target}' have different content",
                    suggestion=(
                        f"rename the source image or remove '{target}' before publishing"
                    ),
                )

        move = ImageMove(source=source, target=target, new_url=new_url, skip_copy=skip_copy)
        seen_source[source] = move

    if missing:
        paths_str = ", ".join(missing)
        raise ImageSourceMissingError(
            f"image source file(s) not found: {paths_str}",
            suggestion="check that all absolute image paths exist on disk before publishing",
        )

    ctx.image_plan = list(seen_source.values())

    # Build a lookup from resolved source path -> new_url for the rewrite step
    source_to_url: dict[Path, str] = {
        move.source: move.new_url for move in ctx.image_plan
    }

    # Second pass: rewrite body text
    def _rewrite_via_span(m: re.Match, new_url: str) -> str:
        """Replace only the captured 'path' group within the full match string."""
        base = m.start()
        start, end = m.span("path")
        original = m.group(0)
        return original[: start - base] + new_url + original[end - base :]

    def _rewrite_md(m: re.Match) -> str:
        raw_path = m.group("path")
        if classify_path(raw_path) != "absolute":
            return m.group(0)
        source = Path(os.path.expanduser(raw_path)).resolve()
        new_url = source_to_url.get(source)
        if new_url is None:
            return m.group(0)
        return _rewrite_via_span(m, new_url)

    def _rewrite_html(m: re.Match) -> str:
        raw_path = m.group("path")
        if classify_path(raw_path) != "absolute":
            return m.group(0)
        source = Path(os.path.expanduser(raw_path)).resolve()
        new_url = source_to_url.get(source)
        if new_url is None:
            return m.group(0)
        return _rewrite_via_span(m, new_url)

    body = ctx.raw_body
    body = MD_IMG.sub(_rewrite_md, body)
    body = HTML_IMG.sub(_rewrite_html, body)
    ctx.rewritten_body = body


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def run(argv: list[str]) -> int:
    """Script entry point. Catches PublishError and converts to exit code."""
    try:
        ctx = parse_args(argv)
        if ctx is None:
            # --list mode already handled
            return 0
        repo_root = ctx.src_dir.parent
        ctx.config = PublishConfig.from_yaml(repo_root / "_data" / "publish.yml")
        load_draft(ctx)
        resolve_title(ctx)
        extract_description(ctx)
        process_images(ctx)
        # Subsequent pipeline steps added in later steps.
        return 0
    except PublishError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code
    except SystemExit:
        raise  # let argparse --help and error exits propagate normally


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
