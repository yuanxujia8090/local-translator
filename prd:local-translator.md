# 本地中英互译服务和页面 — 完整方案

## 一、系统架构

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐
│   浏览器      │  HTTP │   FastAPI     │  POST │    oMLX          │
│  Web前端页面  │──────▶│  后端服务     │──────▶│  (localhost:8000)│
│              │◀──────│  API代理层    │◀──────│  TranslateGemma  │
└──────────────┘       └───────────────┘       └──────────────────┘
```

- **前端**：HTML + CSS + ReactJS（利用你的前端优势，零构建工具）
- **后端**：Python， FastAPI（异步、自动文档、轻量级）
- **推理引擎**：oMLX（Apple Silicon 原生，OpenAI 兼容 API）服务本地端口：8050
- **模型**：TranslateGemma-4B-it（MLX量化版，~3GB RAM）

---

## 二、项目结构

```
local-translator/
├── app.py                  # FastAPI 主入口 + API路由
├── translate.py            # 翻译逻辑封装（prompt构建、API调用）
├── templates/
│   └── index.html          # 翻译页面（HTML+CSS+React 组件化）
├── requirements.txt        # Python依赖
└── README.md               # 使用说明
```

设计稿说明

1. 页面设计稿参考： ./设计稿草图.png
2. 大致布局： 左右结构，左边输入，右边输出，最右侧有默认隐藏的历史记录（仅保留最多20次）

---

## 三、后端实现

### 3.1 requirements.txt

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
requests>=2.32.0
pydantic>=2.10.0
```

### 3.2 translate.py — 翻译核心逻辑

```python
"""TranslateGemma-4B-it 翻译封装"""

import requests
from typing import Optional

OLLAMA_BASE_URL = "http://localhost:8050/v1"  # oMLX服务地址
MODEL_NAME = "translategemma-4b-it-4bit"       # oMLX中加载的模型名
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.3                      # 翻译任务需低温度保证一致性


def build_prompt(text: str, src_lang: str, tgt_lang: str) -> str:
    """构建 TranslateGemma 格式的 prompt"""
    lang_map = {
        "en": ("English", "en"),
        "zh-Hans": ("Chinese (Simplified)", "zh-Hans"),
    }

    src_name, src_code = lang_map.get(src_lang, (src_lang, src_lang))
    tgt_name, tgt_code = lang_map.get(tgt_lang, (tgt_lang, tgt_lang))

    prompt = f"""You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. Your goal is to accurately convey the meaning and nuances of the original {src_name} text while adhering to {tgt_code} grammar, vocabulary, and cultural sensitivities.
Produce only the {tgt_name} translation, without any additional explanations or commentary. Please translate the following {src_name} text into {tgt_code}:


{text}"""
    return prompt


def translate_text(
    text: str,
    src_lang: str = "en",
    tgt_lang: str = "zh-Hans",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """调用 oMLX API 执行翻译"""
    if not text.strip():
        return ""

    prompt = build_prompt(text, src_lang, tgt_lang)

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
        "temperature": temperature or DEFAULT_TEMPERATURE,
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json=payload,
            timeout=120,  # 模型推理可能较慢，给足超时
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"]
        # 清理可能的多余空白和 system prefix
        return result.strip()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("无法连接到 oMLX 服务，请确保 oMLX 已启动")
    except KeyError:
        raise RuntimeError(f"API 返回格式异常: {resp.text}")


def translate_batch(
    texts: list[str], src_lang: str = "en", tgt_lang: str = "zh-Hans"
) -> list[str]:
    """批量翻译（顺序调用，避免并发压力）"""
    return [translate_text(t, src_lang, tgt_lang) for t in texts]
```

### 3.3 app.py — FastAPI 服务

