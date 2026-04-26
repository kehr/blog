# Draft Publisher TRD

依据：`docs/prds/draft-publisher-prd.md`

## 1. 整体架构

单文件 Python 脚本 `scripts/publish.py`，约 250-300 行；按 9 步流水线组织，无类继承层次，函数式风格。

```
                +---------------------+
                |  parse_args()       |  CLI 解析
                +----------+----------+
                           |
                           v
                +---------------------+
                |  load_config()      |  _data/publish.yml
                +----------+----------+
                           |
                           v
                +---------------------+
                |  load_draft()       |  读 _drafts/<file>.md
                +----------+----------+
                           |
                           v
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
+---------------+ +-----------------+ +---------------+
| resolve_title | | extract_desc    | | process_imgs  |
+-------+-------+ +-------+---------+ +-------+-------+
        |                 |                   |
        +--------+--------+-------------------+
                 v
        +---------------------+
        |  build_frontmatter  |
        +----------+----------+
                   v
        +---------------------+
        |  assemble_post      |
        +----------+----------+
                   v
        +---------------------+
        |  commit_filesystem  |  事务边界
        +---------------------+
```

## 2. 数据结构

### 2.1 PublishContext

贯穿整条流水线的纯数据载体，不带行为：

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

@dataclass
class PublishContext:
    # CLI 输入
    draft_file: Path                    # 绝对路径
    slug: str
    src_dir: Path
    cli_categories: Optional[list[str]] # None = 走默认；[] = 强制置空
    cli_tags: Optional[list[str]]
    cli_image: Optional[str]
    cli_description: Optional[str]
    cli_date: Optional[datetime]
    dry_run: bool
    force: bool
    verbose: bool

    # 配置
    config: "PublishConfig"

    # 计算结果
    title: str = ""
    description: str = ""
    publish_date: datetime = field(default_factory=datetime.now)
    image_plan: list["ImageMove"] = field(default_factory=list)
    rewritten_body: str = ""
    front_matter: dict = field(default_factory=dict)
    target_post_path: Path = field(default_factory=Path)
```

### 2.2 PublishConfig

配置文件读取后的强类型镜像，缺省值兜底；用 dataclass + classmethod 解析：

```python
@dataclass
class PublishConfig:
    default_categories: list[str]
    default_tags: list[str]
    default_image_path: str
    default_description: str
    desc_max_length: int
    desc_strip_markdown: bool
    images_posts_dir: Path        # assets/img/posts
    images_url_prefix: str        # /assets/img/posts
    posts_dir: Path               # _posts
    slug_pattern: str
    fail_on_existing_post: bool

    @classmethod
    def from_yaml(cls, path: Path) -> "PublishConfig":
        ...
```

### 2.3 ImageMove

单条图片搬运指令：

```python
@dataclass
class ImageMove:
    source: Path           # 草稿引用的原始绝对路径
    target: Path           # assets/img/posts/<slug>/<basename>
    new_url: str           # /assets/img/posts/<slug>/<basename>
    skip_copy: bool = False  # True 表示目标已存在且哈希一致
```

### 2.4 错误类型

集中定义在文件头部，所有错误继承自一个基类，便于 main 统一捕获并退出码非 0：

```python
class PublishError(Exception):
    exit_code: int = 1

class DraftNotFoundError(PublishError):    pass
class DraftHasFrontMatterError(PublishError): pass
class InvalidSlugError(PublishError):       pass
class TargetPostExistsError(PublishError):  pass
class ImageSourceMissingError(PublishError):pass
class ImageNameConflictError(PublishError): pass
class ConfigParseError(PublishError):       pass
```

## 3. 核心函数接口

### 3.1 流水线主控

```python
def run(argv: list[str]) -> int:
    """脚本入口。捕获 PublishError 转为退出码，捕获其他异常打栈并退出 2。"""
    try:
        ctx = parse_args(argv)
        ctx.config = load_config(ctx)
        load_draft(ctx)
        resolve_title(ctx)
        extract_description(ctx)
        process_images(ctx)
        build_frontmatter(ctx)
        assemble_post(ctx)
        commit_filesystem(ctx)
        return 0
    except PublishError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code
```

### 3.2 各步签名

```python
def parse_args(argv: list[str]) -> PublishContext: ...
def load_config(ctx: PublishContext) -> PublishConfig: ...
def load_draft(ctx: PublishContext) -> None:
    """读 ctx.draft_file 到 ctx._raw_body；若内容以 `---` 起始则抛 DraftHasFrontMatterError。"""

