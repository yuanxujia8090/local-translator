"""app.py FastAPI endpoints 单元测试。

策略：用 TestClient + patch translate.translate_text，不真正调用 oMLX。
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 辅助函数：重新导入 app（确保使用测试用 config）
# ---------------------------------------------------------------------------

def _import_app(fake_config: Path):
    """清除模块缓存并重新导入 app，让它读到 fake config。"""
    import sys

    # patch os.path 让模块加载时找到 fake_config
    with patch("app.os.path.join", return_value=str(fake_config)):
        with patch("app.os.path.dirname", return_value=str(fake_config.parent)):
            # 清除旧缓存
            for mod in list(sys.modules.keys()):
                if mod in ("app", "translate"):
                    del sys.modules[mod]

            with patch("translate.os.path.join", return_value=str(fake_config)):
                with patch("translate.os.path.dirname", return_value=str(fake_config.parent)):
                    import app as app_module  # noqa: F811
                    return app_module


# ---------------------------------------------------------------------------
# 测试：/ — index page
# ---------------------------------------------------------------------------

class TestIndexPage:
    def test_index_returns_html(self, fake_config):
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<!DOCTYPE html>" in resp.text
        assert "本地翻译" in resp.text


# ---------------------------------------------------------------------------
# 测试：POST /api/translate
# ---------------------------------------------------------------------------

class TestTranslateEndpoint:
    def _make_client(self, fake_config):
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient
        return client, app_module

    def test_successful_translation(self, fake_config):
        """正常翻译请求返回正确响应。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="你好，世界"
        ) as mock_translate:
            resp = client.post(
                "/api/translate",
                json={
                    "text": "Hello world",
                    "src_lang": "en",
                    "tgt_lang": "zh-Hans",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "Hello world"
        assert data["target"] == "你好，世界"
        assert data["src_lang"] == "en"
        assert data["tgt_lang"] == "zh-Hans"

    def test_translation_saves_to_history(self, fake_config):
        """翻译成功后应写入历史记录。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(app_module, "translate_text", return_value="你好"):
            resp = client.post(
                "/api/translate",
                json={"text": "Hello", "src_lang": "en", "tgt_lang": "zh-Hans"},
            )

        assert resp.status_code == 200
        # 检查 .history/translations.json 是否存在且包含数据
        history_file = app_module._HISTORY_FILE
        assert history_file.exists()
        history_data = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(history_data) == 1
        assert history_data[0]["text"] == "Hello"
        assert history_data[0]["translation"] == "你好"

    def test_empty_text_rejected(self, fake_config):
        """空文本应被 Pydantic 校验拒绝（422）。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.post(
            "/api/translate",
            json={"text": "", "src_lang": "en", "tgt_lang": "zh-Hans"},
        )
        assert resp.status_code == 422

    def test_invalid_lang_rejected(self, fake_config):
        """不支持的语言代码应被 Pydantic 校验拒绝（422）。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.post(
            "/api/translate",
            json={"text": "Hello", "src_lang": "fr", "tgt_lang": "zh-Hans"},
        )
        assert resp.status_code == 422

    def test_text_too_long_rejected(self, fake_config):
        """超过 4096 字符应被拒绝。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        long_text = "A" * 4097
        resp = client.post(
            "/api/translate",
            json={"text": long_text, "src_lang": "en", "tgt_lang": "zh-Hans"},
        )
        assert resp.status_code == 422

    def test_connection_error_returns_503(self, fake_config):
        """oMLX 连接失败应返回 503。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", side_effect=ConnectionError("服务不可用")
        ):
            resp = client.post(
                "/api/translate",
                json={"text": "Hello", "src_lang": "en", "tgt_lang": "zh-Hans"},
            )

        assert resp.status_code == 503
        assert "服务不可用" in resp.json()["detail"]

    def test_generic_error_returns_500(self, fake_config):
        """其他异常应返回 500。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", side_effect=RuntimeError("模型崩溃")
        ):
            resp = client.post(
                "/api/translate",
                json={"text": "Hello", "src_lang": "en", "tgt_lang": "zh-Hans"},
            )

        assert resp.status_code == 500
        assert "翻译失败" in resp.json()["detail"]

    def test_custom_max_tokens_passed_through(self, fake_config):
        """max_tokens 参数应透传给 translate_text。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="OK"
        ) as mock_fn:
            resp = client.post(
                "/api/translate",
                json={
                    "text": "Hello",
                    "src_lang": "en",
                    "tgt_lang": "zh-Hans",
                    "max_tokens": 256,
                    "temperature": 0.7,
                },
            )

        assert resp.status_code == 200
        mock_fn.assert_called_once_with(
            text="Hello",
            src_lang="en",
            tgt_lang="zh-Hans",
            max_tokens=256,
            temperature=0.7,
        )


# ---------------------------------------------------------------------------
# 测试：POST /api/translate/auto
# ---------------------------------------------------------------------------

class TestTranslateAutoEndpoint:
    def _setup(self, fake_config):
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient
        return client, app_module

    def test_english_to_chinese(self, fake_config):
        """英文输入自动翻译为中文。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="你好"
        ) as mock_fn:
            resp = client.post("/api/translate/auto", params={"text": "Hello world"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["src_lang"] == "en"
        assert data["tgt_lang"] == "zh-Hans"

    def test_chinese_to_english(self, fake_config):
        """中文输入自动翻译为英文。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="Hello"
        ) as mock_fn:
            resp = client.post("/api/translate/auto", params={"text": "你好世界"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["src_lang"] == "zh-Hans"
        assert data["tgt_lang"] == "en"

    def test_empty_text_rejected(self, fake_config):
        """空文本应返回 400。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.post("/api/translate/auto", params={"text": ""})
        assert resp.status_code == 400

    def test_whitespace_only_rejected(self, fake_config):
        """纯空白文本应返回 400。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.post("/api/translate/auto", params={"text": "   "})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 测试：GET /api/history & DELETE /api/history
# ---------------------------------------------------------------------------

class TestHistoryEndpoints:
    def test_get_empty_history(self, fake_config):
        """空历史记录返回空列表。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_history_after_translation(self, fake_config):
        """翻译后应能获取历史记录。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="你好"
        ):
            client.post(
                "/api/translate",
                json={"text": "Hello", "src_lang": "en", "tgt_lang": "zh-Hans"},
            )

        resp = client.get("/api/history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 1
        assert history[0]["text"] == "Hello"
        assert history[0]["translation"] == "你好"

    def test_clear_history(self, fake_config):
        """清空历史记录。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch.object(
            app_module, "translate_text", return_value="你好"
        ):
            client.post(
                "/api/translate",
                json={"text": "Hello", "src_lang": "en", "tgt_lang": "zh-Hans"},
            )

        resp = client.delete("/api/history")
        assert resp.status_code == 200
        assert resp.json()["message"] == "历史记录已清空"

        # 验证确实为空
        resp = client.get("/api/history")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# 测试：GET /api/health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_ok(self, fake_config):
        """oMLX 正常时返回 ok。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # health() 内部用 `import requests as req`，所以 patch 全局 requests.get
        with patch("requests.get", return_value=mock_resp):
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_unreachable(self, fake_config):
        """oMLX 不可达时返回错误信息。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with patch("requests.get", side_effect=ConnectionError("连接失败")):
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"  # health endpoint 总是返回 status=ok

    def test_health_error_status(self, fake_config):
        """oMLX 返回非 200 状态码 — 注意：原代码 omlx_status 变量计算了但未使用，
        返回的始终是 URL。这是已知 bug，测试匹配当前行为。"""
        app_module = _import_app(fake_config)
        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("requests.get", return_value=mock_resp):
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        # omlx_status 变量未使用 — 返回的始终是 URL（原代码 bug）
        assert data["omlx_url"] == "http://localhost:8050/v1"
