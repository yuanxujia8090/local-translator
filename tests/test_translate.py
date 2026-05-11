"""translate.py 单元测试：translate_text、translate_batch。

策略：用 unittest.mock.patch 拦截 requests.post，不真正调用 oMLX。
"""

import pytest
from unittest.mock import patch, MagicMock


# -----------------------------------------------------------------------
# translate_text 测试（需要 mock requests.post）
# -----------------------------------------------------------------------

class TestTranslateText:
    """测试 translate_text 函数。"""

    def test_basic_translation(self, patch_omlx_call):
        """正常翻译流程。"""
        from translate import translate_text
        result = translate_text("Hello world", "en", "zh-Hans")
        assert result == "你好，世界"

    def test_calls_completions_endpoint(self, patch_omlx_call):
        """确认请求发送到 /completions 而非 /chat/completions。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans")
        patch_omlx_call.assert_called_once()
        call_args = patch_omlx_call.call_args
        assert "/completions" in call_args[0][0]
        # 确保不是 chat/completions
        assert "/chat/" not in call_args[0][0]

    def test_request_payload_structure(self, patch_omlx_call):
        """验证请求 payload 使用 completions 格式（prompt 而非 messages）。"""
        from translate import translate_text
        translate_text("Hello world", "en", "zh-Hans")

        payload = patch_omlx_call.call_args[1]["json"]
        assert "model" in payload
        assert "prompt" in payload  # completions 用 prompt，不是 messages
        assert "messages" not in payload

    def test_prompt_format(self, patch_omlx_call):
        """验证 prompt 包含 <start_of_turn>/<end_of_turn> token。"""
        from translate import translate_text
        translate_text("Hello world", "en", "zh-Hans")

        payload = patch_omlx_call.call_args[1]["json"]
        prompt = payload["prompt"]
        assert "<start_of_turn>user" in prompt
        assert "Translate from en to zh-Hans: Hello world" in prompt
        assert "<end_of_turn>" in prompt
        assert "<start_of_turn>model" in prompt

    def test_stop_token_in_payload(self, patch_omlx_call):
        """验证 stop token 设置。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans")

        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["stop"] == ["<end_of_turn>"]

    def test_stream_false(self, patch_omlx_call):
        """验证 stream=False。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans")

        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["stream"] is False

    def test_custom_max_tokens(self, patch_omlx_call):
        """用户指定 max_tokens 应生效。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans", max_tokens=256)
        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["max_tokens"] == 256

    def test_custom_temperature(self, patch_omlx_call):
        """用户指定 temperature 应生效。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans", temperature=0.7)
        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["temperature"] == 0.7

    def test_temperature_zero_is_preserved(self, patch_omlx_call):
        """temperature=0 不应被 DEFAULT 覆盖。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans", temperature=0)
        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["temperature"] == 0

    def test_max_tokens_zero_is_preserved(self, patch_omlx_call):
        """max_tokens=0 不应被 DEFAULT 覆盖。"""
        from translate import translate_text
        translate_text("Hello", "en", "zh-Hans", max_tokens=0)
        payload = patch_omlx_call.call_args[1]["json"]
        assert payload["max_tokens"] == 0

    def test_empty_text_returns_empty(self, patch_omlx_call):
        """空文本直接返回空字符串，不调用 API。"""
        from translate import translate_text
        result = translate_text("", "en", "zh-Hans")
        assert result == ""
        patch_omlx_call.assert_not_called()

    def test_whitespace_only_returns_empty(self, patch_omlx_call):
        """纯空白文本返回空字符串。"""
        from translate import translate_text
        result = translate_text("   \n  ", "en", "zh-Hans")
        assert result == ""
        patch_omlx_call.assert_not_called()

    def test_connection_error_raises(self):
        """无法连接 oMLX 时应抛出 ConnectionError。"""
        from translate import translate_text

        with patch("translate.requests.post", side_effect=Exception("Connection refused")):
            import requests
            with patch("translate.requests.post", side_effect=requests.exceptions.ConnectionError()):
                with pytest.raises(ConnectionError, match="无法连接到 oMLX"):
                    translate_text("Hello", "en", "zh-Hans")

    def test_invalid_response_format_raises(self, mock_omlx_response):
        """API 返回异常格式时应抛出 RuntimeError。"""
        from translate import translate_text

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status.return_value = None
        # completions 接口返回 text 字段，不是 message.content
        mock_resp.json.return_value = {"bad": "format"}

        with patch("translate.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="API 返回格式异常"):
                translate_text("Hello", "en", "zh-Hans")

    def test_end_of_turn_truncation(self, mock_omlx_response):
        """模型输出包含 <end_of_turn> 时应正确截取。"""
        from translate import translate_text

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"text": "你好，世界<end_of_turn>\n额外内容"}],
        }

        with patch("translate.requests.post", return_value=mock_resp):
            result = translate_text("Hello", "en", "zh-Hans")
            assert result == "你好，世界"

    def test_no_end_of_turn_returns_full_text(self, mock_omlx_response):
        """没有 <end_of_turn> 时返回完整文本。"""
        from translate import translate_text

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"text": "你好，世界"}],
        }

        with patch("translate.requests.post", return_value=mock_resp):
            result = translate_text("Hello", "en", "zh-Hans")
            assert result == "你好，世界"


# -----------------------------------------------------------------------
# translate_batch 测试
# -----------------------------------------------------------------------

class TestTranslateBatch:
    """测试批量翻译。"""

    def test_batch_translates_all(self, patch_omlx_call):
        """批量翻译应返回等长列表。"""
        from translate import translate_batch
        results = translate_batch(["Hello", "World"], "en", "zh-Hans")
        assert len(results) == 2

    def test_batch_calls_api_once_per_item(self, patch_omlx_call):
        """每个文本调用一次 API。"""
        from translate import translate_batch
        translate_batch(["A", "B", "C"], "en", "zh-Hans")
        assert patch_omlx_call.call_count == 3
