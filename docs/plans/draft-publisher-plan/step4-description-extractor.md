# Step 4: Description 自动提取

## 任务目标

实现 `extract_description` 与辅助函数 `strip_markdown_inline`，按 PRD 3.4 规则从草稿正文提取首段作为 description。CLI 显式传入 description 时跳过提取（含「强制置空」语义）。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。新增 extract_description + strip_markdown_inline |
| `scripts/test_publish.py` | 修改。覆盖 description 提取所有分支 |

## 设计依据

- PRD 3.3 description.max_length / description.strip_markdown
- PRD 3.4 description 来源规则（跳空行、跳 H1、首段、清洗、截断）
- PRD 4.1 提取为空时警告但不阻断
- TRD 3.2 extract_description 签名
- TRD 4.3 提取算法伪代码

## 验证标准

1. 测试覆盖：草稿首行 `# 标题`，第二行空行，第三行段落 -> description 为第三行清洗后内容
2. 测试覆盖：草稿无 H1，直接从首段提取
3. 测试覆盖：连续多行非空段落 -> 拼接为一行（空格连接）
4. 测试覆盖：超长段落按 `max_length` 截断且 rstrip
5. 测试覆盖：strip_markdown 开启时去链接/粗体/斜体/行内代码
6. 测试覆盖：草稿仅含 H1 与图片 -> description 为空字符串，stderr 给警告
7. 测试覆盖：CLI `--description "x"` 时跳过提取，ctx.description == "x"
8. 测试覆盖：CLI `--description ""` 时强制置空，ctx.description == ""
9. lint 全绿

## 依赖

Step 3 完成。串行执行，下一步为 Step 5。

## 提交

完成后 commit：`add description extractor`
