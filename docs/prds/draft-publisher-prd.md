# Draft Publisher PRD

## 1. 背景与目标

### 1.1 现状

博客采用 Jekyll + chirpy 主题，工作流为：

- 草稿写在 `_drafts/`，发布稿在 `_posts/YYYY-MM-DD-<slug>.md`
- 现有 `scripts/publish-post.sh` 只完成「移动 + 补 date」最小动作
- 草稿命名约束 ASCII slug，无法承载中文文件名草稿
- 草稿被要求自带完整 front matter，与「草稿专注内容」的诉求冲突

### 1.2 目标

构建一套草稿到发布稿的转换系统，使作者在草稿阶段只关注正文内容，所有 meta 信息在发布命令调用时由模板默认值与命令行参数自动补齐。同时解决文件改名、图片本地路径搬运等机械性工作。

### 1.3 非目标

- 不替代 Jekyll 构建本身（继续走 `make build` / `make serve`）
- 不接管 git 提交动作（publish 只移动文件，git commit 仍由作者显式执行）
- 不做正文内容的语义改写（与已有 `blogpost-style` 技能职责分离）
- 不替代 `scripts/new-post.sh`（创建草稿入口保持不变）

## 2. 用户故事

### 2.1 主路径：中文草稿发布

作者在 Obsidian 或 Typora 里写一篇标题为中文的笔记，文件名形如 `如何设计一个好的Skill.md`，正文里有若干粘贴自剪贴板的本地缓存图片（绝对路径）。完成写作后：

```
make publish file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"
```

期望产物：

- `_posts/2026-04-26-how-to-design-a-good-skill.md`，含完整 front matter
- `assets/img/posts/how-to-design-a-good-skill/<图片名>.png` 拷贝到位
- 草稿正文里图片链接被改写为站内路径
- `_drafts/如何设计一个好的Skill.md` 被删除

### 2.2 次要路径：覆盖默认 meta

作者写了一篇 AI 主题的文章，与默认分类 `Notes` 不一致：

```
make publish file="agent-harness-notes" slug="agent-harness-notes" \
             categories="Notes,AI" tags="agent,harness"
```

期望覆盖默认分类与标签，其余字段仍走默认值。

### 2.3 dry-run 预览

发布前预览将生成的 front matter 与图片搬运计划：

```
make publish-check file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"
```

期望只打印计划，不写盘、不删草稿。

## 3. 功能需求

### 3.1 草稿契约

| 项 | 要求 |
|----|------|
| Front matter | 草稿必须不含 `---` front matter；含则拒绝发布 |
| 文件名 | 允许任意 Unicode 字符，含中文/空格/标点 |
| 正文起始 | 允许首行为 `# 标题` 形式的 H1，也允许直接正文段落 |
| 图片引用 | 接受 `![alt](path)` 与 `<img src="path">` 两种形态；path 可为本地绝对路径、家目录路径、相对路径或远程 URL |

### 3.2 CLI 接口

主命令：

```
make publish file="<draft-name>" slug="<english-slug>" \
             [categories="A,B"] [tags="x,y,z"] \
             [image="/assets/img/foo.jpg"] [date="YYYY-MM-DD HH:MM"] \
             [src=_drafts] [dry-run=1]
```

辅助命令：

- `make publish-list`：列出 `_drafts/` 下所有草稿（含中文文件名）
- `make publish-check file=...`：等价于 `dry-run=1`

参数详细：

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `file` | 是 | - | 草稿文件名，带或不带 `.md` 都接受 |
| `slug` | 是 | - | 英文 slug，必须满足 `^[a-z0-9][a-z0-9-]*$` |
| `categories` | 否 | 配置默认 | 逗号分隔列表 |
| `tags` | 否 | 配置默认 | 逗号分隔列表 |
| `image` | 否 | 配置默认 | 封面图站内 URL |
| `date` | 否 | 当前本地时间 | 格式 `YYYY-MM-DD HH:MM` 或带秒 |
| `src` | 否 | `_drafts` | 草稿目录 |
| `dry-run` | 否 | 0 | 1 表示仅打印计划 |
| `force` | 否 | 0 | 1 时允许覆盖已存在的同名 post |

CLI 字符串型参数（categories / tags / image / description）未传时回退到默认；显式传入空字符串视为「强制置空」覆盖默认。

