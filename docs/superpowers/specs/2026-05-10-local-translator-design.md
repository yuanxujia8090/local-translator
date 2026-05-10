# 本地中英日互译服务 — 设计文档

## 概述

基于 TranslateGemma-4B-it + oMLX 的本地翻译 Web 应用，支持中、英、日三语互译。
纯本地运行，无需云端 API，保护隐私。

## 技术架构

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐
│   浏览器      │  HTTP │   FastAPI     │  POST │    oMLX          │
│  Vite + React │──────▶│  后端服务     │──────▶│  (可配置端口)    │
│              │◀──────│  API代理层    │◀──────│  TranslateGemma  │
└──────────────┘       └───────────────┘       └──────────────────┘
```

- **前端**：Vite + React（JSX），组件化架构
- **后端**：Python FastAPI，JSON 配置文件驱动
- **推理引擎**：oMLX（Apple Silicon 原生），`POST /v1/completions` 接口
- **模型**：TranslateGemma-4B-it（MLX 量化版）

## 功能范围

### 核心功能
- **三语互译**：中↔英、中↔日、英↔日（6 个方向）
- **自动翻译**：输入防抖触发，无需手动点击按钮
- **方向交换**：一键切换源/目标语言并自动重新翻译
- **工具栏**：清空输入、粘贴剪贴板、复制译文

### 辅助功能
- **翻译历史**：最近 N 条记录（可配置），点击回溯
- **错误提示**：面板内嵌显示，不遮挡内容

### 配置项（config.json）
| 配置 | 默认值 | 说明 |
|------|--------|------|
| `omlx.host` | "localhost" | oMLX 服务地址 |
| `omlx.port` | 8050 | oMLX 服务端口 |
| `omlx.model` | "translategemma-4b-it-4bit" | 模型名称 |
| `omlx.temperature` | 0.1 | 采样温度 |
| `omlx.max_tokens` | 1024 | 最大输出 token 数 |
| `server.port` | 8980 | FastAPI 服务端口 |
| `max_input_chars` | 4096 | 最大输入字符数 |
| `debounce_ms` | 800 | 防抖延迟（毫秒） |
| `history_limit` | 20 | 翻译历史保留条数 |
| `languages` | {en: "English", zh-Hans: "简体中文", ja: "日本語"} | 支持语种 |

## UI 设计

### 布局
- **左右双面板**（PC 端优化，移动端自动切换单列）
- 左侧：输入面板（textarea + 右上角清空按钮 + 粘贴按钮）
- 右侧：输出面板（结果文本 + 复制按钮）

### 交互
- **自动翻译**：输入停止 debounce_ms 后自动调用后端 API
- **快捷键**：Ctrl/Cmd + Enter 手动触发翻译
- **方向交换**：⇄ 按钮切换语言对并自动重新翻译

### 错误处理
- oMLX 连接失败：面板内嵌红色提示区域
- API 返回错误：显示具体错误信息
- 网络超时：显示超时提示

## 数据流

```
用户输入 → debounce timer → POST /api/translate → oMLX /v1/completions
                                    ↓
                          解析响应 + <end_of_turn> 截断
                                    ↓
                              显示译文 + 更新历史
```

## 组件架构（前端）

| 组件 | 职责 |
|------|------|
| `App` | 状态管理、配置加载、全局错误处理 |
| `Header` | 标题 + oMLX 连接状态指示 |
| `DirectionBar` | 语言选择器 + 方向交换按钮 |
| `InputPanel` | 文本输入、清空、粘贴、字符计数 |
| `OutputPanel` | 译文显示、复制、错误提示 |
| `TranslateButton` | （保留但非必需，自动翻译为主） |
| `HistoryPanel` | 最近翻译记录列表 |

## API 设计（后端）

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 返回 React SPA |
| POST | `/api/translate` | 执行翻译（指定方向） |
| GET | `/api/config` | 返回当前配置（前端显示用） |

### POST /api/translate
请求体：
```json
{
  "text": "待翻译文本",
  "src_lang": "en",
  "tgt_lang": "zh-Hans"
}
```

响应：
```json
{
  "source": "Hello",
  "target": "你好",
  "src_lang": "en",
  "tgt_lang": "zh-Hans"
}
```

## 翻译历史存储

使用 IndexedDB（前端本地），数据结构：
```json
{
  "id": "timestamp",
  "text": "原文",
  "translation": "译文",
  "src_lang": "en",
  "tgt_lang": "zh-Hans",
  "timestamp": 1716000000000
}
```

## 非功能需求

- **隐私**：所有数据本地处理，不上传云端
- **性能**：首次响应 ~5-15s（模型加载），后续请求 2-8s
- **内存**：~3GB RAM（4bit 量化版）
- **超时**：API 层设 120s 超时防止卡死
