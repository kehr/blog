# Step 3: 草稿读取与 title 解析

## 任务目标

实现 `load_draft` 与 `resolve_title` 两个流水线步骤。`load_draft` 读取草稿文件并强制校验「零 front matter」契约；`resolve_title` 把草稿文件名（去 .md）写入 `ctx.title`，原样保留中文。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。新增 load_draft 与 resolve_title |
| `scripts/test_publish.py` | 修改。覆盖以下分支 |

## 设计依据

- PRD 3.1 草稿契约（必须无 front matter）
- PRD 3.4 title 字段来源
- TRD 3.2 load_draft / resolve_title 签名
- TRD 8 字符串安全（pathlib.Path）

## 验证标准

1. 测试覆盖：草稿文件不存在 -> `DraftNotFoundError`，错误信息含 `_drafts/` 实际清单
2. 测试覆盖：草稿首行是 `---` -> `DraftHasFrontMatterError`，错误信息提示「草稿零 meta」契约
3. 测试覆盖：草稿前有 BOM 或多个空行后才到 `---` -> 仍判定为含 front matter（避免误漏）
4. 测试覆盖：草稿文件名为 `如何设计一个好的Skill.md` -> `ctx.title == "如何设计一个好的Skill"`
5. 测试覆盖：草稿文件名含空格、英文混排 -> 原样保留
6. 测试覆盖：CLI 传入 `--file` 时不带 `.md` 与带 `.md` 都能正确定位文件
7. lint 全绿

## 依赖

Step 2 完成。串行执行，下一步为 Step 4。

## 提交

完成后 commit：`add draft loader and title resolver`
