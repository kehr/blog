# Step 8: Makefile 集成与真实草稿冒烟测试

## 任务目标

把 `publish.py` 接入 Makefile（`publish` / `publish-list` / `publish-check` / `test-publish` 四个 target），删除被替代的 `scripts/publish-post.sh`，用真实草稿 `_drafts/如何设计一个好的Skill.md` 跑一遍 dry-run 与正式发布，验证端到端。这一步是用户验收闭环的最后一公里。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `Makefile` | 修改。替换 `publish` target，新增 `publish-list` / `publish-check` / `test-publish` |
| `scripts/publish-post.sh` | 删除 |
| `_drafts/如何设计一个好的Skill.md` | 不修改源文件；冒烟测试在 worktree 内进行，验收阶段在主仓库重跑 |

## 设计依据

- PRD 2.1 / 2.3 用户故事（中文草稿主路径与 dry-run 路径）
- TRD 4.7 Makefile 完整 target 写法
- TRD 7 文件衔接表

## 验证标准

冒烟测试（worktree 内跑）：

1. `make publish-list` 列出 `_drafts/` 下文件含中文文件名，编码无乱码
2. `make publish-check file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"` 打印计划，不写盘、不删草稿
3. `make publish file="如何设计一个好的Skill" slug="how-to-design-a-good-skill"` 成功执行，PRD 7 验收清单 1-5 项全部满足
4. `make serve-drafts` 启动后浏览器访问该 post URL 渲染正常，图片可见
5. `make test-publish` 全绿
6. 故意构造一个含 `---` 的草稿，跑 publish 应被拒绝
7. 故意传一个非法 slug（含大写或中文），跑 publish 应被拒绝
8. 删除 `scripts/publish-post.sh` 后，原 `make publish` 行为已被新实现替代，不存在残留引用

工作流验收（主仓库验收阶段，由用户完成）：

9. worktree 内 rebase origin/main 干净
10. 主仓库 `git merge --ff-only feature/draft-publisher` 成功
11. 主仓库重跑步骤 1-7 通过
12. 主仓库 `git push origin main` 后清理 worktree 与分支

## 依赖

Step 7 完成。

## 提交

完成后 commit：`integrate publish pipeline into makefile and remove legacy shell script`

随后由执行者更新 `docs/reports/draft-publisher-execution-report.md` 标记全部 step 完成，等待用户在主仓库验收。