```python
"""本地翻译服务 — FastAPI 后端"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional

from translate import translate_text, OLLAMA_BASE_URL

app = FastAPI(
    title="本地中英互译服务",
    description="基于 TranslateGemma-4B-it + oMLX 的本地翻译服务",
    version="1.0.0",
)


# ---------- 数据模型 ----------

class TranslateRequest(BaseModel):
    """翻译请求"""
    text: str = Field(..., min_length=1, max_length=4096, description="待翻译文本")
    src_lang: str = Field(default="en", pattern="^(en|zh-Hans)$", description="源语言: en 或 zh-Hans")
    tgt_lang: str = Field(default="zh-Hans", pattern="^(en|zh-Hans)$", description="目标语言: en 或 zh-Hans")
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


# ---------- 路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回翻译页面"""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/translate", response_model=TranslateResponse)
async def api_translate(req: TranslateRequest):
    """执行翻译"""
    try:
        result = translate_text(
            text=req.text,
            src_lang=req.src_lang,
            tgt_lang=req.tgt_lang,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")

    return TranslateResponse(
        source=req.text,
        target=result,
        src_lang=req.src_lang,
        tgt_lang=req.tgt_lang,
    )


@app.post("/api/translate/auto")
async def api_translate_auto(text: str):
    """自动检测语言方向并翻译（英↔中）"""
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    # 简单启发式判断：包含中文字符 → 英译中；否则 → 中译英
    has_chinese = any("\u4e00" <= c <= "\u9fff" for c in text)
    if has_chinese:
        src, tgt = "zh-Hans", "en"
    else:
        src, tgt = "en", "zh-Hans"

    try:
        result = translate_text(text, src_lang=src, tgt_lang=tgt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")

    return {"source": text, "target": result, "src_lang": src, "tgt_lang": tgt}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    try:
        import requests as req
        resp = req.get(f"{OLLAMA_BASE_URL}/models", timeout=5)
        omlx_status = "ok" if resp.status_code == 200 else f"error: {resp.status_code}"
    except Exception as e:
        omlx_status = f"unreachable: {str(e)}"

    return HealthResponse(status="ok", omlx_url=f"{OLLAMA_BASE_URL}")


# ---------- 启动方式 ----------
# uvicorn app:app --reload --host 0.0.0.0 --port 8001
```

---

## 四、前端实现

