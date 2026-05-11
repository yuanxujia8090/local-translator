# AGENTS.md — Local-Translator

## 安装与运行

```bash
uv sync                          # 安装依赖（需要 Python 3.13）
uvicorn app:app --reload --host 0.0.0.0 --port 8780
```

测试：`pytest`（无需子命令）。需要 oMLX mock — 测试中 patch 了 `requests.post`，不需要真实的模型服务。

## 配置

`config.json` 是唯一配置来源 — `app.py` 和 `translate.py` 都在导入时读取它。修改后需要重启服务。关键字段：

- `omlx.*` — host、port（默认 8050）、模型名、temperature、max_tokens
- `server.port` — FastAPI 端口（默认 8780）
- `history_limit` — 最大保存翻译数（默认 20）

## 架构

```
app.py          # FastAPI — 路由、请求/响应模型、历史记录管理
translate.py    # 翻译逻辑 — 构建带 <start_of_turn>/<end_of_turn> token 的 prompt，调用 oMLX /v1/completions
config.json     # 全部运行时配置（导入时读取）
templates/index.html  # 单页前端，无需构建步骤
```

关键细节：`translate.py` 使用 `/v1/completions`（不是 chat/completions）。prompt 格式必须包含 `<start_of_turn>` / `<end_of_turn>` token 以适配 TranslateGemma。参考 `check-omlx.py`。

## 测试注意事项

- 测试使用 `fake_config` fixture 创建临时 `config.json`，并清除 `sys.modules["app"]` / `sys.modules["translate"]` 以便重新导入时读取新配置。
- 测试 mock `requests.post` 返回假 completions 响应 — 不会连接真实的 oMLX 服务。
- `conftest.py` 提供共享 fixtures：`fake_config`、`mock_omlx_response`、`patch_omlx_call`、`patch_health_check`。

## 历史记录

翻译结果持久化到 `.history/translations.json`（纯 JSON，通过锁保证线程安全）。已被 git 忽略。

## 已知问题

- `app.py:206` — health endpoint 计算了 `omlx_status` 但从未在响应中使用（始终返回 URL）。测试中已记录此行为。

## 已有指引

详见 `CLAUDE.md`，包含架构细节和开发命令。
