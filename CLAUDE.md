# CLAUDE.md

本文档为 Claude Code (claude.ai/code) 在操作本仓库代码时提供指导。

## 项目概述

Local-translator 是一个基于 Web 的翻译服务，由本地大语言模型（通过 oMLX 运行的 TranslateGemma-4B-it）驱动。它提供了一个基于 FastAPI 的后端和一个深色主题的单页前端，支持英文、简体中文和日文之间的实时翻译。

## 架构

```
app.py          # FastAPI 应用 — 路由、请求/响应模型、历史记录管理
translate.py    # 翻译逻辑 — 构建提示词，调用 oMLX OpenAI 兼容 API
config.json     # 运行时配置（oMLX 端点、模型、语言、服务器端口）
templates/      # 前端 — 单个 index.html，内嵌 CSS + JS（无框架）
main.py         # 入口占位符（生产环境不使用）
```

关键模式：
- `config.json` 是所有配置的唯一数据源。`app.py` 和 `translate.py` 都在导入时独立读取它。
- 历史记录存储在 `.history/translations.json`（纯 JSON 文件，最多保留 `history_limit` 条记录）。
- 前端是原生 HTML/CSS/JS — 无需构建步骤，无打包工具。自动翻译使用防抖（根据配置中的 800ms）。
- `/api/translate/auto` 的语言检测是基于启发式的（Unicode 范围检查，用于 CJK/日文）。

## 开发命令

```bash
# 安装依赖（使用 uv）
uv sync

# 启动开发服务器
uvicorn app:app --reload --host 0.0.0.0 --port 8980

# 或：python -m uvicorn app:app --reload
```

当前未配置测试、lint 或格式化工具。项目使用 `uv` 作为包管理器（参见 `pyproject.toml` 和 `uv.lock`）。

## 配置

编辑 `config.json` 可修改：
- `omlx.*` — oMLX 服务端点、模型名称、温度、最大 token 数
- `server.port` — FastAPI 服务器端口（默认 8980）
- `history_limit` — 最大保存翻译数（默认 20）
- `languages` — 语言代码 → 显示名称映射