### 4.1 templates/index.html

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>本地中英互译 — TranslateGemma-4B-it</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --border: #334155;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --error: #ef4444;
      --radius: 12px;
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      padding: 20px 32px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    header h1 {
      font-size: 20px;
      font-weight: 600;
    }

    header h1 span { color: var(--primary); }

    .status-badge {
      display: flex; align-items: center; gap: 6px;
      font-size: 13px; color: var(--text-muted);
    }

    .status-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--success); transition: background 0.3s;
    }

    .status-dot.error { background: var(--error); }

    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 1200px;
      width: 100%;
      margin: 0 auto;
      padding: 24px 32px;
    }

    /* 方向切换栏 */
    .direction-bar {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      margin-bottom: 20px;
    }

    .lang-label {
      font-size: 15px;
      font-weight: 500;
      color: var(--text-muted);
    }

    .lang-label.active { color: var(--primary); }

    .swap-btn {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      width: 40px; height: 40px;
      border-radius: 50%;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px;
      transition: all 0.2s;
    }

    .swap-btn:hover { background: var(--primary); border-color: var(--primary); }

    /* 翻译面板 */
    .panels {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      flex: 1;
    }

    @media (max-width: 768px) {
      .panels { grid-template-columns: 1fr; }
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .panel-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .panel-header h3 { font-size: 14px; font-weight: 500; }

    .panel-actions { display: flex; gap: 8px; }

    .icon-btn {
      background: none; border: none; color: var(--text-muted);
      cursor: pointer; padding: 4px 8px; border-radius: 6px;
      font-size: 13px; transition: all 0.2s;
    }

    .icon-btn:hover { color: var(--text); background: rgba(255,255,255,0.05); }

    textarea {
      flex: 1;
      min-height: 200px;
      background: transparent;
      border: none;
      color: var(--text);
      padding: 16px;
      font-size: 15px;
      line-height: 1.6;
      resize: none;
      outline: none;
      font-family: inherit;
    }

    textarea::placeholder { color: var(--text-muted); }

    .output-area {
      flex: 1;
      min-height: 200px;
      padding: 16px;
      font-size: 15px;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .output-area.placeholder { color: var(--text-muted); font-style: italic; }

    .panel-footer {
      padding: 8px 16px;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
      color: var(--text-muted);
    }

    /* 翻译按钮 */
    .translate-bar {
      display: flex;
      justify-content: center;
      margin-top: 20px;
    }

    .translate-btn {
      background: var(--primary);
      color: white;
      border: none;
      padding: 12px 48px;
      border-radius: var(--radius);
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }

    .translate-btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
    .translate-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    .translate-btn.loading {
      position: relative;
      pointer-events: none;
    }

    .translate-btn.loading::after {
      content: '';
      position: absolute;
      width: 16px; height: 16px;
      border: 2px solid transparent;
      border-top-color: white;
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    /* 错误提示 */
    .error-toast {
      position: fixed;
      bottom: 24px; right: 24px;
      background: var(--error);
      color: white;
      padding: 12px 20px;
      border-radius: var(--radius);
      font-size: 14px;
      opacity: 0;
      transform: translateY(20px);
      transition: all 0.3s;
      pointer-events: none;
    }

    .error-toast.show { opacity: 1; transform: translateY(0); }
  </style>
</head>
<body>

<header>
  <h1><span>⚡</span> 本地中英互译 <small style="font-weight:400;font-size:13px;color:var(--text-muted)">TranslateGemma-4B-it</small></h1>
  <div class="status-badge">
    <span class="status-dot" id="statusDot"></span>
    <span id="statusText">检查中...</span>
  </div>
</header>

<main>
  <div class="direction-bar">
    <span class="lang-label active" id="srcLabel">English</span>
    <button class="swap-btn" onclick="swapDirection()" title="交换方向">⇄</button>
    <span class="lang-label" id="tgtLabel">简体中文</span>
  </div>

  <div class="panels">
    <!-- 源语言面板 -->
    <div class="panel">
      <div class="panel-header">
        <h3 id="srcPanelTitle">输入 (English)</h3>
        <div class="panel-actions">
          <button class="icon-btn" onclick="clearSource()" title="清空">✕</button>
          <button class="icon-btn" onclick="pasteFromClipboard()" title="粘贴">📋</button>
        </div>
      </div>
      <textarea id="sourceText" placeholder="在此输入要翻译的文本..." maxlength="4096"></textarea>
      <div class="panel-footer">
        <span id="charCount">0 / 4096</span>
      </div>
    </div>

    <!-- 目标语言面板 -->
    <div class="panel">
      <div class="panel-header">
        <h3 id="tgtPanelTitle">翻译 (简体中文)</h3>
        <div class="panel-actions">
          <button class="icon-btn" onclick="copyResult()" title="复制结果">📄</button>
        </div>
      </div>
      <div class="output-area placeholder" id="resultText">翻译结果将显示在这里...</div>
      <div class="panel-footer">
        <span id="resultInfo"></span>
      </div>
    </div>
  </div>

  <div class="translate-bar">
    <button class="translate-btn" id="translateBtn" onclick="doTranslate()">翻译</button>
  </div>
</main>

<div class="error-toast" id="errorToast"></div>

<script>
  // ---------- 状态管理 ----------
  let srcLang = 'en';
  let tgtLang = 'zh-Hans';

  const langNames = { en: 'English', 'zh-Hans': '简体中文' };

  // ---------- DOM 元素 ----------
  const sourceText = document.getElementById('sourceText');
  const resultText = document.getElementById('resultText');
  const translateBtn = document.getElementById('translateBtn');
  const charCount = document.getElementById('charCount');
  const resultInfo = document.getElementById('resultInfo');
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');

  // ---------- 初始化 ----------
  sourceText.addEventListener('input', () => {
    charCount.textContent = `${sourceText.value.length} / 4096`;
    if (sourceText.value.trim()) {
      resultText.classList.add('placeholder');
      resultText.textContent = '翻译结果将显示在这里...';
    }
  });

  // Ctrl+Enter / Cmd+Enter 快捷翻译
  sourceText.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      doTranslate();
    }
  });

  checkHealth();

  // ---------- 健康检查 ----------
  async function checkHealth() {
    try {
      const resp = await fetch('/api/health');
      const data = await resp.json();
      if (data.status === 'ok') {
        statusDot.classList.remove('error');
        statusText.textContent = `oMLX 已连接 (${data.omlx_url})`;
      } else {
        throw new Error(data.status);
      }
    } catch (e) {
      statusDot.classList.add('error');
      statusText.textContent = 'oMLX 未连接';
    }
  }

  // ---------- 交换方向 ----------
  function swapDirection() {
    [srcLang, tgtLang] = [tgtLang, srcLang];

    document.getElementById('srcLabel').textContent = langNames[srcLang];
    document.getElementById('tgtLabel').textContent = langNames[tgtLang];
    document.getElementById('srcPanelTitle').textContent = `输入 (${langNames[srcLang]})`;
    document.getElementById('tgtPanelTitle').textContent = `翻译 (${langNames[tgtLang]})`;

    // 交换源文本和结果
    if (resultText.classList.contains('placeholder')) return;
    const result = resultText.textContent;
    if (result && !resultText.classList.contains('placeholder')) {
      sourceText.value = result;
      charCount.textContent = `${result.length} / 4096`;
    }
  }

  // ---------- 翻译 ----------
  async function doTranslate() {
    const text = sourceText.value.trim();
    if (!text) return;

    translateBtn.classList.add('loading');
    translateBtn.textContent = '';
    resultText.classList.remove('placeholder');

    try {
      const resp = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, src_lang: srcLang, tgt_lang: tgtLang }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || '翻译失败');
      }

      const data = await resp.json();
      resultText.textContent = data.target;
      resultInfo.textContent = `${srcLang} → ${tgtLang}`;

    } catch (e) {
      showError(e.message);
      resultText.textContent = '翻译失败，请重试';
    } finally {
      translateBtn.classList.remove('loading');
      translateBtn.textContent = '翻译';
    }
  }

  // ---------- 工具函数 ----------
  function clearSource() {
    sourceText.value = '';
    charCount.textContent = '0 / 4096';
    resultText.classList.add('placeholder');
    resultText.textContent = '翻译结果将显示在这里...';
    resultInfo.textContent = '';
  }

  async function copyResult() {
    const text = resultText.textContent;
    if (!text || resultText.classList.contains('placeholder')) return;
    await navigator.clipboard.writeText(text);
    showToast('已复制到剪贴板');
  }

  async function pasteFromClipboard() {
    try {
      const text = await navigator.clipboard.readText();
      sourceText.value = text;
      charCount.textContent = `${text.length} / 4096`;
    } catch {
      showToast('无法读取剪贴板');
    }
  }

  function showError(msg) {
    const toast = document.getElementById('errorToast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 4000);
  }

  function showToast(msg) {
    const toast = document.getElementById('errorToast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
  }
</script>

</body>
</html>
```

---

## 五、部署与运行步骤

### Step 1: 准备 oMLX 服务（先决条件）

```bash
# 克隆并安装 oMLX
git clone https://github.com/jundot/omlx && cd omlx && pip install -e .

# 下载 TranslateGemma-4B-it MLX 量化版
# oMLX 会自动发现 safetensors 格式的模型

# 启动 oMLX 服务（后台运行）
omlx serve --model mlx-community/translategemma-4b-it-4bit &

# 验证 oMLX 是否正常运行
curl http://localhost:8050/v1/models
```

### Step 2: 启动翻译服务

```bash
cd local-translator/
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8001
```

### Step 3: 访问页面

浏览器打开 `http://localhost:8001`，即可使用翻译界面。

### Step 4: API 文档（自动生成）

- Swagger UI：`http://localhost:8001/docs`
- ReDoc：`http://localhost:8001/redoc`

---

## 六、API 接口说明

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/` | 返回翻译页面 |
| `POST` | `/api/translate` | 指定方向的翻译（英→中 / 中→英） |
| `POST` | `/api/translate/auto` | 自动检测语言方向并翻译 |
| `GET` | `/api/health` | 健康检查（验证 oMLX 连接状态） |

### POST /api/translate 请求示例

```json
{
  "text": "Hello, how are you?",
  "src_lang": "en",
  "tgt_lang": "zh-Hans",
  "max_tokens": 512,
  "temperature": 0.3
}
```

### POST /api/translate/auto 请求示例

```bash
curl -X POST "http://localhost:8001/api/translate/auto?text=你好世界"
# 自动识别为 zh-Hans → en，返回英文翻译
```

---

## 七、性能与注意事项

| 项目 | 说明 |
|------|------|
| **内存需求** | ~3GB RAM（4bit 量化版） |
| **首次响应延迟** | 模型加载 ~5-15秒（仅首次），后续请求 oMLX SSD缓存加速 |
| **单次翻译耗时** | ~2-8秒（取决于文本长度和Mac配置） |
| **并发限制** | oMLX 默认单模型推理，建议串行调用避免OOM |
| **文本限制** | 前端最大4096字符，模型上下文窗口支持更长但建议控制长度 |
| **超时设置** | API 层已设120秒超时，防止模型推理卡死 |

---

## 八、后续可扩展方向

1. **翻译历史**：本地 IndexedDB 存储历史记录，支持回溯
2. **批量翻译**：上传文本文件（txt/csv），逐行翻译下载结果
3. **快捷键全局触发**：结合 Alfred Workflow 实现系统级快捷翻译
4. **更多语言对**：TranslateGemma 支持55种语言，扩展 `lang_map` 即可
5. **翻译记忆**：缓存已翻译的文本对，相同内容直接返回结果
