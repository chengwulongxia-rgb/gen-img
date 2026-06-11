# gen-img

**Gemini 圖片生成 CLI，專為部落格配圖設計。**

用 Google Gemini 模型生成插圖、封面、示意圖。支援 YAML 風格模板複用，一套 prompt 配多種比例。

## 安裝

```bash
git clone https://github.com/chengwulongxia-rgb/gen-img
cd gen-img
uv sync
```

## 設定

複製 `.env.example`（或自建 `.env`），填入 Gemini API key：

```
GOOGLE_CLOUD_API_KEY=你的_API_key
```

去 [Google AI Studio](https://aistudio.google.com/apikey) 申請。

## 快速開始

```bash
# 最簡單：一句話產圖
uv run python main.py "一隻在寫程式的橘貓，像素風格"

# 指定比例和尺寸
uv run python main.py "AI 訓練流程圖" -a 16:9 --size 2K

# 加上風格指令
uv run python main.py "伺服器機房" \
    -s "極簡向量插畫，深色背景，科技感，無文字"
```

## YAML Preset（複用風格模板）

把常用的風格組態寫成 YAML，放在 `presets/` 目錄：

```yaml
# presets/my-style.yaml
system_instruction: "溫暖水彩風格，柔和色調，留白多"
aspect_ratio: "2:3"
size: "1K"
```

使用：

```bash
# 列出所有 preset
uv run python main.py --list-presets

# 用 preset 產圖
uv run python main.py "主題描述" -p my-style

# CLI 參數可以覆蓋 YAML
uv run python main.py "主題" -p my-style -a 16:9 --size 2K
```

### 內建 Preset

| Preset | 比例 | 用途 |
|--------|------|------|
| `tech-hero` | 16:9 | 科技文章封面，深色向量風，右側留白放標題 |
| `article-inset` | 2:3 | 文章內插圖，暖色調，不搶文字 |
| `thumbnail` | 1:1 | 社群 / RSS 縮圖，高對比醒目 |
| `tech-diagram` | 16:9 | AI / 技術流程示意圖，幾何風 |

### YAML 完整欄位

```yaml
prompt: "圖片描述"            # 可省略，改用命令列 prompt
system_instruction: "風格"    # 系統指令
aspect_ratio: "16:9"         # 圖片比例
size: "1K"                   # 1K / 2K / 4K
temperature: 1.0             # 創意度 0-2
output: "my-image"           # 輸出檔名前綴
```

優先順序：**命令列 > YAML > 預設值**

## CLI 完整參數

```
uv run python main.py [prompt] [options]

位置參數:
  prompt              圖片描述（若 YAML 已提供可省略）

選項:
  -p, --preset        YAML preset 檔名（自動從 presets/ 搜尋）
  --list-presets      列出現有 presets
  -s, --system-instruction  系統指令（風格、色調、構圖）
  -a, --aspect-ratio  圖片比例（預設: 16:9）
                       可用: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4,
                             9:16, 16:9, 21:9, 1:4, 1:8, 4:1, 8:1
  -z, --size          圖片尺寸（預設: 1K）
                       可用: 1K, 2K, 4K
  -o, --output        輸出檔名（預設: genimg_時間戳）
  -t, --temperature   創意度 0-2（預設: 1.0）
  -q, --quiet         安靜模式，只輸出圖片路徑
  --model             模型名稱
```

## 部落格常用比例

| 比例 | 用途 |
|------|------|
| **16:9** | 封面橫幅（hero image / Open Graph） |
| **2:3** | 文章插圖（直立，適合手機捲動） |
| **1:1** | 方形縮圖 / 社群預覽 |
| **21:9** | 超寬橫幅 |

## 測試

```bash
uv run pytest tests/ -v
```

## 技術棧

- Python ≥ 3.13
- [google-genai](https://github.com/googleapis/python-genai) — Gemini SDK
- [python-dotenv](https://github.com/theskumar/python-dotenv) — 環境變數
- [PyYAML](https://pyyaml.org/) — YAML preset 解析
- [pytest](https://pytest.org/) — 測試框架
