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
| Step 5: 图片处理 | pending | - | - | - |
| Step 6: Front matter 构建 | pending | - | - | - |
| Step 7: 组装与事务写盘 | pending | - | - | - |
| Step 8: Makefile 与冒烟 | pending | - | - | - |

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

## 5. 已记录但未修复的观察项

| # | 来源 | 观察 | 后续处理时机 |
|---|------|------|-------------|
| 1 | Step 2 code review | `PublishContext.target_post_path` 默认 `Path('.')`（truthy），后续若用 `if ctx.target_post_path` 判断会误命中 | Step 7 实现 assemble_post 时改为 `Optional[Path] = None` 并显式赋值 |
| 2 | Step 2 code review | `_DATE_FORMATS` 不接受带 TZ 后缀的输入（如 `2026-04-26 14:00+08:00`） | 暂不扩展；若用户反馈再加。已在 PRD 限制为 `YYYY-MM-DD HH:MM` |
| 3 | Step 2 spec review | PRD 3.2 参数表未单列 `--description`（PRD 写作疏漏，正文已说明） | Step 8 验收前回头补 PRD 表格 |
| 4 | Step 2 code review | `publish.py:141` 注释 "Step 7 can make this config-driven" 是阶段性备注 | Step 7 完成后清理 |
| 5 | Step 3 spec review | `load_config` 未提取为独立函数（TRD 3.2 单列）；run() 中内联调用 from_yaml | Step 7 集成时重构为独立函数，便于测试与未来 mock |
| 6 | Step 3 code review | `run()` 中 `src_dir.parent` 推导 repo root 是隐含假设，子目录 src 会出错 | Step 7 加注释显式化或改为从 ctx 携带 repo_root |
| 7 | Step 3 code review | 缺 CRLF 草稿测试覆盖 | Step 7 端到端测试时补一个 CRLF 用例 |
| 8 | Step 3 code review | `DraftNotFoundError` suggestion 未截断长草稿清单 | 若用户反馈再加 `available[:10] + N more` |
| 9 | Step 4 re-review | 链接正则只支持一层括号嵌套（`a_(b_(c))` 无法匹配） | 已在代码注释声明限制；博客 URL 罕见，不扩展 |

## 6. 无法决策项（等待用户验收时确认）

（首次执行，暂无）

## 7. Review 结果

### 7.1 Spec compliance

待全部 step 完成后填写。

### 7.2 Code quality

待全部 step 完成后填写。

## 8. 验收记录

待用户在主仓库 ff-merge 验收后填写。
