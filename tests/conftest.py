"""共享 fixtures：Mock oMLX API、FastAPI TestClient。"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

import pytest


# ---------------------------------------------------------------------------
# 临时 config.json — 每个测试用独立的 tmp_path，不污染真实配置
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_config(tmp_path: Path):
    """创建临时 config.json，返回其 Path。"""
    config_data = {
        "omlx": {
            "host": "localhost",
            "port": 8050,
            "model": "translategemma-4b-it-4bit",
            "temperature": 0.1,
            "max_tokens": 1024,
        },
        "server": {"port": 8780},
        "max_input_chars": 4096,
        "debounce_ms": 800,
        "history_limit": 20,
        "languages": {
            "en": "English",
            "zh-Hans": "简体中文",
            "ja": "日本語",
        },
    }

    fake_path = tmp_path / "config.json"
    fake_path.write_text(json.dumps(config_data), encoding="utf-8")

    # 清除模块缓存，确保下次 import 使用新 config
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("app", "translate"):
            del sys.modules[mod_name]

    yield fake_path


@pytest.fixture()
def mock_omlx_response():
    """模拟 oMLX completions API 成功响应。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.raise_for_status.return_value = None
    # completions 接口返回 choices[0].text，不是 message.content
    mock_resp.json.return_value = {
        "choices": [{"text": "你好，世界"}],
    }
    return mock_resp


@pytest.fixture()
def patch_omlx_call(mock_omlx_response):
    """Patch translate.requests.post，返回 mock 响应。"""
    with patch("translate.requests.post", return_value=mock_omlx_response) as mock_post:
        yield mock_post


@pytest.fixture()
def patch_health_check():
    """Patch app.requests.get（health endpoint 内部调用）。"""
    mock_health = MagicMock()
    mock_health.status_code = 200
    with patch("app.requests.get", return_value=mock_health) as mock_get:
        yield mock_get