### 3.3 默认配置

新建 `_data/publish.yml`：

```yaml
defaults:
  categories:
    - Notes
  tags:
    - notes
  image:
    path: /assets/img/default.jpg
  description: ""

description:
  max_length: 160
  strip_markdown: true

images:
  posts_dir: assets/img/posts
  url_prefix: /assets/img/posts

posts_dir: _posts

validation:
  slug_pattern: "^[a-z0-9][a-z0-9-]*$"
  fail_on_existing_post: true
```

字段语义：

- `defaults.*`：未在 CLI 指定时使用的 front matter 默认值
- `defaults.description`：留空字符串时由脚本从首段自动提取
- `description.max_length`：自动提取的最大字符数（中文按 1 字符算）
- `description.strip_markdown`：开启时去除链接、粗体、斜体等标记
- `images.posts_dir`：图片目标根目录，`<posts_dir>/<slug>/` 为最终目录
- `images.url_prefix`：重写后图片 URL 的根路径
- `validation.fail_on_existing_post`：true 时同名 post 已存在直接拒绝

### 3.4 Front matter 生成规则

| 字段 | 来源 |
|------|------|
| `title` | 草稿文件名去掉 `.md` 后缀，原样保留 |
| `description` | CLI 未传时按以下规则提取：跳过开头空行 -> 若首行为 `# ` 起始的 H1 则跳过该行 -> 取下一个非空段落 -> 按 `description.strip_markdown` 清洗 -> 按 `description.max_length` 截断；若全文无非空段落则置为空字符串 |
| `date` | CLI `date` 参数；未传则取系统当前本地时间，格式 `YYYY-MM-DD HH:MM:SS +0800` |
| `categories` | CLI `categories` > `defaults.categories` |
| `tags` | CLI `tags` > `defaults.tags` |
| `image.path` | CLI `image` > `defaults.image.path` |

字段顺序固定为：title -> description -> date -> categories -> tags -> image，与现有 `_posts` 保持一致。

### 3.5 图片处理

扫描正文中所有图片引用：

| 路径形态 | 处理 |
|---------|------|
| 绝对路径（如 `/Users/...` 或 `~/...`） | 拷贝到 `<images.posts_dir>/<slug>/<basename>`，正文 URL 改写为 `<images.url_prefix>/<slug>/<basename>` |
| 相对路径（如 `./img/foo.png`） | 不动 |
| 远程 URL（http/https） | 不动 |

冲突处理：

- 目标目录已有同名文件，且内容哈希一致 -> 跳过拷贝，复用 URL
- 目标目录已有同名文件但内容不同 -> 报错，提示作者在草稿中重命名引用

### 3.6 文件命名

输出文件名规则：

```
<posts_dir>/<YYYY-MM-DD>-<slug>.md
```

其中 `YYYY-MM-DD` 取 `date` 字段的日期部分，`slug` 取 CLI 参数。

### 3.7 输出预览（dry-run）

```
draft : _drafts/如何设计一个好的Skill.md
post  : _posts/2026-04-26-how-to-design-a-good-skill.md (will create)
images:
  /Users/kyle/Library/Application Support/typora-user-images/image-20260425205116233.png
    -> assets/img/posts/how-to-design-a-good-skill/image-20260425205116233.png
front matter:
  title: 如何设计一个好的Skill
  description: 深度理解 ... (auto-extracted, 42 chars)
  date: 2026-04-26 14:32:10 +0800
  categories: [Notes]
  tags: [notes]
  image:
    path: /assets/img/default.jpg
```

## 4. 非功能需求

### 4.1 错误处理

所有错误 fail-fast，退出码非 0，错误信息输出到 stderr 并附下一步建议：

| 错误场景 | 行为 |
|---------|------|
| 草稿文件不存在 | 列出 `_drafts/` 实际有什么文件 |
| 草稿已含 `---` front matter | 拒绝，提示「草稿零 meta」契约 |
| slug 非法 | 提示正则规则与清洗建议 |
| 目标 post 已存在 | 拒绝（除非显式 `force=1`，默认拒绝） |
| 图片源路径不存在 | 列出所有缺失图片，停止 |
| 图片同名内容不同 | 提示重命名 |
| 配置文件 YAML 解析失败 | 指出行号 |
| 提取 description 为空 | 警告但不阻断 |

