"""Tests for publish.py - Step 1: config and error types. Step 2: CLI and context. Step 3: draft loader and title resolver. Step 4: description extractor."""
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest

from publish import (
    ConfigParseError,
    DraftHasFrontMatterError,
    DraftNotFoundError,
    ImageNameConflictError,
    ImageSourceMissingError,
    InvalidSlugError,
    PublishConfig,
    PublishContext,
    PublishError,
    TargetPostExistsError,
    extract_description,
    load_draft,
    parse_args,
    parse_list,
    resolve_title,
    run,
    strip_markdown_inline,
)

# Path to the real config used by the blog
REPO_ROOT = Path(__file__).parent.parent
REAL_CONFIG = REPO_ROOT / "_data" / "publish.yml"


class TestPublishConfigLoadsDefaultYaml:
    """test_config_loads_default_yaml: read real _data/publish.yml and assert field values."""

    def test_loads_successfully(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert isinstance(cfg, PublishConfig)

    def test_default_categories(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.default_categories == ["Notes"]

    def test_default_tags(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.default_tags == ["notes"]

    def test_default_image_path(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.default_image_path == "/assets/img/default.jpg"

    def test_default_description(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.default_description == ""

    def test_desc_max_length(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.desc_max_length == 160

    def test_desc_strip_markdown(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.desc_strip_markdown is True

    def test_images_posts_dir(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.images_posts_dir == Path("assets/img/posts")

    def test_images_url_prefix(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.images_url_prefix == "/assets/img/posts"

    def test_posts_dir(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.posts_dir == Path("_posts")

    def test_slug_pattern(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.slug_pattern == "^[a-z0-9][a-z0-9-]*$"

    def test_fail_on_existing_post(self):
        cfg = PublishConfig.from_yaml(REAL_CONFIG)
        assert cfg.fail_on_existing_post is True


class TestPublishConfigParsesMinimalYaml:
    """test_config_parses_minimal_yaml: minimal yaml with only 'defaults: {}' uses safe defaults."""

    def test_minimal_yaml_no_error(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert isinstance(cfg, PublishConfig)

    def test_minimal_yaml_categories_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.default_categories == []

    def test_minimal_yaml_tags_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.default_tags == []

    def test_minimal_yaml_image_path_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.default_image_path == "/assets/img/default.jpg"

    def test_minimal_yaml_description_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.default_description == ""

    def test_minimal_yaml_desc_max_length_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.desc_max_length == 160

    def test_minimal_yaml_strip_markdown_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.desc_strip_markdown is True

    def test_minimal_yaml_posts_dir_default(self, tmp_path: Path):
        p = tmp_path / "publish.yml"
        p.write_text("defaults: {}\n", encoding="utf-8")
        cfg = PublishConfig.from_yaml(p)
        assert cfg.posts_dir == Path("_posts")


class TestPublishConfigRaisesOnMissingFile:
    """test_config_raises_on_missing_file: non-existent path raises ConfigParseError."""

    def test_raises_config_parse_error(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.yml"
        with pytest.raises(ConfigParseError):
            PublishConfig.from_yaml(missing)

    def test_error_message_contains_path(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.yml"
        with pytest.raises(ConfigParseError) as exc_info:
            PublishConfig.from_yaml(missing)
        assert str(missing) in str(exc_info.value)


class TestPublishConfigRaisesOnYamlSyntaxError:
    """test_config_raises_on_yaml_syntax_error: malformed YAML raises ConfigParseError."""

    def test_raises_config_parse_error(self, tmp_path: Path):
        p = tmp_path / "bad.yml"
        p.write_text("defaults: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigParseError):
            PublishConfig.from_yaml(p)

    def test_error_message_contains_yaml_info(self, tmp_path: Path):
        p = tmp_path / "bad.yml"
        p.write_text("defaults: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigParseError) as exc_info:
            PublishConfig.from_yaml(p)
        # yaml.YAMLError message typically includes line number info
        msg = str(exc_info.value)
        assert "yaml" in msg.lower() or "line" in msg.lower() or "mark" in msg.lower()


class TestPublishErrorIncludesSuggestion:
    """test_publish_error_includes_suggestion: PublishError subclass with suggestion in str()."""

    def test_config_parse_error_suggestion(self):
        e = ConfigParseError("config not found", suggestion="run: ls _data/")
        assert "run: ls _data/" in str(e)

    def test_draft_not_found_error_suggestion(self):
        e = DraftNotFoundError("draft missing", suggestion="check _drafts/")
        assert "check _drafts/" in str(e)

    def test_invalid_slug_error_suggestion(self):
        e = InvalidSlugError("bad slug", suggestion="use ^[a-z0-9][a-z0-9-]*$")
        assert "use ^[a-z0-9][a-z0-9-]*$" in str(e)

    def test_error_without_suggestion(self):
        e = TargetPostExistsError("post exists")
        # no crash when suggestion is absent
        assert "post exists" in str(e)

    def test_all_error_subclasses_are_publish_error(self):
        errors = [
            DraftNotFoundError,
            DraftHasFrontMatterError,
            InvalidSlugError,
            TargetPostExistsError,
            ImageSourceMissingError,
            ImageNameConflictError,
            ConfigParseError,
        ]
        for cls in errors:
            assert issubclass(cls, PublishError)
            assert issubclass(cls, Exception)

    def test_exit_code_attribute(self):
        e = ConfigParseError("err")
        assert e.exit_code == 1


# ---------------------------------------------------------------------------
# Step 2: parse_list
# ---------------------------------------------------------------------------


class TestParseList:
    def test_basic(self):
        assert parse_list("a, b ,c") == ["a", "b", "c"]

    def test_empty_string(self):
        assert parse_list("") == []

    def test_single_item(self):
        assert parse_list("foo") == ["foo"]

    def test_strips_whitespace(self):
        assert parse_list("  x , y  ") == ["x", "y"]

    def test_trailing_comma(self):
        # trailing comma produces no extra empty item
        assert parse_list("a,b,") == ["a", "b"]


# ---------------------------------------------------------------------------
# Step 2: parse_args
# ---------------------------------------------------------------------------


class TestParseArgsBasic:
    """test_parse_args_basic: --file foo --slug bar parses ctx fields correctly."""

    def test_draft_file_resolved(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file == tmp_path / "foo.md"

    def test_slug_set(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.slug == "bar"

    def test_src_dir_set(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.src_dir == tmp_path

    def test_dry_run_default_false(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.dry_run is False

    def test_dry_run_flag(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path), "--dry-run"])
        assert ctx.dry_run is True

    def test_force_default_false(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.force is False

    def test_force_flag(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path), "--force"])
        assert ctx.force is True

    def test_verbose_default_false(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.verbose is False

    def test_config_defaults_to_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.config is None


class TestParseArgsMissingRequiredArgs:
    """test_parse_args_missing_file_or_slug: missing required arg exits with SystemExit(2)."""

    def test_missing_file_raises_system_exit(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--slug", "bar", "--src", str(tmp_path)])
        assert exc_info.value.code == 2

    def test_missing_slug_raises_system_exit(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--file", "foo", "--src", str(tmp_path)])
        assert exc_info.value.code == 2

    def test_missing_both_raises_system_exit(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])
        assert exc_info.value.code == 2


class TestParseArgsSlugValidation:
    """Slug validation raises InvalidSlugError for invalid patterns."""

    def test_slug_invalid_uppercase(self, tmp_path: Path):
        with pytest.raises(InvalidSlugError):
            parse_args(["--file", "foo", "--slug", "Bad", "--src", str(tmp_path)])

    def test_slug_invalid_mixed_case(self, tmp_path: Path):
        with pytest.raises(InvalidSlugError):
            parse_args(["--file", "foo", "--slug", "Bad-Slug", "--src", str(tmp_path)])

    def test_slug_invalid_chinese(self, tmp_path: Path):
        with pytest.raises(InvalidSlugError):
            parse_args(["--file", "foo", "--slug", "中文", "--src", str(tmp_path)])

    def test_slug_invalid_underscore(self, tmp_path: Path):
        with pytest.raises(InvalidSlugError):
            parse_args(["--file", "foo", "--slug", "a_b", "--src", str(tmp_path)])

    def test_slug_invalid_starts_with_dash(self, tmp_path: Path):
        # argparse treats "-abc" as an option flag, so it exits with SystemExit(2)
        # before reaching slug validation. Both InvalidSlugError and SystemExit are
        # acceptable ways to reject a dash-leading slug.
        with pytest.raises((InvalidSlugError, SystemExit)):
            parse_args(["--file", "foo", "--slug", "-abc", "--src", str(tmp_path)])

    def test_slug_valid_lowercase_digits_dashes(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "my-post-01", "--src", str(tmp_path)])
        assert ctx.slug == "my-post-01"

    def test_slug_invalid_contains_suggestion(self, tmp_path: Path):
        with pytest.raises(InvalidSlugError) as exc_info:
            parse_args(["--file", "foo", "--slug", "BadSlug", "--src", str(tmp_path)])
        assert "suggestion" in str(exc_info.value).lower()


class TestParseArgsCategoriesTags:
    """Categories and tags: None when unspecified, [] when explicit empty, list when provided."""

    def test_categories_unspecified_is_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.cli_categories is None

    def test_categories_explicit_empty_is_list(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--categories", ""])
        assert ctx.cli_categories == []

    def test_categories_parsed_as_list(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--categories", "a,b ,c"])
        assert ctx.cli_categories == ["a", "b", "c"]

    def test_tags_unspecified_is_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.cli_tags is None

    def test_tags_explicit_empty_is_list(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--tags", ""])
        assert ctx.cli_tags == []

    def test_tags_parsed_as_list(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--tags", "x,y"])
        assert ctx.cli_tags == ["x", "y"]


class TestParseArgsFileResolution:
    """File path resolution: auto-append .md, relative -> src_dir, absolute -> direct."""

    def test_file_without_md_suffix(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file.name == "foo.md"

    def test_file_with_md_suffix(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo.md", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file.name == "foo.md"

    def test_file_chinese_name(self, tmp_path: Path):
        ctx = parse_args(["--file", "如何设计", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file.name == "如何设计.md"

    def test_file_absolute_path_used_directly(self, tmp_path: Path):
        abs_path = tmp_path / "other" / "draft.md"
        ctx = parse_args(["--file", str(abs_path), "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file == abs_path

    def test_file_in_src_dir(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.draft_file.parent == tmp_path
        assert ctx.draft_file.is_absolute()


class TestParseArgsDateFormats:
    """--date accepts YYYY-MM-DD, YYYY-MM-DD HH:MM, YYYY-MM-DD HH:MM:SS."""

    def test_date_only(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--date", "2026-04-26"])
        assert isinstance(ctx.cli_date, datetime)
        assert ctx.cli_date.tzinfo is not None
        assert ctx.cli_date.year == 2026
        assert ctx.cli_date.month == 4
        assert ctx.cli_date.day == 26

    def test_date_with_time(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--date", "2026-04-26 14:00"])
        assert isinstance(ctx.cli_date, datetime)
        assert ctx.cli_date.hour == 14
        assert ctx.cli_date.minute == 0
        assert ctx.cli_date.tzinfo is not None

    def test_date_with_seconds(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--date", "2026-04-26 14:00:30"])
        assert isinstance(ctx.cli_date, datetime)
        assert ctx.cli_date.second == 30
        assert ctx.cli_date.tzinfo is not None

    def test_date_unspecified_is_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.cli_date is None


class TestParseArgsImageDescription:
    """--image and --description: None when unspecified, str (possibly empty) when provided."""

    def test_image_unspecified_is_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.cli_image is None

    def test_image_explicit_empty(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--image", ""])
        assert ctx.cli_image == ""

    def test_image_value(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--image", "/assets/img/cover.jpg"])
        assert ctx.cli_image == "/assets/img/cover.jpg"

    def test_description_unspecified_is_none(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path)])
        assert ctx.cli_description is None

    def test_description_explicit_empty(self, tmp_path: Path):
        ctx = parse_args(["--file", "foo", "--slug", "bar", "--src", str(tmp_path),
                          "--description", ""])
        assert ctx.cli_description == ""


# ---------------------------------------------------------------------------
# Step 2: list_drafts and --list mode via run()
# ---------------------------------------------------------------------------


class TestRunListMode:
    """test_run_list_mode: --list prints .md filenames sorted, excludes .gitkeep."""

    def test_run_list_exits_zero(self, tmp_path: Path):
        tmp_drafts = tmp_path / "_drafts"
        tmp_drafts.mkdir()
        (tmp_drafts / "a.md").write_text("content", encoding="utf-8")
        ret = run(["--list", "--src", str(tmp_drafts)])
        assert ret == 0

    def test_run_list_prints_md_files(self, tmp_path: Path, capsys):
        tmp_drafts = tmp_path / "_drafts"
        tmp_drafts.mkdir()
        (tmp_drafts / "a.md").write_text("content", encoding="utf-8")
        (tmp_drafts / "中文.md").write_text("内容", encoding="utf-8")
        (tmp_drafts / ".gitkeep").write_text("", encoding="utf-8")
        run(["--list", "--src", str(tmp_drafts)])
        captured = capsys.readouterr()
        assert "a.md" in captured.out
        assert "中文.md" in captured.out
        assert ".gitkeep" not in captured.out

    def test_run_list_sorted(self, tmp_path: Path, capsys):
        tmp_drafts = tmp_path / "_drafts"
        tmp_drafts.mkdir()
        (tmp_drafts / "z.md").write_text("z", encoding="utf-8")
        (tmp_drafts / "a.md").write_text("a", encoding="utf-8")
        run(["--list", "--src", str(tmp_drafts)])
        captured = capsys.readouterr()
        lines = [l for l in captured.out.splitlines() if l.strip()]
        assert lines == sorted(lines)


class TestRunPropagatesPublishError:
    """test_run_propagates_publish_error: PublishError causes run() to return non-zero."""

    def test_invalid_slug_returns_nonzero(self, tmp_path: Path):
        ret = run(["--file", "foo", "--slug", "BadSlug", "--src", str(tmp_path)])
        assert ret != 0

    def test_invalid_slug_stderr_message(self, tmp_path: Path, capsys):
        run(["--file", "foo", "--slug", "BadSlug", "--src", str(tmp_path)])
        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or "BadSlug" in captured.err or "slug" in captured.err.lower()

    def test_publish_error_exit_code(self, tmp_path: Path, monkeypatch):
        from publish import InvalidSlugError

        def fake_parse_args(argv):
            raise InvalidSlugError("bad slug", suggestion="use lowercase")

        monkeypatch.setattr("publish.parse_args", fake_parse_args)
        ret = run(["--file", "foo", "--slug", "ok", "--src", str(tmp_path)])
        assert ret == 1


# ---------------------------------------------------------------------------
# Step 3: load_draft
# ---------------------------------------------------------------------------


def _make_ctx(src_dir: Path, filename: str = "post.md") -> PublishContext:
    """Build a minimal PublishContext pointing at src_dir/filename."""
    return PublishContext(
        draft_file=src_dir / filename,
        slug="my-post",
        src_dir=src_dir,
        cli_categories=None,
        cli_tags=None,
        cli_image=None,
        cli_description=None,
        cli_date=None,
        dry_run=False,
        force=False,
        verbose=False,
    )


class TestLoadDraftMissingFile:
    """load_draft raises DraftNotFoundError when draft file does not exist."""

    def test_load_draft_missing_file_raises(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "missing.md")
        with pytest.raises(DraftNotFoundError):
            load_draft(ctx)

    def test_load_draft_missing_file_error_message_contains_path(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "missing.md")
        with pytest.raises(DraftNotFoundError) as exc_info:
            load_draft(ctx)
        assert "missing.md" in str(exc_info.value)

    def test_load_draft_missing_file_lists_real_drafts(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        (src_dir / "a.md").write_text("content a", encoding="utf-8")
        (src_dir / "b.md").write_text("content b", encoding="utf-8")
        ctx = _make_ctx(src_dir, "missing.md")
        with pytest.raises(DraftNotFoundError) as exc_info:
            load_draft(ctx)
        msg = str(exc_info.value)
        assert "a.md" in msg
        assert "b.md" in msg

    def test_load_draft_empty_drafts_dir(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        (src_dir / ".gitkeep").write_text("", encoding="utf-8")
        ctx = _make_ctx(src_dir, "missing.md")
        with pytest.raises(DraftNotFoundError) as exc_info:
            load_draft(ctx)
        msg = str(exc_info.value)
        assert "empty" in msg.lower()


class TestLoadDraftFrontMatterRejection:
    """load_draft raises DraftHasFrontMatterError when draft starts with --- (front matter)."""

    def test_load_draft_rejects_front_matter_first_line(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        draft = src_dir / "post.md"
        draft.write_text("---\ntitle: Hello\n---\n\nBody text.", encoding="utf-8")
        ctx = _make_ctx(src_dir)
        with pytest.raises(DraftHasFrontMatterError):
            load_draft(ctx)

    def test_load_draft_rejects_front_matter_after_blank_lines(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        draft = src_dir / "post.md"
        draft.write_text("\n\n\n---\ntitle: Hello\n---\n\nBody text.", encoding="utf-8")
        ctx = _make_ctx(src_dir)
        with pytest.raises(DraftHasFrontMatterError):
            load_draft(ctx)

    def test_load_draft_rejects_front_matter_with_bom(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        draft = src_dir / "post.md"
        # Write UTF-8 BOM followed by front matter
        draft.write_bytes(b"\xef\xbb\xbf---\ntitle: Hello\n---\n\nBody text.")
        ctx = _make_ctx(src_dir)
        with pytest.raises(DraftHasFrontMatterError):
            load_draft(ctx)

    def test_load_draft_accepts_horizontal_rule_in_body(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        draft = src_dir / "post.md"
        draft.write_text(
            "# Title\n\nSome text.\n\n---\n\nMore text after HR.",
            encoding="utf-8",
        )
        ctx = _make_ctx(src_dir)
        load_draft(ctx)  # must not raise
        assert "---" in ctx.raw_body

    def test_load_draft_error_message_mentions_front_matter(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        draft = src_dir / "post.md"
        draft.write_text("---\ntitle: Hello\n---\n\nBody.", encoding="utf-8")
        ctx = _make_ctx(src_dir)
        with pytest.raises(DraftHasFrontMatterError) as exc_info:
            load_draft(ctx)
        msg = str(exc_info.value)
        assert "front matter" in msg.lower()


class TestLoadDraftReadsBody:
    """load_draft reads the file content into ctx.raw_body."""

    def test_load_draft_reads_chinese_body(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        chinese_content = "# 如何设计\n\n这是正文内容，包含中文字符。"
        draft = src_dir / "如何设计.md"
        draft.write_text(chinese_content, encoding="utf-8")
        ctx = _make_ctx(src_dir, "如何设计.md")
        load_draft(ctx)
        assert ctx.raw_body == chinese_content

    def test_load_draft_reads_ascii_body(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        content = "# Hello\n\nThis is the body."
        (src_dir / "post.md").write_text(content, encoding="utf-8")
        ctx = _make_ctx(src_dir)
        load_draft(ctx)
        assert ctx.raw_body == content


# ---------------------------------------------------------------------------
# Step 3: resolve_title
# ---------------------------------------------------------------------------


class TestResolveTitle:
    """resolve_title sets ctx.title to the stem of draft_file."""

    def test_resolve_title_basic(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "foo.md")
        resolve_title(ctx)
        assert ctx.title == "foo"

    def test_resolve_title_chinese_filename(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "如何设计.md")
        resolve_title(ctx)
        assert ctx.title == "如何设计"

    def test_resolve_title_with_spaces(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "Hello World.md")
        resolve_title(ctx)
        assert ctx.title == "Hello World"

    def test_resolve_title_strips_md_only(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "foo.bar.md")
        resolve_title(ctx)
        assert ctx.title == "foo.bar"

    def test_resolve_title_full_chinese_filename(self, tmp_path: Path):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        ctx = _make_ctx(src_dir, "如何设计一个好的Skill.md")
        resolve_title(ctx)
        assert ctx.title == "如何设计一个好的Skill"


# ---------------------------------------------------------------------------
# Step 3: run() integration with load_draft
# ---------------------------------------------------------------------------


class TestRunPropagatesDraftNotFound:
    """run() returns non-zero exit code when draft file is not found."""

    def test_run_propagates_draft_not_found(self, tmp_path: Path, capsys, monkeypatch):
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        # Set up a valid publish.yml so config loading succeeds
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        (data_dir / "publish.yml").write_text("defaults: {}\n", encoding="utf-8")

        from publish import PublishContext

        def fake_parse_args(argv):
            return PublishContext(
                draft_file=src_dir / "nonexistent.md",
                slug="my-post",
                src_dir=src_dir,
                cli_categories=None,
                cli_tags=None,
                cli_image=None,
                cli_description=None,
                cli_date=None,
                dry_run=False,
                force=False,
                verbose=False,
            )

        monkeypatch.setattr("publish.parse_args", fake_parse_args)

        # Also patch config loading to use our tmp publish.yml
        original_from_yaml = PublishConfig.from_yaml

        def fake_from_yaml(path):
            return original_from_yaml(data_dir / "publish.yml")

        monkeypatch.setattr("publish.PublishConfig.from_yaml", fake_from_yaml)

        ret = run(["--file", "nonexistent", "--slug", "my-post", "--src", str(src_dir)])
        assert ret == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or "nonexistent" in captured.err


# ---------------------------------------------------------------------------
# Step 4 helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    default_description: str = "",
    desc_max_length: int = 160,
    desc_strip_markdown: bool = True,
) -> PublishConfig:
    """Build a minimal PublishConfig for description tests."""
    return PublishConfig(
        default_categories=[],
        default_tags=[],
        default_image_path="/assets/img/default.jpg",
        default_description=default_description,
        desc_max_length=desc_max_length,
        desc_strip_markdown=desc_strip_markdown,
        images_posts_dir=Path("assets/img/posts"),
        images_url_prefix="/assets/img/posts",
        posts_dir=Path("_posts"),
        slug_pattern="^[a-z0-9][a-z0-9-]*$",
        fail_on_existing_post=True,
    )


def _make_ctx_with_body(
    src_dir: Path,
    body: str,
    *,
    cli_description: "str | None" = None,
    config: "PublishConfig | None" = None,
    filename: str = "post.md",
) -> PublishContext:
    """Build a PublishContext with raw_body and config already set."""
    ctx = PublishContext(
        draft_file=src_dir / filename,
        slug="my-post",
        src_dir=src_dir,
        cli_categories=None,
        cli_tags=None,
        cli_image=None,
        cli_description=cli_description,
        cli_date=None,
        dry_run=False,
        force=False,
        verbose=False,
    )
    ctx.raw_body = body
    ctx.config = config if config is not None else _make_config()
    return ctx


# ---------------------------------------------------------------------------
# Step 4: strip_markdown_inline
# ---------------------------------------------------------------------------


class TestStripMarkdownInlineLink:
    def test_link_replaced_with_anchor_text(self):
        assert strip_markdown_inline("[anchor](https://x)") == "anchor"

    def test_link_in_sentence(self):
        result = strip_markdown_inline("visit [home](https://example.com) today")
        assert result == "visit home today"

    def test_multiple_links(self):
        result = strip_markdown_inline("[a](u1) and [b](u2)")
        assert result == "a and b"


class TestStripMarkdownInlineCode:
    def test_inline_code_replaced_with_content(self):
        assert strip_markdown_inline("`code`") == "code"

    def test_inline_code_in_sentence(self):
        result = strip_markdown_inline("use `print()` here")
        assert result == "use print() here"


class TestStripMarkdownInlineBold:
    def test_double_asterisk_bold(self):
        assert strip_markdown_inline("**bold**") == "bold"

    def test_triple_asterisk(self):
        assert strip_markdown_inline("***triple***") == "triple"

    def test_bold_in_sentence(self):
        result = strip_markdown_inline("this is **important** text")
        assert result == "this is important text"


class TestStripMarkdownInlineItalic:
    def test_single_asterisk_italic(self):
        assert strip_markdown_inline("*italic*") == "italic"

    def test_single_underscore_italic(self):
        assert strip_markdown_inline("_underscore_") == "underscore"

    def test_double_underscore_bold(self):
        assert strip_markdown_inline("__bold__") == "bold"


class TestStripMarkdownInlineCombined:
    def test_link_and_bold_and_code(self):
        src = "[**link**](https://x) and `code` here"
        # link is stripped first, then bold, then code
        result = strip_markdown_inline(src)
        assert "https://x" not in result
        assert "`" not in result
        assert "**" not in result
        assert "link" in result
        assert "code" in result

    def test_mixed_in_paragraph(self):
        src = "Read [docs](https://docs.example.com) or `help()` for **more** info."
        result = strip_markdown_inline(src)
        assert result == "Read docs or help() for more info."


class TestStripMarkdownInlineNoMarks:
    def test_plain_text_unchanged(self):
        assert strip_markdown_inline("plain text here") == "plain text here"

    def test_chinese_plain_text(self):
        assert strip_markdown_inline("这是一段纯文本") == "这是一段纯文本"

    def test_empty_string(self):
        assert strip_markdown_inline("") == ""


# ---------------------------------------------------------------------------
# Step 4: extract_description
# ---------------------------------------------------------------------------


class TestExtractDescriptionSkipH1:
    """Verifies H1 line is skipped; first paragraph after blank lines is used."""

    def test_extracts_paragraph_after_h1(self, tmp_path: Path):
        body = "# 标题\n\n这是首段"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "这是首段"

    def test_h1_with_extra_blank_lines(self, tmp_path: Path):
        body = "# Title\n\n\n\nFirst para"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "First para"


class TestExtractDescriptionNoH1:
    """No H1 -> extracts from first non-empty line directly."""

    def test_extracts_first_paragraph(self, tmp_path: Path):
        body = "这是首段"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "这是首段"

    def test_non_h1_heading_treated_as_paragraph(self, tmp_path: Path):
        body = "## Subheading\n\nrest"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        # ## line is not H1, so it is treated as first paragraph line
        assert "Subheading" in ctx.description


class TestExtractDescriptionSkipsLeadingBlankLines:
    """Leading blank lines before any content are skipped."""

    def test_three_blank_lines_then_paragraph(self, tmp_path: Path):
        body = "\n\n\nFirst paragraph text"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "First paragraph text"

    def test_blank_lines_before_h1_then_paragraph(self, tmp_path: Path):
        body = "\n\n# Title\n\nThe body paragraph"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "The body paragraph"


class TestExtractDescriptionMultipleLinesJoined:
    """Consecutive non-empty lines in paragraph are joined with a space."""

    def test_two_lines_joined(self, tmp_path: Path):
        body = "# H\n\nLine one\nLine two"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "Line one Line two"

    def test_three_lines_joined(self, tmp_path: Path):
        body = "First\nSecond\nThird"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert ctx.description == "First Second Third"


class TestExtractDescriptionTruncatesToMaxLength:
    """Paragraph longer than desc_max_length is truncated and rstripped."""

    def test_truncates_ascii(self, tmp_path: Path):
        long_text = "a" * 200
        ctx = _make_ctx_with_body(
            tmp_path, long_text, config=_make_config(desc_max_length=50, desc_strip_markdown=False)
        )
        extract_description(ctx)
        assert len(ctx.description) <= 50

    def test_rstrip_after_truncation(self, tmp_path: Path):
        # Truncation boundary may land mid-word; rstrip removes trailing spaces
        text = "word " * 40  # many words with trailing spaces between them
        ctx = _make_ctx_with_body(
            tmp_path, text, config=_make_config(desc_max_length=10, desc_strip_markdown=False)
        )
        extract_description(ctx)
        assert not ctx.description.endswith(" ")

    def test_short_text_not_truncated(self, tmp_path: Path):
        text = "Short"
        ctx = _make_ctx_with_body(
            tmp_path, text, config=_make_config(desc_max_length=160, desc_strip_markdown=False)
        )
        extract_description(ctx)
        assert ctx.description == "Short"


class TestExtractDescriptionStripMarkdownWhenEnabled:
    """When desc_strip_markdown=True, inline markdown is stripped."""

    def test_strips_link_in_description(self, tmp_path: Path):
        body = "# T\n\n[anchor](https://x) and text"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=True))
        extract_description(ctx)
        assert "https://x" not in ctx.description
        assert "[" not in ctx.description
        assert "anchor" in ctx.description

    def test_strips_bold_in_description(self, tmp_path: Path):
        body = "**important** text"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=True))
        extract_description(ctx)
        assert "**" not in ctx.description
        assert "important" in ctx.description


class TestExtractDescriptionKeepsMarkdownWhenDisabled:
    """When desc_strip_markdown=False, inline markdown is preserved."""

    def test_preserves_link(self, tmp_path: Path):
        body = "[anchor](https://x)"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert "[anchor](https://x)" in ctx.description

    def test_preserves_bold(self, tmp_path: Path):
        body = "**bold** text"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config(desc_strip_markdown=False))
        extract_description(ctx)
        assert "**bold**" in ctx.description


class TestExtractDescriptionEmptyDraftWarns:
    """Draft with only H1 and blank lines -> empty description + stderr warning."""

    def test_empty_description_when_only_h1(self, tmp_path: Path, capsys):
        body = "# 标题\n\n"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config())
        extract_description(ctx)
        assert ctx.description == ""
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()

    def test_empty_draft_warns(self, tmp_path: Path, capsys):
        body = ""
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config())
        extract_description(ctx)
        assert ctx.description == ""
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()

    def test_does_not_raise_on_empty(self, tmp_path: Path):
        body = "# Only heading\n\n"
        ctx = _make_ctx_with_body(tmp_path, body, config=_make_config())
        # must not raise
        extract_description(ctx)


class TestExtractDescriptionCliExplicitValue:
    """CLI explicit description bypasses extraction."""

    def test_cli_value_used_directly(self, tmp_path: Path):
        body = "# Title\n\nThe body paragraph that should not be used"
        ctx = _make_ctx_with_body(tmp_path, body, cli_description="x")
        extract_description(ctx)
        assert ctx.description == "x"

    def test_cli_value_not_truncated(self, tmp_path: Path):
        # Even if longer than max_length, CLI value is used verbatim
        long_cli = "a" * 300
        ctx = _make_ctx_with_body(
            tmp_path, "body", cli_description=long_cli,
            config=_make_config(desc_max_length=50),
        )
        extract_description(ctx)
        assert ctx.description == long_cli


class TestExtractDescriptionCliExplicitEmpty:
    """CLI --description '' forces empty description (no extraction)."""

    def test_cli_empty_string_forces_empty(self, tmp_path: Path):
        body = "# Title\n\nThere is content here"
        ctx = _make_ctx_with_body(tmp_path, body, cli_description="")
        extract_description(ctx)
        assert ctx.description == ""


class TestExtractDescriptionUsesConfigDefault:
    """When CLI is None and config.default_description is non-empty, use config default."""

    def test_config_default_used_when_no_cli(self, tmp_path: Path):
        body = "# Title\n\nBody text"
        ctx = _make_ctx_with_body(
            tmp_path, body, cli_description=None,
            config=_make_config(default_description="d"),
        )
        extract_description(ctx)
        assert ctx.description == "d"

    def test_config_default_not_used_when_cli_is_set(self, tmp_path: Path):
        body = "# Title\n\nBody text"
        ctx = _make_ctx_with_body(
            tmp_path, body, cli_description="override",
            config=_make_config(default_description="d"),
        )
        extract_description(ctx)
        assert ctx.description == "override"


class TestExtractDescriptionChineseTruncation:
    """Chinese characters are counted by character (not byte) for max_length."""

    def test_chinese_truncated_by_char_count(self, tmp_path: Path):
        # 20 Chinese chars; limit to 10 -> 10 chars
        text = "一二三四五六七八九十" * 2  # 20 chars
        ctx = _make_ctx_with_body(
            tmp_path, text, config=_make_config(desc_max_length=10, desc_strip_markdown=False)
        )
        extract_description(ctx)
        assert len(ctx.description) == 10

    def test_chinese_not_truncated_when_under_limit(self, tmp_path: Path):
        text = "一二三四五"  # 5 chars
        ctx = _make_ctx_with_body(
            tmp_path, text, config=_make_config(desc_max_length=10, desc_strip_markdown=False)
        )
        extract_description(ctx)
        assert ctx.description == "一二三四五"


class TestRunPipelineThroughDescription:
    """End-to-end: run() processes up to extract_description and sets ctx.description."""

    def test_run_sets_description_from_body(self, tmp_path: Path):
        # Build a minimal tmp repo layout
        src_dir = tmp_path / "_drafts"
        src_dir.mkdir()
        data_dir = tmp_path / "_data"
        data_dir.mkdir()

        draft = src_dir / "test-post.md"
        draft.write_text("# Title\n\nThe first paragraph.", encoding="utf-8")
        (data_dir / "publish.yml").write_text(
            "defaults: {}\ndescription:\n  max_length: 160\n  strip_markdown: false\n",
            encoding="utf-8",
        )

        # We capture ctx by hooking into run internals via monkeypatch is impractical;
        # instead verify run() exits 0 (pipeline reaches description step without error)
        ret = run(
            ["--file", "test-post", "--slug", "test-post", "--src", str(src_dir)]
        )
        assert ret == 0


# ---------------------------------------------------------------------------
# BUG regression tests: strip_markdown_inline edge cases
# ---------------------------------------------------------------------------


class TestStripMarkdownInlineSnakeCase:
    """BUG-1: underscore regex must not consume underscores inside identifiers."""

    def test_preserves_snake_case(self):
        assert strip_markdown_inline("snake_case_name") == "snake_case_name"

    def test_preserves_path_underscores(self):
        assert strip_markdown_inline("/api/v1/user_profile") == "/api/v1/user_profile"

    def test_still_strips_single_underscore_emphasis(self):
        assert strip_markdown_inline("_emphasis_") == "emphasis"

    def test_still_strips_double_underscore_bold(self):
        assert strip_markdown_inline("__strong__") == "strong"


class TestStripMarkdownInlineLinkWithParens:
    """BUG-2: link regex must handle URLs that contain parentheses."""

    def test_link_with_parens_in_url(self):
        result = strip_markdown_inline(
            "[Wiki Foo](https://en.wikipedia.org/wiki/Foo_(bar))"
        )
        assert result == "Wiki Foo"
        assert ")" not in result

    def test_simple_link_still_works(self):
        assert strip_markdown_inline("[a](https://x)") == "a"


class TestStripMarkdownInlineMixedBoldItalic:
    """BUG-3: asterisk regex must match longest delimiter first to avoid residual marks."""

    def test_mixed_bold_italic_no_double_asterisk_residue(self):
        result = strip_markdown_inline("**a*b**")
        assert "**" not in result

    def test_triple_asterisk_only(self):
        assert strip_markdown_inline("***x***") == "x"

    def test_double_asterisk_only(self):
        assert strip_markdown_inline("**x**") == "x"

    def test_single_asterisk_only(self):
        assert strip_markdown_inline("*x*") == "x"
