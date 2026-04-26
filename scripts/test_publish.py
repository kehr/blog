"""Tests for publish.py - Step 1: config and error types."""
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
    PublishError,
    TargetPostExistsError,
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
