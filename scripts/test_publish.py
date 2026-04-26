"""Tests for publish.py - Step 1: config and error types. Step 2: CLI and context. Step 3: draft loader and title resolver. Step 4: description extractor. Step 5: image scanner and link rewriter. Step 6: front matter builder and serializer."""
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest

from publish import (
    FIELD_ORDER,
    ConfigParseError,
    DraftHasFrontMatterError,
    DraftNotFoundError,
    ImageMove,
    ImageNameConflictError,
    ImageSourceMissingError,
    InvalidSlugError,
    PublishConfig,
    PublishContext,
    PublishError,
    TargetPostExistsError,
    _yaml_quote,
    build_frontmatter,
    classify_path,
    extract_description,
    hashes_equal,
    load_draft,
    parse_args,
    parse_list,
    process_images,
    resolve_title,
    run,
    serialize_frontmatter,
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


# ---------------------------------------------------------------------------
# Step 5: classify_path
# ---------------------------------------------------------------------------


class TestClassifyPathBasic:
    """classify_path returns 'remote', 'absolute', or 'relative' for various inputs."""

    def test_http_url_is_remote(self):
        assert classify_path("http://example.com/img.png") == "remote"

    def test_https_url_is_remote(self):
        assert classify_path("https://cdn.example.com/img.png") == "remote"

    def test_slash_prefix_is_absolute(self):
        assert classify_path("/Users/kyle/images/foo.png") == "absolute"

    def test_tilde_prefix_is_absolute(self):
        assert classify_path("~/Pictures/img.png") == "absolute"

    def test_relative_dot_slash(self):
        assert classify_path("./local/img.png") == "relative"

    def test_relative_no_prefix(self):
        assert classify_path("local/img.png") == "relative"

    def test_relative_double_dot(self):
        assert classify_path("../images/img.png") == "relative"


# ---------------------------------------------------------------------------
# Step 5: hashes_equal
# ---------------------------------------------------------------------------


class TestHashesEqual:
    """hashes_equal compares two files by sha1 content hash."""

    def test_same_content_returns_true(self, tmp_path: Path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"same content here")
        b.write_bytes(b"same content here")
        assert hashes_equal(a, b) is True

    def test_different_content_returns_false(self, tmp_path: Path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"content A")
        b.write_bytes(b"content B")
        assert hashes_equal(a, b) is False

    def test_empty_files_are_equal(self, tmp_path: Path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"")
        b.write_bytes(b"")
        assert hashes_equal(a, b) is True

    def test_empty_vs_non_empty_returns_false(self, tmp_path: Path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"")
        b.write_bytes(b"data")
        assert hashes_equal(a, b) is False


# ---------------------------------------------------------------------------
# Step 5 fixtures and helpers
# ---------------------------------------------------------------------------


def _make_image_repo(tmp_path: Path) -> Path:
    """Create a minimal repo layout under tmp_path and return repo_root."""
    (tmp_path / "_drafts").mkdir()
    (tmp_path / "_posts").mkdir()
    (tmp_path / "_data").mkdir()
    (tmp_path / "assets" / "img" / "posts").mkdir(parents=True)
    (tmp_path / "_data" / "publish.yml").write_text(
        "defaults: {}\n", encoding="utf-8"
    )
    return tmp_path


def _make_image_ctx(
    repo: Path,
    body: str,
    slug: str = "my-post",
    filename: str = "post.md",
) -> PublishContext:
    """Build a PublishContext with config and raw_body ready for process_images."""
    src_dir = repo / "_drafts"
    ctx = PublishContext(
        draft_file=src_dir / filename,
        slug=slug,
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
    ctx.raw_body = body
    ctx.config = PublishConfig(
        default_categories=[],
        default_tags=[],
        default_image_path="/assets/img/default.jpg",
        default_description="",
        desc_max_length=160,
        desc_strip_markdown=True,
        images_posts_dir=Path("assets/img/posts"),
        images_url_prefix="/assets/img/posts",
        posts_dir=Path("_posts"),
        slug_pattern="^[a-z0-9][a-z0-9-]*$",
        fail_on_existing_post=True,
    )
    return ctx


# ---------------------------------------------------------------------------
# Step 5: process_images -- markdown absolute path
# ---------------------------------------------------------------------------


class TestProcessImagesMdAbsolute:
    """Verification 1: markdown absolute path generates ImageMove and rewrites link."""

    def test_image_plan_has_one_move(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"fake png data")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert len(ctx.image_plan) == 1

    def test_image_move_source_is_absolute(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"fake png data")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert ctx.image_plan[0].source == img

    def test_image_move_target_path(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"fake png data")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        expected_target = repo / "assets" / "img" / "posts" / "my-post" / "foo.png"
        assert ctx.image_plan[0].target == expected_target

    def test_image_move_new_url(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"fake png data")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert ctx.image_plan[0].new_url == "/assets/img/posts/my-post/foo.png"

    def test_rewritten_body_has_new_url(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"fake png data")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert "/assets/img/posts/my-post/foo.png" in ctx.rewritten_body
        assert str(img) not in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- tilde home path
# ---------------------------------------------------------------------------


class TestProcessImagesMdHomePath:
    """Verification 2: ~/dir/img.png is expanded and processed as absolute."""

    def test_home_path_processed(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        # Use a real file under a known absolute path rather than actual ~
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "img.png"
        img.write_bytes(b"data")

        # Simulate a body with an absolute path (since ~ expansion in tests depends on HOME)
        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1
        assert ctx.image_plan[0].new_url == "/assets/img/posts/my-post/img.png"

    def test_tilde_expansion_via_monkeypatch(self, tmp_path: Path, monkeypatch):
        """Verify ~ prefix triggers expanduser: monkeypatch HOME to tmp_path."""
        import os
        monkeypatch.setenv("HOME", str(tmp_path))

        repo = _make_image_repo(tmp_path)
        img = tmp_path / "img.png"
        img.write_bytes(b"tilde image data")

        body = "![alt](~/img.png)"
        ctx = _make_image_ctx(repo, body, slug="tilde-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1
        assert ctx.image_plan[0].new_url == "/assets/img/posts/tilde-post/img.png"
        assert "~/img.png" not in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- relative path unchanged
# ---------------------------------------------------------------------------


class TestProcessImagesMdRelativeUnchanged:
    """Verification 3: relative paths are not added to image_plan and remain unchanged."""

    def test_relative_not_in_image_plan(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](./local/img.png)"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert ctx.image_plan == []

    def test_relative_link_unchanged_in_rewritten_body(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](./local/img.png)"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert "./local/img.png" in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- remote URL unchanged
# ---------------------------------------------------------------------------


class TestProcessImagesMdRemoteUnchanged:
    """Verification 4: remote https:// URLs are not touched."""

    def test_remote_not_in_image_plan(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](https://cdn.example.com/img.png)"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert ctx.image_plan == []

    def test_remote_link_unchanged_in_rewritten_body(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](https://cdn.example.com/img.png)"
        ctx = _make_image_ctx(repo, body)
        process_images(ctx)
        assert "https://cdn.example.com/img.png" in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- HTML img tag
# ---------------------------------------------------------------------------


class TestProcessImagesHtmlImg:
    """Verification 5: HTML img tags are handled same as markdown images."""

    def test_html_img_plan_generated(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.jpg"
        img.write_bytes(b"jpeg data")

        body = f'<img src="{img}" width="200">'
        ctx = _make_image_ctx(repo, body, slug="html-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1
        assert ctx.image_plan[0].new_url == "/assets/img/posts/html-post/foo.jpg"

    def test_html_img_attributes_preserved(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.jpg"
        img.write_bytes(b"jpeg data")

        body = f'<img src="{img}" width="200">'
        ctx = _make_image_ctx(repo, body, slug="html-post")
        process_images(ctx)
        # The rewritten body should preserve 'width="200"' attribute
        assert 'width="200"' in ctx.rewritten_body

    def test_html_img_src_rewritten(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.jpg"
        img.write_bytes(b"jpeg data")

        body = f'<img src="{img}" width="200">'
        ctx = _make_image_ctx(repo, body, slug="html-post")
        process_images(ctx)
        assert "/assets/img/posts/html-post/foo.jpg" in ctx.rewritten_body
        assert str(img) not in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- missing source raises
# ---------------------------------------------------------------------------


class TestProcessImagesMissingSourceRaises:
    """Verification 6: non-existent source raises ImageSourceMissingError listing all missing paths."""

    def test_raises_image_source_missing_error(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](/nonexistent/nowhere/img.png)"
        ctx = _make_image_ctx(repo, body)
        with pytest.raises(ImageSourceMissingError):
            process_images(ctx)

    def test_error_message_contains_missing_path(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = "![alt](/nonexistent/nowhere/img.png)"
        ctx = _make_image_ctx(repo, body)
        with pytest.raises(ImageSourceMissingError) as exc_info:
            process_images(ctx)
        assert "/nonexistent/nowhere/img.png" in str(exc_info.value)

    def test_error_lists_all_missing_paths(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        body = (
            "![a](/no/a.png)\n"
            "![b](/no/b.png)\n"
        )
        ctx = _make_image_ctx(repo, body)
        with pytest.raises(ImageSourceMissingError) as exc_info:
            process_images(ctx)
        msg = str(exc_info.value)
        assert "/no/a.png" in msg
        assert "/no/b.png" in msg


# ---------------------------------------------------------------------------
# Step 5: process_images -- dedup same source
# ---------------------------------------------------------------------------


class TestProcessImagesDedupSameSource:
    """Verification 7: same source referenced twice -> one ImageMove, both links rewritten."""

    def test_only_one_image_move_generated(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "shared.png"
        img.write_bytes(b"shared image data")

        body = f"![first]({img})\n\n![second]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1

    def test_both_links_rewritten(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "shared.png"
        img.write_bytes(b"shared image data")

        body = f"![first]({img})\n\n![second]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        # The original absolute path should not appear in rewritten_body at all
        assert str(img) not in ctx.rewritten_body
        # Both references converted to new URL
        new_url = "/assets/img/posts/my-post/shared.png"
        assert ctx.rewritten_body.count(new_url) == 2


# ---------------------------------------------------------------------------
# Step 5: process_images -- target exists same hash -> skip_copy
# ---------------------------------------------------------------------------


class TestProcessImagesTargetExistsSameHashSkip:
    """Verification 8: target already exists with same content -> ImageMove.skip_copy=True."""

    def test_skip_copy_true_when_same_hash(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        content = b"same image content"
        img.write_bytes(content)

        # Pre-create the target with same content
        target_dir = repo / "assets" / "img" / "posts" / "my-post"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "foo.png").write_bytes(content)

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1
        assert ctx.image_plan[0].skip_copy is True


# ---------------------------------------------------------------------------
# Step 5: process_images -- target exists different hash -> raises
# ---------------------------------------------------------------------------


class TestProcessImagesTargetExistsDiffHashRaises:
    """Verification 9: target already exists with different content -> ImageNameConflictError."""

    def test_raises_image_name_conflict_error(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"source content")

        # Pre-create target with different content
        target_dir = repo / "assets" / "img" / "posts" / "my-post"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "foo.png").write_bytes(b"different content")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        with pytest.raises(ImageNameConflictError):
            process_images(ctx)

    def test_error_message_contains_both_paths(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"source content")

        target_dir = repo / "assets" / "img" / "posts" / "my-post"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "foo.png").write_bytes(b"different content")

        body = f"![alt]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        with pytest.raises(ImageNameConflictError) as exc_info:
            process_images(ctx)
        msg = str(exc_info.value)
        assert str(img) in msg or "foo.png" in msg


# ---------------------------------------------------------------------------
# Step 5: process_images -- markdown image with title attribute
# ---------------------------------------------------------------------------


class TestProcessImagesMdWithTitle:
    """Verification 10: ![alt](path "title") still correctly extracts path."""

    def test_path_extracted_from_titled_md_image(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "titled.png"
        img.write_bytes(b"titled image")

        body = f'![alt]({img} "My Title")'
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1
        assert ctx.image_plan[0].new_url == "/assets/img/posts/my-post/titled.png"

    def test_title_preserved_in_rewritten_body(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "titled.png"
        img.write_bytes(b"titled image")

        body = f'![alt]({img} "My Title")'
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        # Title should remain in rewritten body
        assert '"My Title"' in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- Chinese alt text
# ---------------------------------------------------------------------------


class TestProcessImagesMdChineseAlt:
    """Verification 11: Chinese alt text is handled normally."""

    def test_chinese_alt_processed(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "zh.png"
        img.write_bytes(b"image data")

        body = f"![中文描述]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert len(ctx.image_plan) == 1

    def test_chinese_alt_preserved_in_rewritten_body(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "zh.png"
        img.write_bytes(b"image data")

        body = f"![中文描述]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)
        assert "中文描述" in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5: process_images -- end-to-end via run()
# ---------------------------------------------------------------------------


class TestRunPipelineThroughImages:
    """Verification 15: run() goes through process_images; ctx.image_plan and rewritten_body set."""

    def test_run_exits_zero_with_absolute_image(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "cover.png"
        img.write_bytes(b"image bytes")

        draft = repo / "_drafts" / "my-draft.md"
        draft.write_text(
            f"# Title\n\nSome text.\n\n![cover]({img})\n",
            encoding="utf-8",
        )

        ret = run(
            ["--file", "my-draft", "--slug", "my-post", "--src", str(repo / "_drafts")]
        )
        assert ret == 0

    def test_run_returns_nonzero_when_image_missing(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        draft = repo / "_drafts" / "my-draft.md"
        draft.write_text(
            "# Title\n\nText.\n\n![img](/no/such/img.png)\n",
            encoding="utf-8",
        )

        ret = run(
            ["--file", "my-draft", "--slug", "my-post", "--src", str(repo / "_drafts")]
        )
        assert ret != 0


# ---------------------------------------------------------------------------
# Step 5 bug regression: alt-equals-path false-hit in _rewrite_md/_rewrite_html
# ---------------------------------------------------------------------------


class TestRewriteMdAltEqualsPath:
    """BUG-4: when alt == path (Obsidian default), str.replace must not corrupt alt text."""

    def test_src_rewritten_not_alt(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"image data")

        # alt == absolute path (Obsidian/Typora default behavior)
        body = f"![{img}]({img})"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)

        # src must be rewritten to the new URL
        assert "](/assets/img/posts/my-post/foo.png)" in ctx.rewritten_body
        # alt must remain the original absolute path (unchanged)
        assert f"![{img}]" in ctx.rewritten_body


class TestRewriteHtmlAltEqualsPath:
    """BUG-4: when HTML alt == src, only the src attribute value must be rewritten."""

    def test_src_rewritten_alt_unchanged(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"image data")

        body = f'<img src="{img}" alt="{img}">'
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)

        # src attribute must contain the new URL
        assert 'src="/assets/img/posts/my-post/foo.png"' in ctx.rewritten_body
        # alt must remain the original absolute path
        assert f'alt="{img}"' in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 5 bug regression: absolute images_posts_dir rejected at config parse time
# ---------------------------------------------------------------------------


class TestConfigRejectsAbsoluteImagesPostsDir:
    """BUG-5: images.posts_dir with absolute path must raise ConfigParseError immediately."""

    def test_absolute_posts_dir_raises(self, tmp_path: Path):
        cfg_file = tmp_path / "publish.yml"
        cfg_file.write_text(
            "images:\n  posts_dir: /etc/var\n  url_prefix: /a\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigParseError) as exc_info:
            PublishConfig.from_yaml(cfg_file)
        assert "must be relative" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Step 5 supplemental: single-quote src in HTML img
# ---------------------------------------------------------------------------


class TestHtmlImgSingleQuoteSrc:
    """Supplemental: <img src='path'> with single quotes is correctly handled."""

    def test_single_quote_src_rewritten(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        img_dir = tmp_path / "ext_images"
        img_dir.mkdir()
        img = img_dir / "foo.png"
        img.write_bytes(b"image data")

        body = f"<img src='{img}' width='200'>"
        ctx = _make_image_ctx(repo, body, slug="my-post")
        process_images(ctx)

        assert "/assets/img/posts/my-post/foo.png" in ctx.rewritten_body
        assert str(img) not in ctx.rewritten_body


# ---------------------------------------------------------------------------
# Step 6 helpers
# ---------------------------------------------------------------------------


def _make_fm_config(
    categories: list[str] | None = None,
    tags: list[str] | None = None,
    image_path: str = "/assets/img/default.jpg",
) -> PublishConfig:
    """Build a PublishConfig with controllable front matter defaults."""
    return PublishConfig(
        default_categories=categories if categories is not None else ["Notes"],
        default_tags=tags if tags is not None else ["notes"],
        default_image_path=image_path,
        default_description="",
        desc_max_length=160,
        desc_strip_markdown=True,
        images_posts_dir=Path("assets/img/posts"),
        images_url_prefix="/assets/img/posts",
        posts_dir=Path("_posts"),
        slug_pattern="^[a-z0-9][a-z0-9-]*$",
        fail_on_existing_post=True,
    )


def _make_fm_ctx(
    slug: str = "test-post",
    title: str = "Test Title",
    description: str = "A test description.",
    cli_categories: list[str] | None = None,
    cli_tags: list[str] | None = None,
    cli_image: str | None = None,
    cli_date: datetime | None = None,
    config: PublishConfig | None = None,
) -> PublishContext:
    """Build a PublishContext with fields pre-filled up to build_frontmatter."""
    if config is None:
        config = _make_fm_config()
    ctx = PublishContext(
        draft_file=Path("/tmp/draft.md"),
        slug=slug,
        src_dir=Path("/tmp/_drafts"),
        cli_categories=cli_categories,
        cli_tags=cli_tags,
        cli_image=cli_image,
        cli_description=None,
        cli_date=cli_date,
        dry_run=False,
        force=False,
        verbose=False,
    )
    ctx.config = config
    ctx.title = title
    ctx.description = description
    return ctx


# ---------------------------------------------------------------------------
# Step 6: _yaml_quote
# ---------------------------------------------------------------------------


class TestYamlQuoteSafeText:
    """test_yaml_quote_safe_text: plain text and Chinese output as bare values."""

    def test_plain_english(self):
        assert _yaml_quote("hello world") == "hello world"

    def test_chinese_bare(self):
        # Chinese characters are safe bare values in YAML 1.1/1.2 with UTF-8
        assert _yaml_quote("你好世界") == "你好世界"

    def test_mixed_chinese_english(self):
        assert _yaml_quote("从 LLM 到 Agent") == "从 LLM 到 Agent"

    def test_digits_embedded_in_text(self):
        # text with embedded digits is fine as long as the whole string is not numeric
        assert _yaml_quote("step 6") == "step 6"


class TestYamlQuoteSpecial:
    """test_yaml_quote_special: strings with special chars are double-quoted."""

    def test_colon_in_string(self):
        result = _yaml_quote("title: with colon")
        assert result.startswith('"') and result.endswith('"')

    def test_hash_in_string(self):
        result = _yaml_quote("text # comment")
        assert result.startswith('"') and result.endswith('"')

    def test_single_quote_in_string(self):
        result = _yaml_quote("it's fine")
        assert result.startswith('"') and result.endswith('"')

    def test_double_quote_in_string_escapes(self):
        result = _yaml_quote('say "hello"')
        # Outer double-quotes wrapping, inner double-quote escaped
        assert result == '"say \\"hello\\""'

    def test_leading_bracket(self):
        result = _yaml_quote("[item]")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_brace(self):
        result = _yaml_quote("{key: val}")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_exclamation(self):
        result = _yaml_quote("!important")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_asterisk(self):
        result = _yaml_quote("*bold*")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_ampersand(self):
        result = _yaml_quote("&ref")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_pipe(self):
        result = _yaml_quote("|literal")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_gt(self):
        result = _yaml_quote(">folded")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_percent(self):
        result = _yaml_quote("%TAG")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_at(self):
        result = _yaml_quote("@handle")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_backtick(self):
        result = _yaml_quote("`code`")
        assert result.startswith('"') and result.endswith('"')

    def test_leading_whitespace(self):
        result = _yaml_quote(" leading space")
        assert result.startswith('"') and result.endswith('"')

    def test_trailing_whitespace(self):
        result = _yaml_quote("trailing space ")
        assert result.startswith('"') and result.endswith('"')

    def test_backslash_escaped_in_quoted(self):
        result = _yaml_quote("path\\to\\file")
        # Backslash triggers quoting
        assert result.startswith('"') and result.endswith('"')
        # Internal backslashes must be escaped as \\
        assert '\\\\' in result


class TestYamlQuoteEmpty:
    """test_yaml_quote_empty: empty string returns the literal two double-quotes."""

    def test_empty_string(self):
        assert _yaml_quote("") == '""'


class TestYamlQuoteYamlKeywords:
    """test_yaml_quote_yaml_keywords: YAML boolean/null lookalikes are quoted."""

    def test_yes_quoted(self):
        result = _yaml_quote("yes")
        assert result.startswith('"') and result.endswith('"')

    def test_no_quoted(self):
        result = _yaml_quote("no")
        assert result.startswith('"') and result.endswith('"')

    def test_true_quoted(self):
        result = _yaml_quote("true")
        assert result.startswith('"') and result.endswith('"')

    def test_false_quoted(self):
        result = _yaml_quote("false")
        assert result.startswith('"') and result.endswith('"')

    def test_null_quoted(self):
        result = _yaml_quote("null")
        assert result.startswith('"') and result.endswith('"')

    def test_pure_integer_string_quoted(self):
        # A string that looks like an integer should be quoted
        result = _yaml_quote("123")
        assert result.startswith('"') and result.endswith('"')

    def test_pure_float_string_quoted(self):
        result = _yaml_quote("3.14")
        assert result.startswith('"') and result.endswith('"')


# ---------------------------------------------------------------------------
# Step 6: build_frontmatter
# ---------------------------------------------------------------------------


class TestBuildFrontmatterUsesConfigDefaults:
    """Verification 1: no CLI overrides -> front_matter mirrors config defaults."""

    def test_categories_from_config(self):
        ctx = _make_fm_ctx()
        build_frontmatter(ctx)
        assert ctx.front_matter["categories"] == ["Notes"]

    def test_tags_from_config(self):
        ctx = _make_fm_ctx()
        build_frontmatter(ctx)
        assert ctx.front_matter["tags"] == ["notes"]

    def test_image_from_config(self):
        ctx = _make_fm_ctx()
        build_frontmatter(ctx)
        assert ctx.front_matter["image"] == {"path": "/assets/img/default.jpg"}

    def test_title_from_ctx(self):
        ctx = _make_fm_ctx(title="My Draft Title")
        build_frontmatter(ctx)
        assert ctx.front_matter["title"] == "My Draft Title"

    def test_description_from_ctx(self):
        ctx = _make_fm_ctx(description="A short blurb.")
        build_frontmatter(ctx)
        assert ctx.front_matter["description"] == "A short blurb."

    def test_date_is_datetime(self):
        ctx = _make_fm_ctx()
        build_frontmatter(ctx)
        assert isinstance(ctx.front_matter["date"], datetime)


class TestBuildFrontmatterCliCategoriesOverrides:
    """Verification 2: cli_categories not None -> overrides config default."""

    def test_cli_list_overrides(self):
        ctx = _make_fm_ctx(cli_categories=["A", "B"])
        build_frontmatter(ctx)
        assert ctx.front_matter["categories"] == ["A", "B"]

    def test_cli_single_overrides(self):
        ctx = _make_fm_ctx(cli_categories=["Tech"])
        build_frontmatter(ctx)
        assert ctx.front_matter["categories"] == ["Tech"]


class TestBuildFrontmatterCliCategoriesExplicitEmpty:
    """Verification 3: cli_categories=[] -> front_matter has empty list (force clear)."""

    def test_explicit_empty_list(self):
        ctx = _make_fm_ctx(cli_categories=[])
        build_frontmatter(ctx)
        assert ctx.front_matter["categories"] == []


class TestBuildFrontmatterCliImageOverrides:
    """Verification 4: cli_image provided -> image dict uses that path."""

    def test_cli_image_path(self):
        ctx = _make_fm_ctx(cli_image="/x.png")
        build_frontmatter(ctx)
        assert ctx.front_matter["image"] == {"path": "/x.png"}

    def test_cli_image_overrides_config_default(self):
        config = _make_fm_config(image_path="/assets/img/default.jpg")
        ctx = _make_fm_ctx(cli_image="/custom.png", config=config)
        build_frontmatter(ctx)
        assert ctx.front_matter["image"]["path"] == "/custom.png"


class TestBuildFrontmatterCliDateOverrides:
    """Verification 5: cli_date set -> front_matter date uses it; ctx.publish_date also updated."""

    def test_cli_date_in_front_matter(self):
        specific = datetime(2026, 1, 15, 9, 0, 0).astimezone()
        ctx = _make_fm_ctx(cli_date=specific)
        build_frontmatter(ctx)
        assert ctx.front_matter["date"] == specific

    def test_ctx_publish_date_updated(self):
        specific = datetime(2026, 1, 15, 9, 0, 0).astimezone()
        ctx = _make_fm_ctx(cli_date=specific)
        build_frontmatter(ctx)
        assert ctx.publish_date == specific

    def test_no_cli_date_uses_publish_date(self):
        ctx = _make_fm_ctx(cli_date=None)
        original = ctx.publish_date
        build_frontmatter(ctx)
        assert ctx.front_matter["date"] == original


class TestBuildFrontmatterFieldOrder:
    """Verification 6: dict keys order matches FIELD_ORDER."""

    def test_keys_in_field_order(self):
        ctx = _make_fm_ctx()
        build_frontmatter(ctx)
        assert list(ctx.front_matter.keys()) == FIELD_ORDER


# ---------------------------------------------------------------------------
# Step 6: serialize_frontmatter
# ---------------------------------------------------------------------------


class TestSerializeFrontmatterBasic:
    """Verification 7: output starts and ends with ---."""

    def test_starts_with_dashes(self):
        fm = {
            "title": "Hello",
            "description": "A blurb",
            "date": datetime(2026, 4, 19, 10, 0, 0).astimezone(),
            "categories": ["Notes"],
            "tags": ["AI"],
            "image": {"path": "/assets/img/default.jpg"},
        }
        result = serialize_frontmatter(fm)
        assert result.startswith("---\n")

    def test_ends_with_dashes_newline(self):
        fm = {
            "title": "Hello",
            "description": "A blurb",
            "date": datetime(2026, 4, 19, 10, 0, 0).astimezone(),
            "categories": ["Notes"],
            "tags": ["AI"],
            "image": {"path": "/assets/img/default.jpg"},
        }
        result = serialize_frontmatter(fm)
        assert result.endswith("---\n")

    def test_one_field_per_logical_entry(self):
        fm = {
            "title": "Hello",
            "description": "A blurb",
        }
        result = serialize_frontmatter(fm)
        lines = result.strip().split("\n")
        # Should have: ---, title, description, ---
        assert len(lines) == 4


class TestSerializeFrontmatterImageNested:
    """Verification 8: image renders as 2-line nested structure."""

    def test_image_two_lines(self):
        fm = {"image": {"path": "/assets/img/foo.png"}}
        result = serialize_frontmatter(fm)
        lines = [l for l in result.split("\n") if l.strip()]
        # Look for "image:" and "  path: ..."
        assert any(l == "image:" for l in lines)
        assert any(l.startswith("  path:") for l in lines)

    def test_image_path_value_present(self):
        fm = {"image": {"path": "/assets/img/foo.png"}}
        result = serialize_frontmatter(fm)
        assert "/assets/img/foo.png" in result


class TestSerializeFrontmatterListIndent:
    """Verification 9: list fields render with 2-space bullet indent."""

    def test_categories_rendered_as_list(self):
        fm = {"categories": ["a", "b"]}
        result = serialize_frontmatter(fm)
        assert "categories:\n  - a\n  - b" in result

    def test_tags_rendered_as_list(self):
        fm = {"tags": ["x", "y", "z"]}
        result = serialize_frontmatter(fm)
        assert "tags:\n  - x\n  - y\n  - z" in result


class TestSerializeFrontmatterEmptyList:
    """Verification 10: empty list renders as `key: []`."""

    def test_empty_categories(self):
        fm = {"categories": []}
        result = serialize_frontmatter(fm)
        assert "categories: []" in result

    def test_empty_tags(self):
        fm = {"tags": []}
        result = serialize_frontmatter(fm)
        assert "tags: []" in result


class TestSerializeFrontmatterDateFormat:
    """Verification 11: datetime renders as YYYY-MM-DD HH:MM:SS +HHMM."""

    def test_date_format_utc_offset(self):
        import datetime as dt_module
        # Create a fixed-offset aware datetime at +0800
        tz = dt_module.timezone(dt_module.timedelta(hours=8))
        d = datetime(2026, 4, 19, 10, 0, 0, tzinfo=tz)
        fm = {"date": d}
        result = serialize_frontmatter(fm)
        assert "date: 2026-04-19 10:00:00 +0800" in result


class TestSerializeFrontmatterQuotesSpecialChars:
    """Verification 12: title/description with special chars gets quoted."""

    def test_colon_in_title_quoted(self):
        fm = {"title": "My Post: A Story"}
        result = serialize_frontmatter(fm)
        assert 'title: "My Post: A Story"' in result

    def test_double_quote_in_title_escaped(self):
        fm = {"title": 'Say "hello"'}
        result = serialize_frontmatter(fm)
        # The value should be double-quoted with inner quotes escaped
        assert 'title: "Say \\"hello\\""' in result

    def test_plain_chinese_not_quoted(self):
        fm = {"title": "纯中文标题"}
        result = serialize_frontmatter(fm)
        assert "title: 纯中文标题" in result

    def test_mixed_chinese_with_fullwidth_colon_bare(self):
        # Full-width colon U+FF1A is NOT a YAML structural character; no quoting needed.
        fm = {"title": "从 LLM 到 Agent：以 Harness 为骨架的 0-1 工程路线"}
        result = serialize_frontmatter(fm)
        title_line = [l for l in result.split("\n") if l.startswith("title:")][0]
        # Should be a bare value, no surrounding double-quotes
        assert title_line == "title: 从 LLM 到 Agent：以 Harness 为骨架的 0-1 工程路线"

    def test_ascii_colon_in_title_quoted(self):
        # ASCII colon is a YAML structural character and must trigger quoting
        fm = {"title": "My Post: A Story"}
        result = serialize_frontmatter(fm)
        assert 'title: "My Post: A Story"' in result


class TestSerializeFrontmatterQuotesYamlKeywords:
    """Verification 13: YAML keyword lookalikes are quoted to prevent misinterpretation."""

    def test_yes_in_title_quoted(self):
        fm = {"title": "yes"}
        result = serialize_frontmatter(fm)
        assert 'title: "yes"' in result

    def test_null_in_title_quoted(self):
        fm = {"title": "null"}
        result = serialize_frontmatter(fm)
        assert 'title: "null"' in result

    def test_pure_number_in_title_quoted(self):
        fm = {"title": "123"}
        result = serialize_frontmatter(fm)
        assert 'title: "123"' in result


class TestSerializeFrontmatterKeepsRealPostStyle:
    """Verification 14: output matches 2026-04-19-agent-engineering-with-harness.md header style."""

    def test_real_post_style(self):
        import datetime as dt_module
        tz = dt_module.timezone(dt_module.timedelta(hours=8))
        d = datetime(2026, 4, 19, 10, 0, 0, tzinfo=tz)
        fm = {
            "title": "从 LLM 到 Agent：以 Harness 为骨架的 0-1 工程路线",
            "description": (
                "过去一年的 Agent 项目里，决定生产可靠性的不是模型选型，"
                "而是 Harness 工程。这篇梳理底层机制、四类设计模式、多智能体边界、"
                "框架取舍与一条按 Prompt-Context-Harness 三层递进的学习路径。"
            ),
            "date": d,
            "categories": ["Notes"],
            "tags": ["AI"],
            "image": {"path": "/assets/img/agentic-ai.png"},
        }
        result = serialize_frontmatter(fm)
        # Field order check
        keys_in_output = [
            l.split(":")[0].strip()
            for l in result.split("\n")
            if l and not l.startswith(" ") and l != "---" and ":" in l
        ]
        assert keys_in_output == ["title", "description", "date", "categories", "tags", "image"]
        # Nested image style
        assert "image:\n  path:" in result
        # List style
        assert "categories:\n  - Notes" in result
        assert "tags:\n  - AI" in result
        # Date format
        assert "date: 2026-04-19 10:00:00 +0800" in result
        # Title uses full-width colon (U+FF1A) which is not a YAML structural character
        # -> bare value, no surrounding quotes, matching real post style
        assert "title: 从 LLM 到 Agent：以 Harness 为骨架的 0-1 工程路线" in result
        assert 'title: "从 LLM 到 Agent：以 Harness 为骨架的 0-1 工程路线"' not in result


# ---------------------------------------------------------------------------
# Step 6: run() integration through build_frontmatter
# ---------------------------------------------------------------------------


class TestRunPipelineThroughFrontmatter:
    """Verification 18: end-to-end run builds ctx.front_matter."""

    def test_front_matter_populated_after_run(self, tmp_path: Path):
        # Build a minimal repo
        repo = _make_image_repo(tmp_path)
        draft = repo / "_drafts" / "my-post.md"
        draft.write_text("# My Post\n\nSome content here.\n", encoding="utf-8")

        rc = run([
            "--file", "my-post",
            "--slug", "my-post",
            "--src", str(repo / "_drafts"),
        ])
        assert rc == 0

    def test_front_matter_has_all_fields(self, tmp_path: Path):
        repo = _make_image_repo(tmp_path)
        draft = repo / "_drafts" / "test-post.md"
        draft.write_text("# Test Post\n\nContent for testing.\n", encoding="utf-8")

        # Patch run to return ctx for inspection
        import publish as pub
        captured: list[pub.PublishContext] = []
        original_build = pub.build_frontmatter

        def capturing_build(ctx: pub.PublishContext) -> None:
            original_build(ctx)
            captured.append(ctx)

        pub.build_frontmatter = capturing_build
        try:
            rc = run([
                "--file", "test-post",
                "--slug", "test-post",
                "--src", str(repo / "_drafts"),
            ])
        finally:
            pub.build_frontmatter = original_build

        assert rc == 0
        assert len(captured) == 1
        fm = captured[0].front_matter
        for field in FIELD_ORDER:
            assert field in fm, f"Missing field: {field}"
