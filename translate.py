"""TranslateGemma-4B-it 翻译封装 — 使用 /v1/completions 接口。

关键：TranslateGemma 模型要求通过 completions 接口 + 手动构建
<start_of_turn>/<end_of_turn> token 格式，不能用 chat/completions。
参考：check-omlx.py
"""

import json
import os
import requests
from typing import Optional

from logger import logger

# 从 config.json 读取配置
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path, "r", encoding="utf-8") as f:
    _config = json.load(f)

_omlx_cfg = _config["omlx"]
OLLAMA_BASE_URL = f"http://{_omlx_cfg['host']}:{_omlx_cfg['port']}/v1"
MODEL_NAME = _omlx_cfg["model"]
DEFAULT_MAX_TOKENS = _config.get("max_tokens", 1024) if "max_tokens" in _omlx_cfg else 512
DEFAULT_TEMPERATURE = _config.get("temperature", 0.1) if "temperature" in _omlx_cfg else 0.3


def translate_text(
    text: str,
    src_lang: str = "en",
    tgt_lang: str = "zh-Hans",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """调用 oMLX /v1/completions 接口执行翻译"""
    if not text.strip():
        return ""

    logger.info("调用 oMLX: %s -> %s, model=%s", src_lang, tgt_lang, MODEL_NAME)

    # 手动构造 TranslateGemma 期望的 prompt 格式（使用语言代码）
    prompt = (
        f"<start_of_turn>user\n"
        f"Translate from {src_lang} to {tgt_lang}: {text}<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
        "stop": ["<end_of_turn>"],
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/completions",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["text"]
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到 oMLX 服务，请确保 oMLX 已启动")
        raise ConnectionError("无法连接到 oMLX 服务，请确保 oMLX 已启动")
    except requests.exceptions.HTTPError:
        logger.error("oMLX HTTP 错误: %s", resp.text)
        raise
    except KeyError:
        logger.error("API 返回格式异常: %s", resp.text)
        raise RuntimeError(f"API 返回格式异常: {resp.text}")
    # 手动截取第一个 <end_of_turn> 之前的内容
    if "<end_of_turn>" in result:
        result = result.split("<end_of_turn>")[0].strip()
    else:
        result = result.strip()
    logger.info("oMLX 返回翻译结果")
    return result


def translate_batch(
    texts: list[str], src_lang: str = "en", tgt_lang: str = "zh-Hans"
) -> list[str]:
    """批量翻译（顺序调用，避免并发压力）"""
    return [translate_text(t, src_lang, tgt_lang) for t in texts]
