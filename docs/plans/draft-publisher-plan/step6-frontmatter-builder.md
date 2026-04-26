# Step 6: Front matter 构建与序列化

## 任务目标

实现 `build_frontmatter` 与 `serialize_frontmatter`：按字段顺序常量 `FIELD_ORDER` 拼装 front matter 字典，再手工序列化为 YAML 文本（不依赖 yaml.safe_dump 以保证字段顺序与既有 post 一致）。同时实现 `_yaml_quote` 处理特殊字符。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。新增 build_frontmatter、serialize_frontmatter、_yaml_quote、FIELD_ORDER 常量 |
| `scripts/test_publish.py` | 修改。覆盖 front matter 生成与序列化全部分支 |

## 设计依据

- PRD 3.4 front matter 字段来源与覆盖优先级（CLI > 默认）
- PRD 3.4 字段顺序固定
- TRD 3.2 build_frontmatter 签名
- TRD 4.1 serialize_frontmatter 与 FIELD_ORDER 常量
- TRD 8 字段顺序由常量驱动

## 验证标准

1. 测试覆盖：未传 CLI 时各字段取自 PublishConfig 默认值
2. 测试覆盖：CLI 传 `categories` 覆盖默认；传 `--categories ""` 写入空列表
3. 测试覆盖：date 字段格式化为 `YYYY-MM-DD HH:MM:SS +0800` 形式（带本地时区 offset）
4. 测试覆盖：image 字段序列化为嵌套 `image:\n  path: "..."` 结构
5. 测试覆盖：title/description 含冒号、井号、引号时正确加引号
6. 测试覆盖：序列化结果以 `---` 起止，每行一个字段，列表项缩进两空格
7. 测试覆盖：序列化结果与 `_posts/2026-04-19-agent-engineering-with-harness.md` 的 front matter 风格一致（字段顺序、缩进、引号风格）
8. lint 全绿

## 依赖

Step 5 完成。串行执行，下一步为 Step 7。

## 提交

完成后 commit：`add frontmatter builder and serializer`
