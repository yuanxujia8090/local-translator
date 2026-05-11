"""本地翻译服务 — FastAPI 后端"""

import json
import os
import requests
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

from logger import logger
from translate import (
    translate_text,
    OLLAMA_BASE_URL,
)

# 从 config.json 读取配置
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path, "r", encoding="utf-8") as f:
    _config = json.load(f)

_server_cfg = _config.get("server", {})
_SERVER_PORT = _server_cfg.get("port", 8980)

# 历史记录管理（线程锁保护并发安全）
_HISTORY_DIR = Path(os.path.dirname(__file__)) / ".history"
_HISTORY_FILE = _HISTORY_DIR / "translations.json"
_HISTORY_LIMIT = _config.get("history_limit", 20)
_history_lock = threading.Lock()

# ---------- 数据模型 ----------


class TranslateRequest(BaseModel):
    """翻译请求"""

    text: str = Field(..., min_length=1, max_length=4096, description="待翻译文本")
    src_lang: str = Field(default="en", pattern="^(en|zh-Hans|ja)$", description="源语言")
    tgt_lang: str = Field(default="zh-Hans", pattern="^(en|zh-Hans|ja)$", description="目标语言")
    max_tokens: Optional[int] = Field(default=512, ge=64, le=2048, description="最大输出token数")
    temperature: Optional[float] = Field(default=0.3, ge=0.1, le=1.0, description="采样温度")


class TranslateResponse(BaseModel):
    """翻译响应"""

    source: str
    target: str
    src_lang: str
    tgt_lang: str


class HealthResponse(BaseModel):
    status: str
    omlx_url: str


class HistoryItem(BaseModel):
    """历史记录项"""

    id: int
    text: str
    translation: str
    src_lang: str
    tgt_lang: str
    timestamp: str


# ---------- 历史记录管理 ----------


def _load_history() -> list[dict]:
    """加载历史记录"""
    if _HISTORY_FILE.exists():
        try:
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_history(history: list[dict]) -> None:
    """保存历史记录"""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _add_to_history(text: str, translation: str, src_lang: str, tgt_lang: str) -> HistoryItem:
    """添加翻译到历史记录（线程安全）"""
    logger.info("写入历史记录: %s -> %s", src_lang, tgt_lang)
    with _history_lock:
        history = _load_history()
        # 安全地取最大 ID，处理损坏数据
        valid_ids = [h["id"] for h in history if isinstance(h.get("id"), int)]
        next_id = max(valid_ids, default=0) + 1

        item = {
            "id": next_id,
            "text": text,
            "translation": translation,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        history.insert(0, item)  # 最新的在前面
        history = history[:_HISTORY_LIMIT]  # 限制数量
        _save_history(history)
        return HistoryItem(**item)


# ---------- FastAPI 应用 ----------

app = FastAPI(
    title="本地中英互译服务",
    description="基于 TranslateGemma-4B-it + oMLX 的本地翻译服务",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回翻译页面"""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/translate", response_model=TranslateResponse)
async def api_translate(req: TranslateRequest):
    """执行翻译"""
    logger.info("翻译请求: %s -> %s, text=%r", req.src_lang, req.tgt_lang, req.text[:100])
    try:
        result = translate_text(
            text=req.text,
            src_lang=req.src_lang,
            tgt_lang=req.tgt_lang,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
    except ConnectionError as e:
        logger.error("翻译连接失败: %s", str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("翻译失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")

    logger.info("翻译成功: %s -> %s", req.src_lang, req.tgt_lang)

    # 添加到历史记录
    _add_to_history(req.text, result, req.src_lang, req.tgt_lang)

    return TranslateResponse(
        source=req.text,
        target=result,
        src_lang=req.src_lang,
        tgt_lang=req.tgt_lang,
    )


@app.post("/api/translate/auto")
async def api_translate_auto(text: str):
    """自动检测语言方向并翻译"""
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    logger.info("自动翻译请求: text=%r", text[:100])

    # 简单启发式判断
    has_chinese = any("一" <= c <= "鿿" for c in text)
    has_japanese = any("぀" <= c <= "ヿ" for c in text)

    if has_chinese and not has_japanese:
        src, tgt = "zh-Hans", "en"
    elif has_japanese:
        src, tgt = "ja", "zh-Hans"
    elif has_chinese:
        src, tgt = "zh-Hans", "en"
    else:
        # 默认英文 → 中文，或者检测其他语言
        src, tgt = "en", "zh-Hans"

    try:
        result = translate_text(text, src_lang=src, tgt_lang=tgt)
    except Exception as e:
        logger.error("自动翻译失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")

    logger.info("自动翻译成功: %s -> %s", src, tgt)

    return {"source": text, "target": result, "src_lang": src, "tgt_lang": tgt}


@app.get("/api/history", response_model=list[HistoryItem])
async def api_get_history():
    """获取历史记录"""
    history = _load_history()
    return [HistoryItem(**h) for h in history]


@app.delete("/api/history")
async def api_clear_history():
    """清空历史记录"""
    logger.info("清空历史记录")
    _save_history([])
    return {"message": "历史记录已清空"}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/models", timeout=5)
        omlx_status = "ok" if resp.status_code == 200 else f"error: {resp.status_code}"
    except Exception as e:
        logger.warning("oMLX 不可达: %s", str(e))
        omlx_status = f"unreachable: {str(e)}"

    return HealthResponse(status="ok", omlx_url=f"{OLLAMA_BASE_URL}")


# ---------- 启动方式 ----------
# uvicorn app:app --reload --host 0.0.0.0 --port 8980