def resolve_title(ctx: PublishContext) -> None:
    """ctx.title = ctx.draft_file.stem"""

def extract_description(ctx: PublishContext) -> None:
    """按 PRD 3.4 规则填 ctx.description；CLI 显式传值则跳过提取。"""

def process_images(ctx: PublishContext) -> None:
    """扫描 ctx._raw_body，填 ctx.image_plan 与 ctx.rewritten_body。
       不实际拷贝文件（拷贝在 commit_filesystem）。"""

def build_frontmatter(ctx: PublishContext) -> None:
    """填 ctx.front_matter 字典，字段顺序按 PRD 3.4 规定。"""

def assemble_post(ctx: PublishContext) -> None:
    """生成最终 post 文本（front matter + rewritten_body），填 ctx.target_post_path。"""

def commit_filesystem(ctx: PublishContext) -> None:
    """事务性写盘；dry_run=True 时仅打印计划。"""
```

## 4. 关键实现要点

### 4.1 Front matter 序列化

不直接用 `yaml.safe_dump`（顺序不可控），改为手工拼装确保字段顺序：

```python
FIELD_ORDER = ["title", "description", "date", "categories", "tags", "image"]

def serialize_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for key in FIELD_ORDER:
        if key not in fm:
            continue
        value = fm[key]
        if key == "image":
            lines.append("image:")
            lines.append(f'  path: "{value["path"]}"')
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, datetime):
            lines.append(f'{key}: {value.strftime("%Y-%m-%d %H:%M:%S %z")}')
        else:
            lines.append(f"{key}: {_yaml_quote(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"
```

`_yaml_quote()` 在值含冒号、井号、单/双引号、首字符为特殊字符时加引号，否则裸值。

### 4.2 图片正则

支持两种语法：

```python
MD_IMG = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
HTML_IMG = re.compile(
    r'<img\s+[^>]*?src=(["\'])(?P<path>[^"\']+)\1[^>]*>',
    re.IGNORECASE,
)
```

判定路径形态：

```python
def classify_path(p: str) -> str:
    if re.match(r"^https?://", p):
        return "remote"
    if p.startswith("/") or p.startswith("~"):
        return "absolute"
    return "relative"
```

仅 `absolute` 触发拷贝与重写。`~` 路径用 `os.path.expanduser` 展开。

### 4.3 Description 提取

```python
def extract_description_text(body: str, max_len: int, strip_md: bool) -> str:
    lines = body.splitlines()
    i = 0
    # 跳过开头空行
    while i < len(lines) and not lines[i].strip():
        i += 1
    # 跳过首个 H1
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        i += 1
    # 跳过 H1 后空行
    while i < len(lines) and not lines[i].strip():
        i += 1
    # 收集首个非空段落（连续非空行）
    para = []
    while i < len(lines) and lines[i].strip():
        para.append(lines[i].strip())
        i += 1
    text = " ".join(para)
    if strip_md:
        text = strip_markdown_inline(text)
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text

def strip_markdown_inline(s: str) -> str:
    # 去 [text](url) -> text；去 **x**/*x*/`x` 标记
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", s)
    s = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", s)
    return s.strip()
```

### 4.4 事务性写盘

```python
def commit_filesystem(ctx: PublishContext) -> None:
    if ctx.dry_run:
        print_plan(ctx)
        return

    written_images: list[Path] = []
    written_post: Optional[Path] = None
    try:
        # Step 1: copy images
        for move in ctx.image_plan:
            if move.skip_copy:
                continue
            move.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(move.source, move.target)
            written_images.append(move.target)
        # Step 2: write post
        ctx.target_post_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.target_post_path.write_text(ctx.assembled_text, encoding="utf-8")
        written_post = ctx.target_post_path
        # Step 3: delete draft (best-effort)
        try:
            ctx.draft_file.unlink()
        except OSError as e:
            print(f"warning: failed to delete draft {ctx.draft_file}: {e}", file=sys.stderr)
    except Exception:
        # rollback: remove files written in this run
        for p in written_images:
            p.unlink(missing_ok=True)
        if written_post is not None:
            written_post.unlink(missing_ok=True)
        raise
```

### 4.5 图片冲突哈希

```python
def hashes_equal(a: Path, b: Path, chunk: int = 65536) -> bool:
    import hashlib
    def h(p: Path) -> str:
        m = hashlib.sha1()
        with p.open("rb") as f:
            for blk in iter(lambda: f.read(chunk), b""):
                m.update(blk)
        return m.hexdigest()
    return h(a) == h(b)
```

### 4.6 CLI 解析约定

用 `argparse`；列表型参数支持「逗号分隔」与「重复传参」两种形式：

```python
def parse_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]
```

`--categories ""` 显式空字符串解析为 `[]`，触发「强制置空」语义；不传该参数时为 `None`，走默认。

### 4.7 Makefile 集成

```makefile
PYTHON ?= python3

