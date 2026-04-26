# Draft Publisher 执行报告

## 1. 执行元数据

| 项 | 值 |
|----|-----|
| 启动时间 | 2026-04-26 |
| 主仓库 | /Users/kyle/Studio/blog |
| Worktree | .claude/worktrees/draft-publisher |
| 分支 | feature/draft-publisher |
| 验收方式 | 主仓库 ff-merge 验收，验收通过 push origin main |
| 派发模式 | subagent-driven-development，全部 step 串行 |
| PRD | docs/prds/draft-publisher-prd.md |
| TRD | docs/trds/draft-publisher-trd.md |
| Plan 索引 | docs/plans/draft-publisher-plan.md |
| Plan steps | docs/plans/draft-publisher-plan/step1..step8 |

## 2. 全局规则

| 规则 | 应用方式 |
|------|---------|
| 零 AI 痕迹 | 提交信息、注释、配置不含 AI/Claude/Anthropic 关键词；分支名 feature/draft-publisher |
| Lint | 每 step 完成跑 `python3 -m py_compile` + `python3 -m pytest`，全绿才进入下一 step |
| 单文件冲突 | 全部 step 改同文件，串行执行避免冲突 |
| 测试先行 | TDD 节奏：失败用例 -> 实现 -> 通过 |
| 文档语言 | 文档中文，代码注释与日志英文 |
| Emoji | 全程禁用 |
| Worktree 边界 | dev 环境与 lint 工具均在 worktree 内可用，验收前 worktree rebase origin/main |

## 3. Step 实施进度

| Step | 状态 | Commit | 关键决策与偏差 | 跳到 |
|------|------|--------|---------------|------|
| Step 0: docs/draft 落地 | completed | 20b0902 | PRD/TRD/Plan/执行报告/草稿夹具一并入栈 | - |
| Step 1: 配置与错误类型 | completed | c47af22 | TDD 节奏；30 个测试全绿；PyYAML API 对照 dir(yaml) 确认 | - |
| Step 2: PublishContext 与 CLI | completed | aeac0b1 | TDD 全绿 (80/80)；`-abc` slug 被 argparse 拦在 SystemExit(2)，测试接受 `(InvalidSlugError, SystemExit)` 两种拒绝形式；parse_args 返回 Optional[PublishContext]，None 表示 --list 模式已处理；argparse API 通过 `dir()` 与 `help()` 验证 | - |
| Step 3: 草稿读取与 title | completed | beb5677 | TDD 节奏；新增 17 个测试，总计 97/97 全绿；BOM 剥离用 `lstrip("﻿")` 而非 `.lstrip("﻿")`（字面量等价，两者均可）；`load_draft` 仅检查首个非空行是否 `---`，正文中间的水平分隔线不触发拒绝；`resolve_title` 直接用 `Path.stem`，原样保留中文/空格/混排标点；`run()` 接入 `load_draft` + `resolve_title`，config 路径由 `ctx.src_dir.parent / "_data" / "publish.yml"` 推导，与任意 cwd 无关 | - |
| Step 4: Description 提取 | completed | bbdbc50 | TDD 节奏；新增 42 个测试（共 139/139 全绿）；strip_markdown_inline 按 TRD 4.3 顺序：链接 -> 行内代码 -> 星号序列 -> 下划线序列；extract_description 四优先级：CLI 显式值 -> config default -> 自动提取 -> 空值警告；截断用 `len(text)` 即字符数，中文单字符一位符合规范；run() 中 resolve_title 后紧接 extract_description | - |
| Step 5: 图片处理 | completed | f1bcfa1 | TDD 节奏；新增 39 个测试（共 188/188 全绿）；ImageMove dataclass 置于 PublishConfig 之后；MD_IMG 用 [^)\s]+ 排除空白与右括号，HTML_IMG 用 re.IGNORECASE；classify_path 三分支（remote/absolute/relative）；hashes_equal 用 sha1 流式比较；process_images 两轮扫描：第一轮累积 missing 列表与 seen_source 去重；第二轮 re.sub 回调仅替换 path 部分保留 alt/title/attributes；~ 路径用 os.path.expanduser 展开后 Path.resolve()；run() 在 extract_description 后紧接 process_images | - |
| Step 6: Front matter 构建 | completed | 1f038f8 | TDD 节奏；新增 65 个测试（共 257/257 全绿）；FIELD_ORDER 常量驱动字段顺序；_yaml_quote 检测 ASCII 冒号/井号/引号/反斜杠/前导特殊字符/YAML 关键词/纯数字；全角冒号 U+FF1A 不是 YAML 结构字符，可裸值输出，与真实 post 风格一致；build_frontmatter 严格按 CLI > config default 优先级；serialize_frontmatter 手工拼装，不依赖 yaml.dump | - |
| Step 7: 组装与事务写盘 | completed | 331085b | TDD 节奏；新增 21 个测试（共 280/280 全绿）；assemble_post 保证 front matter 与正文之间恰好一个换行；commit_filesystem 三步事务写盘，步骤 1-2 异常触发回滚，步骤 3 失败仅 stderr 警告；print_plan 全部输出到 stdout；load_config 提取为独立函数并赋值 ctx.repo_root；PublishContext 新增 repo_root / assembled_text 字段，target_post_path 改为 Optional[Path] = None；观察项 1/4/5/6/7 全部处理 | - |
| Step 8: Makefile 与冒烟 | completed | f33dd29 | Makefile 新增 publish/publish-list/publish-check/test-publish target；删除 scripts/publish-post.sh；PRD 3.2 补 --description 参数行；冒烟全 7 步通过；发现并修复 BUG-6（MD_IMG 正则不匹配含空格路径），新增 3 个测试，总计 283/283 全绿 | - |

