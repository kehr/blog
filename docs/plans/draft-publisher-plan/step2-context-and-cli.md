# Step 2: PublishContext 与 CLI 解析

## 任务目标

实现 `PublishContext` 数据类与 `parse_args` 函数。`parse_args` 完成 CLI 解析、slug 合法性校验、列表型参数的「逗号分隔 + 强制置空」语义。这一步打通主入口 `run(argv)` 的最外层流程，但不接业务步骤。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。增加 PublishContext、parse_args、parse_list、run 入口框架 |
| `scripts/test_publish.py` | 修改。覆盖 CLI 解析所有分支：必填缺失、slug 大写/中文/空、`--categories ""` 强制置空、`--list` 模式 |

## 设计依据

- PRD 3.2 CLI 接口完整参数表
- PRD 3.2 「字符串型参数显式空字符串视为强制置空」语义
- TRD 2.1 PublishContext 字段
- TRD 3.1 run() 入口流程
- TRD 4.6 CLI 解析约定

## 验证标准

1. `python3 scripts/publish.py --file foo --slug bar --dry-run` 解析成功（即便文件不存在，因为 load_draft 还未接，run 会在 stub 处早退；测试断言 ctx 字段值）
2. 测试覆盖：`--slug "Bad Slug"` 抛 `InvalidSlugError`
3. 测试覆盖：未传 `--file` 或 `--slug` 退出码非 0
4. 测试覆盖：`--categories "a, b ,c"` 解析为 `["a", "b", "c"]`
5. 测试覆盖：`--categories ""` 解析为 `[]`，`cli_categories` 为 `[]` 而非 `None`
6. 测试覆盖：未传 `--categories` 时 `cli_categories` 为 `None`
7. `--list` 模式调用 list_drafts 并打印 `_drafts/` 文件名清单（含中文）
8. lint 全绿

## 依赖

Step 1 完成（错误类型可用）

## 提交

完成后 commit：`add publish CLI parser and context`
