# Step 1: 配置与错误类型

## 任务目标

搭建 publish.py 的基础设施：错误类型层级、`PublishConfig` 数据类与 YAML 加载、默认配置文件、Python 依赖声明、`.gitignore` 更新。这一步不实现业务逻辑，只把脚手架立起来，让后续 step 有可依赖的类型。

## 涉及文件

| 路径 | 操作 |
|-----|------|
| `scripts/publish.py` | 新建。仅含错误类、PublishConfig、模块入口 stub |
| `scripts/test_publish.py` | 新建。包含 PublishConfig.from_yaml 的快乐路径 + YAML 解析失败用例 |
| `scripts/requirements.txt` | 新建。`PyYAML>=6.0` |
| `scripts/requirements-dev.txt` | 新建。引用 requirements.txt + `pytest>=7.0` |
| `_data/publish.yml` | 新建。按 PRD 3.3 写默认值 |
| `.gitignore` | 修改。追加 `__pycache__/` 与 `.pytest_cache/` |

## 设计依据

- PRD 3.3 默认配置 schema
- TRD 2.2 PublishConfig
- TRD 2.4 错误类型
- TRD 6 依赖声明

## 验证标准

1. `python3 -m py_compile scripts/publish.py` 通过
2. `python3 -m pytest scripts/test_publish.py -v` 全绿
3. 故意在 `_data/publish.yml` 写一个语法错误后跑测试，应触发 `ConfigParseError` 用例
4. `_data/publish.yml` 的字段命名与 PRD 3.3 完全一致
5. `requirements.txt` 与 `requirements-dev.txt` 可被 `pip install -r` 解析
6. `.gitignore` 已含 `__pycache__/` 与 `.pytest_cache/`

## 依赖

无前置 step。可作为 worktree 创建后第一个 commit。

## 提交

完成后 commit：`add publish config schema and error types`