## 4. 已修复问题

### BUG-1: 下划线正则破坏 snake_case 标识符

- 原现象：`re.sub(r"_{1,2}([^_]+)_{1,2}", ...)` 无边界断言，导致 `snake_case_name` -> `snakecasename`
- 修复方案：添加 `(?<!\w)` / `(?!\w)` 边界断言，只在下划线前后均为非单词字符时触发
- 修复后验证：`test_preserves_snake_case`、`test_preserves_path_underscores` 两个回归测试通过；原有 `_emphasis_` / `__strong__` 用例不受影响
- commit: 4ef08e8

### BUG-2: 链接正则在 URL 含括号时留下残余 `)`

- 原现象：`re.sub(r"\[([^\]]+)\]\([^)]+\)", ...)` 在遇到 `[anchor](https://x/wiki/Foo_(bar))` 时，`[^)]+` 止步于内层 `)`，导致结果为 `anchor)` 而非 `anchor`
- 修复方案：将 URL 部分改为 `[^()]*(?:\([^()]*\)[^()]*)*`，允许 URL 中含一层嵌套括号
- 修复后验证：`test_link_with_parens_in_url` 和 `test_simple_link_still_works` 两个回归测试通过
- commit: 4ef08e8

### BUG-3: 混合 bold/italic 留下残余星号

- 原现象：`re.sub(r"\*{1,3}([^*]+)\*{1,3}", ...)` 以不确定长度匹配开闭符，`**a*b**` 中 `[^*]+` 无法跨越 `*`，最终产生 `ab**` 残余
- 修复方案：拆为三条独立正则按长度倒序（三星 -> 双星 -> 单星）；双星正则使用 `(.+?)` 允许内容含单个 `*`，并配合 `(?!\*)` / `(?<!\*)` 防止误吃三星边界
- 修复后验证：`test_mixed_bold_italic_no_double_asterisk_residue`、`test_triple_asterisk_only`、`test_double_asterisk_only`、`test_single_asterisk_only` 全部通过；原有 bold/italic 组合测试无回归
- commit: 4ef08e8

### BUG-4: str.replace 在 alt == path 时误命中 alt 文字

- 原现象：`![/abs/foo.png](/abs/foo.png)` 中 `original.replace(raw_path, new_url, 1)` 替换第一次出现，而第一次是 alt 文字（`[` 与 `(` 之间），导致 alt 被改、src 未改、图片失效
- 修复方案：提取 `_rewrite_via_span` helper，用 `m.span("path")` 获取捕获组的字符区间，基于字符串切片仅替换 path 组覆盖的区间，完全不依赖 `str.replace`
- 修复后验证：`TestRewriteMdAltEqualsPath::test_src_rewritten_not_alt` 通过；`TestRewriteHtmlAltEqualsPath::test_src_rewritten_alt_unchanged` 通过；全部 192 个测试通过
- commit: 913ad04

### BUG-5: images_posts_dir 配置为绝对路径时静默丢失 repo_root

- 原现象：`repo_root / config.images_posts_dir / ctx.slug / basename` 在 `images_posts_dir` 为绝对路径时，Python pathlib `__truediv__` 丢弃左侧前缀，文件写入错误位置且无报错
- 修复方案：在 `PublishConfig.from_yaml` 中，解析 `images_posts_dir` 后立即检查 `Path.is_absolute()`，若为绝对路径抛 `ConfigParseError`，message 含 "must be relative"，suggestion 引导用户改用相对路径
- 修复后验证：`TestConfigRejectsAbsoluteImagesPostsDir::test_absolute_posts_dir_raises` 通过；已有配置文件（`assets/img/posts` 相对路径）不受影响
- commit: 913ad04

