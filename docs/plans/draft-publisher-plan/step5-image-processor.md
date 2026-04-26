# Step 5: 图片扫描与重写

## 任务目标

实现 `process_images`：扫描草稿正文中的 markdown 图片与 HTML img 标签，按路径形态分类，对绝对路径生成 `ImageMove` 拷贝计划并改写正文中的链接。本 step 仅生成计划与重写文本，不实际拷贝（拷贝在 Step 7 commit_filesystem）。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 修改。新增 process_images、classify_path、hashes_equal、扫描正则常量 |
| `scripts/test_publish.py` | 修改。覆盖图片处理全部分支 |

## 设计依据

- PRD 3.5 图片处理路径分类与冲突规则
- TRD 2.3 ImageMove 数据结构
- TRD 3.2 process_images 签名（不写盘）
- TRD 4.2 MD_IMG / HTML_IMG 正则与 classify_path
- TRD 4.5 hashes_equal

## 验证标准

1. 测试覆盖：`![alt](/Users/x/foo.png)` -> 计划生成且正文链接重写为 `/assets/img/posts/<slug>/foo.png`
2. 测试覆盖：`![alt](~/dir/img.png)` -> 展开 `~` 后处理
3. 测试覆盖：`![alt](./local/img.png)` 与 `![alt](https://x/img.png)` -> 不动
4. 测试覆盖：`<img src="/abs/foo.jpg" width="200">` -> 同样处理
5. 测试覆盖：图片源不存在 -> `ImageSourceMissingError`，错误信息列出全部缺失图片
6. 测试覆盖：草稿引用同一图片多次 -> 只生成一条 ImageMove，全部链接同步重写
7. 测试覆盖：目标 `assets/img/posts/<slug>/foo.png` 已存在且哈希一致 -> ImageMove.skip_copy=True
8. 测试覆盖：目标已存在但哈希不同 -> `ImageNameConflictError`
9. 测试覆盖：图片 alt 含空格、URL 后含 title 文本 `![](path "title")` -> 仍能正确提取 path
10. lint 全绿

## 依赖

Step 4 完成。串行执行，下一步为 Step 6。

## 提交

完成后 commit：`add image scanner and link rewriter`
