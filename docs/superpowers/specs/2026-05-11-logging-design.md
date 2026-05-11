# 日志模块设计文档

**日期：** 2026-05-11
**主题：** 为本地翻译服务添加日志模块

## 目标

为 `app.py` 和 `translate.py` 添加基础日志功能，便于排查问题。

## 方案概要

使用 Python 标准库 `logging`，新增 `logger.py` 模块统一配置。双输出：控制台（stderr）+ 文件（按天轮转）。

## 技术细节

### logger.py

- 模块级单例，名为 `"local-translator"`
- 两个 handler：
  - `StreamHandler` → stderr，格式 `[YYYY-MM-DD HH:MM:SS] [LEVEL] module:function msg`
  - `TimedRotatingFileHandler` → `logs/local-translator.log`，每天零时轮转，保留所有历史
- 日志级别通过 `LOG_LEVEL` 环境变量控制（默认 `INFO`）

### app.py 集成点

- 请求进入时记录：源文本、语言方向
- 翻译成功/失败时记录结果或异常
- 历史记录操作（写入、读取、清空）
- 健康检查状态

### translate.py 集成点

- API 调用尝试（目标 URL、模型名）
- 连接错误、响应解析异常

## 测试兼容性

现有测试不受影响 — logger 是模块级单例，stderr/文件输出不干扰 TestClient。