### BUG-6: MD_IMG 正则不匹配含空格的绝对路径

- 发现时机：Step 8 冒烟测试；真实草稿引用 Typora 缓存图 `/Users/kyle/Library/Application Support/typora-user-images/...`，路径含空格
- 原现象：`MD_IMG` 正则中 `path` 捕获组为 `[^)\s]+`，空格视为终止符，导致路径被截断，图片被误分类为 relative 而非 absolute，dry-run 输出 `images:` 段为空
- 修复方案：将 `path` 捕获组改为 `[^)\"]+?`（非贪婪），允许路径含空格，仅在右括号和双引号处终止
- 修复后验证：新增 3 个测试（`TestProcessImagesMdPathWithSpaces`）全部通过；原 280 个测试无回归；冒烟 dry-run 正确识别图片并输出搬运计划；283/283 全绿
- commit: f33dd29

## 5. 已记录但未修复的观察项

| # | 来源 | 观察 | 后续处理时机 |
|---|------|------|-------------|
| 1 | Step 2 code review | `PublishContext.target_post_path` 默认 `Path('.')`（truthy），后续若用 `if ctx.target_post_path` 判断会误命中 | √ Step 7 已修复：改为 `Optional[Path] = None` 并在 assemble_post 显式赋值 |
| 2 | Step 2 code review | `_DATE_FORMATS` 不接受带 TZ 后缀的输入（如 `2026-04-26 14:00+08:00`） | 暂不扩展；若用户反馈再加。已在 PRD 限制为 `YYYY-MM-DD HH:MM` |
| 3 | Step 2 spec review | PRD 3.2 参数表未单列 `--description`（PRD 写作疏漏，正文已说明） | √ Step 8 已修复：PRD 3.2 表格新增 `--description` 行 |
| 4 | Step 2 code review | `publish.py:141` 注释 "Step 7 can make this config-driven" 是阶段性备注 | √ Step 7 已清理：注释已删除 |
| 5 | Step 3 spec review | `load_config` 未提取为独立函数（TRD 3.2 单列）；run() 中内联调用 from_yaml | √ Step 7 已修复：提取为独立函数 `load_config(ctx)` |
| 6 | Step 3 code review | `run()` 中 `src_dir.parent` 推导 repo root 是隐含假设，子目录 src 会出错 | √ Step 7 已修复：PublishContext 加 `repo_root` 字段，load_config 赋值，process_images 读 ctx.repo_root |
| 7 | Step 3 code review | 缺 CRLF 草稿测试覆盖 | √ Step 7 已修复：`test_e2e_crlf_draft` 端到端测试覆盖 CRLF 行尾 |
| 8 | Step 3 code review | `DraftNotFoundError` suggestion 未截断长草稿清单 | 若用户反馈再加 `available[:10] + N more` |
| 9 | Step 4 re-review | 链接正则只支持一层括号嵌套（`a_(b_(c))` 无法匹配） | 已在代码注释声明限制；博客 URL 罕见，不扩展 |

## 6. 无法决策项（等待用户验收时确认）

（首次执行，暂无）

## 7. Review 结果

### 7.1 Spec compliance

全部 8 个 step 完成。对照 PRD 验收标准（7 节 10 条）：

| 条目 | 验证结果 |
|------|---------|
| 1. make publish 成功执行 | pass - 冒烟测试 c 通过，退出码 0 |
| 2. post 生成，front matter 字段顺序正确 | pass - head -25 输出确认字段顺序 title/description/date/categories/tags/image |
| 3. assets/img/posts/<slug>/ 含原图 | pass - image-20260425205116233.png 已拷贝 |
| 4. post 中图片链接改写为站内路径 | pass - 正文图片 URL 改为 /assets/img/posts/how-to-design-a-good-skill/... |
| 5. draft 被删除 | pass - _drafts/ 为空（smoke 后已还原） |
| 6. make serve 渲染（浏览器） | 待用户主仓库验收 |
| 7. publish-check 仅打印计划，不写盘 | pass - dry-run 输出四段，草稿未删除 |
| 8. test-publish 全绿 | pass - 283/283 |
| 9. 含 front matter 草稿拒绝 | pass - 冒烟测试 e，退出码 2，提示零 meta 契约 |
| 10. 非法 slug 拒绝 | pass - 冒烟测试 f，退出码 2，提示正则规则 |

### 7.2 Code quality

- 单文件 publish.py 约 760 行，含完整 docstring 和类型注解
- 零外部依赖（除 PyYAML）
- 事务写盘有回滚语义
- 所有错误路径有 suggestion 字段
- 283 个测试覆盖快乐路径与关键边界

## 8. 验收记录

待用户在主仓库 ff-merge 验收后填写。
