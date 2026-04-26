# Step 7: 组装与事务性写盘

## 任务目标

实现 `assemble_post`（拼 front matter + rewritten_body 得到最终 post 文本，并算出 `target_post_path`）与 `commit_filesystem`（按 PRD 4.2 顺序拷贝图片、写 post、删草稿，任一步失败回滚）。同步打通 `run()` 主入口，把前面 8 个步骤串起来端到端可跑。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。新增 assemble_post、commit_filesystem、print_plan、`__main__` 入口 |
| `scripts/test_publish.py` | 修改。新增端到端集成用例 + 事务回滚用例 |

## 设计依据

- PRD 3.6 文件命名 `<posts_dir>/YYYY-MM-DD-<slug>.md`
- PRD 3.7 dry-run 输出格式
- PRD 4.2 事务性写盘三步顺序与回滚语义
- PRD 4.1 「目标 post 已存在」与「force=1」交互
- TRD 3.2 assemble_post / commit_filesystem 签名
- TRD 4.4 commit_filesystem 伪代码

## 验证标准

1. 端到端测试：构造 `_drafts/test.md`（中文文件名 `测试草稿.md`）、`_data/publish.yml`、本地 png 文件，调用 `run` 后 `_posts/<date>-<slug>.md` 存在、`assets/img/posts/<slug>/` 存在、草稿被删除
2. 端到端测试：dry-run 模式仅打印计划，不写任何文件、不删草稿；stdout 含 PRD 3.7 示例的全部段落
3. 端到端测试：`fail_on_existing_post: true` 且目标存在时拒绝；传 `--force` 时覆盖
4. 回滚测试：mock `shutil.copy2` 在第 2 张图片时抛异常 -> 第 1 张已拷贝的图片被删除，post 未写，草稿仍在
5. 回滚测试：mock `Path.write_text` 抛异常 -> 全部图片被删除，草稿仍在
6. 回滚测试：mock `Path.unlink`（删草稿）抛异常 -> post 与图片仍在，stderr 给警告，退出码为 0（视为发布成功）
7. lint 全绿，整套测试套件全绿

## 依赖

Step 6 完成。

## 提交

完成后 commit：`add transactional commit and pipeline integration`
