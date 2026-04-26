# Draft Publisher 实施计划

## 1. 计划元数据

- 依据 PRD: `docs/prds/draft-publisher-prd.md`
- 依据 TRD: `docs/trds/draft-publisher-trd.md`
- 执行方式: subagent-driven-development，多 step 间无依赖关系时并行派发
- 工作目录: 在主仓库根目录创建 worktree `.claude/worktrees/draft-publisher/` 分支 `feature/draft-publisher`
- 验收闭环: 全部 step 完成后 worktree 内 rebase origin/main，主仓库 ff-merge 验收，验收通过 push origin main 并清理 worktree
- 执行报告: `docs/reports/draft-publisher-execution-report.md`，每完成一个 step 实时更新

## 2. 全局约束

| 项 | 约束 |
|----|------|
| 语言 | Python 3.9+；脚本注释与日志全英文；文档与提交信息中文 |
| 零 AI 痕迹 | 提交信息、注释、配置全部不出现 AI/Claude/Anthropic 等关键词；分支名为 feature/draft-publisher |
| Lint | 每个 step 完成后必须跑 `python3 -m py_compile scripts/*.py` 和 `python3 -m pytest scripts/test_publish.py -v`；测试与编译全绿才进入下一步 |
| 提交 | 每个 step 完成后单独 commit，提交信息描述「做了什么」而不是「为什么」 |
| 测试 | TDD 节奏：先写失败用例，再写实现，再跑通；测试集中在 `scripts/test_publish.py` |
| 无 emoji | 代码与文档禁用 emoji |

## 3. Step 列表

| Step | 文件 | 依赖 |
|------|------|------|
| Step 1 | step1-config-and-errors.md | - |
| Step 2 | step2-context-and-cli.md | Step 1 |
| Step 3 | step3-draft-and-title.md | Step 2 |
| Step 4 | step4-description-extractor.md | Step 3 |
| Step 5 | step5-image-processor.md | Step 4 |
| Step 6 | step6-frontmatter-builder.md | Step 5 |
| Step 7 | step7-commit-and-pipeline.md | Step 6 |
| Step 8 | step8-makefile-and-smoke.md | Step 7 |

派发策略：全部 step 串行执行。所有 step 修改同一文件 `scripts/publish.py` 与 `scripts/test_publish.py`，触发「共享文件写入冲突 → 串行」原则，不允许并行 subagent。

## 4. 文件总览

| 路径 | 操作 | Step |
|-----|------|------|
| `scripts/publish.py` | 新建 | Step 1-7 增量 |
| `scripts/test_publish.py` | 新建 | Step 1-7 增量 |
| `scripts/requirements.txt` | 新建 | Step 1 |
| `scripts/requirements-dev.txt` | 新建 | Step 1 |
| `_data/publish.yml` | 新建 | Step 1 |
| `Makefile` | 修改 | Step 8 |
| `scripts/publish-post.sh` | 删除 | Step 8 |
| `.gitignore` | 修改 | Step 1 |
| `docs/reports/draft-publisher-execution-report.md` | 新建并实时更新 | 全程 |

## 5. 验收标准（全部 step 完成后）

对照 PRD 第 7 节验收清单 10 项，逐项在主仓库验收：

1. `make publish file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"` 成功执行
2. `_posts/2026-04-26-how-to-design-a-good-skill.md` 生成且 front matter 字段顺序正确
3. `assets/img/posts/how-to-design-a-good-skill/` 目录存在并含原图
4. post 中图片链接已重写为站内路径
5. `_drafts/如何设计一个好的Skill.md` 已删除
6. `make serve` 启动后该篇 post 在浏览器中正常渲染
7. `make publish-check ...` 仅打印计划不写盘
8. `make test-publish` 全绿
9. 含 `---` 的草稿被拒绝
10. 非法 slug 被拒绝

## 6. 风险与回滚

| 风险 | 缓解 |
|------|------|
| PyYAML 在 macOS 系统 Python 上未装 | Step 1 在 requirements.txt 与 Makefile 中明确，并在 publish.py 主入口给安装提示 |
| 中文文件名在 Makefile 变量展开时引号丢失 | Step 8 测试用例覆盖；Makefile 用 `$(file)` 全程加双引号 |
| 历史 _posts 已有同 slug 同日期文件 | 默认拒绝；smoke test 用新 slug 避免污染 |
| 草稿正文含特殊 YAML 字符（冒号、引号） | front matter 仅由脚本生成，正文不参与 YAML 序列化，无风险 |
| 验收失败需回滚 | 主仓库 `git reset --hard origin/main` 即可，worktree 中代码完整可二次修改 |