.PHONY: publish publish-list publish-check test-publish

publish:
	@if [ -z "$(file)" ] || [ -z "$(slug)" ]; then \
	  echo 'usage: make publish file="..." slug="..." [categories=...] [tags=...] [image=...] [date=...] [src=...] [dry-run=1] [force=1]'; exit 1; \
	fi
	@$(PYTHON) scripts/publish.py \
	  --file "$(file)" --slug "$(slug)" \
	  $(if $(categories),--categories "$(categories)") \
	  $(if $(tags),--tags "$(tags)") \
	  $(if $(image),--image "$(image)") \
	  $(if $(date),--date "$(date)") \
	  $(if $(src),--src "$(src)") \
	  $(if $(dry-run),--dry-run) \
	  $(if $(force),--force)

publish-list:
	@$(PYTHON) scripts/publish.py --list

publish-check:
	@$(MAKE) publish file="$(file)" slug="$(slug)" dry-run=1 \
	  $(if $(categories),categories="$(categories)") \
	  $(if $(tags),tags="$(tags)") \
	  $(if $(image),image="$(image)")

test-publish:
	@$(PYTHON) -m pytest scripts/test_publish.py -v
```

## 5. 测试桩

`scripts/test_publish.py` 用 pytest 与 `tmp_path` fixture，结构：

```python
@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "_drafts").mkdir()
    (tmp_path / "_posts").mkdir()
    (tmp_path / "_data").mkdir()
    (tmp_path / "assets/img/posts").mkdir(parents=True)
    (tmp_path / "_data/publish.yml").write_text(DEFAULT_CONFIG_YAML)
    return tmp_path

def write_draft(repo: Path, name: str, body: str) -> Path: ...
def run_publish(repo: Path, **kwargs) -> int: ...
```

Pipeline 函数对外都接受 `PublishContext`，测试可单独构造 ctx 调用单步而不跑整条流程。

## 6. 依赖

- Python 3.9+（`dataclasses` / `pathlib` / `typing` 标准库；本仓 `.ruby-version` 与 Python 无冲突）
- `PyYAML` 7+：`pip install pyyaml`
- 测试：`pytest` 7+：`pip install pytest`

新建 `scripts/requirements.txt` 与 `scripts/requirements-dev.txt`：

```
# scripts/requirements.txt
PyYAML>=6.0

# scripts/requirements-dev.txt
-r requirements.txt
pytest>=7.0
```

Makefile `publish` target 依赖 `PyYAML`：缺失时给出 `pip install -r scripts/requirements.txt` 提示。

## 7. 与现有代码的衔接

| 文件 | 操作 |
|-----|------|
| `scripts/publish-post.sh` | 删除 |
| `scripts/new-post.sh` | 不动 |
| `_templates/New Post.md` | 不动（Obsidian 用，与 publish.py 解耦） |
| `Makefile` | 替换 `publish` target；新增 `publish-list` / `publish-check` / `test-publish` |
| `_data/publish.yml` | 新建 |
| `scripts/publish.py` | 新建 |
| `scripts/test_publish.py` | 新建 |
| `scripts/requirements.txt` | 新建 |
| `scripts/requirements-dev.txt` | 新建 |
| `.gitignore` | 检查是否需排除 `__pycache__/`、`.pytest_cache/` |

## 8. 设计原则与注意点

| 项 | 原则 |
|----|------|
| 单一文件 | publish.py 不引入子模块；超过 350 行考虑拆分 |
| 副作用集中 | 仅 `commit_filesystem` 写盘；其它步骤纯计算 |
| 配置驱动 | 路径、正则、字段顺序优先走配置，避免代码硬编码 |
| 字符串安全 | 所有 path 拼接走 `pathlib.Path`，不用字符串相加 |
| 错误信息 | 每个 PublishError 子类构造时附下一步建议 |
| 时区 | `datetime.now().astimezone()` 取本地时区，输出带 offset |
| Unicode | 全程 utf-8；草稿/post/路径可含中文；测试覆盖中文文件名 |
| 字段顺序 | `FIELD_ORDER` 常量驱动 front matter 序列化，不依赖 dict 插入序 |
