import requests
import json

Omlx_API_BASE = "http://localhost:8050/v1"
MODEL_ALIAS = "translategemma-4b-it-4bit"

def translate_with_omlx_completions(text, source_lang_code="en", target_lang_code="zh"):
    """
    使用 /v1/completions 接口，手动构建翻译 prompt，完全绕过聊天模板。
    """
    url = f"{Omlx_API_BASE}/completions"

    # 手动构造 TranslateGemma 期望的 prompt 格式
    prompt = (
        f"<start_of_turn>user\n"
        f"Translate from {source_lang_code} to {target_lang_code}: {text}<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )

    payload = {
        "model": MODEL_ALIAS,
        "prompt": prompt,
        "temperature": 0.3,
        "max_tokens": 1024,
        "stop": ["<end_of_turn>"],   # 让模型在回复结束后自动停止
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        # 从 completions 的 choices 中提取文本
        # 改为：
        raw_output = result['choices'][0]['text']
        # 手动截取第一个 <end_of_turn> 之前的内容
        if '<end_of_turn>' in raw_output:
            translated_text = raw_output.split('<end_of_turn>')[0].strip()
        else:
            translated_text = raw_output.strip()
        return translated_text

    except requests.exceptions.RequestException as e:
        print(f"请求 oMLX 服务时出错: {e}")
        if 'response' in locals() and response.text:
            print(f"服务响应: {response.text}")
        return None

if __name__ == "__main__":
    print("=== 英译中 ===")
    text_en = "Hello, how are you?"
    result = translate_with_omlx_completions(text_en, source_lang_code="en", target_lang_code="zh")
    if result:
        print(f"译文: {result}")

    print("\n=== 中译英 ===")
    text_zh = "今天天气真好，我们出去走走吧。"
    result = translate_with_omlx_completions(text_zh, source_lang_code="zh", target_lang_code="en")
    if result:
        print(f"译文: {result}")



# 输出结果见： ./check-omlx-output.txt