### 4.2 事务性写入

写盘顺序：

1. 拷贝所有图片到目标目录
2. 写入 post 文件
3. 删除草稿文件

回滚语义：

- 步骤 1 失败：回滚已拷贝的图片，post 不写，草稿不动
- 步骤 2 失败：回滚已拷贝的图片，草稿不动
- 步骤 3 失败（罕见，权限问题等）：post 与图片已写入成功视为发布成功，草稿保留并打印警告提示作者手动删除

任一步失败均不留半成品（草稿与 post 不能同时存在指向同一篇内容的状态）。

### 4.3 可观测性

| 模式 | 输出 |
|------|------|
| 默认 | 动作摘要（draft 路径 -> post 路径、N 张图） |
| `verbose=1` | 每步进入与返回值 |
| 错误 | stderr 输出 + 建议下一步 |

### 4.4 实现约束

- 实现语言：Python 3，仅依赖标准库 + PyYAML（项目已通过 Jekyll 间接依赖 PyYAML，但 Python 端单独安装）
- 单文件实现 `scripts/publish.py`，约 200-300 行
- 测试入口 `scripts/test_publish.py`，pytest 风格，可选依赖
- Makefile 提供 `make publish` / `make publish-list` / `make publish-check` / `make test-publish` 四个 target

## 5. 范围边界

### 5.1 本期内

- 单文件 `publish.py` 完成 9 步流水线
- `_data/publish.yml` 配置文件
- `assets/img/posts/<slug>/` 自动建目录与拷贝
- Makefile 集成 4 个 target
- pytest 测试套件覆盖快乐路径与关键边界
- 替换现有 `scripts/publish-post.sh`（删除）

### 5.2 本期外（明确不做）

- 自动 `git add` / `git commit`：保持 publish 是文件移动，git 操作仍由作者控制
- 校验 markdown 内部链接：已由 `make check` (htmlproofer) 承担
- 删除草稿原图源文件（如 Typora 缓存图）：脚本只读源图
- 多语言版本生成：当前博客单语言为主
- 草稿到草稿的反向操作（unpublish）：低频需求，本期不做

## 6. 决策记录

| 决策点 | 选择 | 理由 |
|-------|------|------|
| 草稿是否允许 front matter | 不允许 | 强约束「草稿专注内容」契约，避免漂移；含则拒绝并提示 |
| slug 来源 | CLI 显式传入 | 中文文件名无法机械翻译，避免机器翻译质量不可控 |
| title 来源 | 草稿文件名 | 与作者写作时的命名一致，最低心智负担 |
| description 来源 | 首段自动提取 + CLI 可覆盖 | 零额外工作，对 SEO 友好 |
| 默认配置组织 | 单一默认 + CLI 覆盖 | 个人博客无需多 profile，配置简单 |
| 图片本地绝对路径 | 自动拷贝到 assets 并重写链接 | 完全自动化、可重构 |
| 实现语言 | Python | YAML 与正则处理远比 bash 健壮，避免 quoting 地狱 |
| 架构形态 | 单文件 publish.py | 个人博客需求清晰，模块化包过度设计 |
| Jekyll 插件方案 | 不采用 | YYYY-MM-DD-slug 改名是硬性副作用，应是显式 publish 动作 |

## 7. 验收标准

发布后应满足以下全部条件：

1. `make publish file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"` 成功执行
2. `_posts/2026-04-26-how-to-design-a-good-skill.md` 生成，front matter 字段顺序与既有 post 一致
3. `assets/img/posts/how-to-design-a-good-skill/` 目录存在并包含原草稿引用的全部本地图片
4. 生成的 post 中图片链接已改写为 `/assets/img/posts/how-to-design-a-good-skill/<basename>`
5. `_drafts/如何设计一个好的Skill.md` 被删除
6. `make serve` 启动后该篇 post 在浏览器中正常渲染、图片可见
7. `make publish-check ...` 仅打印计划，不写盘、不删草稿
8. `make test-publish` 全绿，覆盖第 5 节测试矩阵中标记的全部用例
9. 草稿包含 `---` front matter 时 publish 命令拒绝并打印契约提示
10. slug 大写或含中文时 publish 命令拒绝并打印正则规则
