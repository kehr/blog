"""Tests for publish.py - Step 1: config and error types. Step 2: CLI and context."""
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
    parse_args,
    parse_list,
    run,
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
