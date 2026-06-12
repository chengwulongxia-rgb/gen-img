"""gen-img — Gemini 圖片生成 CLI，專為部落格配圖設計。

用法:
    # 直接下 prompt
    uv run python main.py "一隻在寫程式的橘貓，像素風格" -a 16:9 -o hero

    # 讀取 YAML preset（prompt 可寫在 YAML 或命令列）
    uv run python main.py "AI 訓練流程圖" --preset presets/tech-hero.yaml

    # YAML 已有 prompt 就不用命令列給
    uv run python main.py --preset presets/cat.yaml

    # 列出現有 presets
    uv run python main.py --list-presets
"""

from google import genai
from google.genai import types
import argparse
import os
import time
from pathlib import Path
from dotenv import load_dotenv

try:
    import yaml
except ImportError:
    yaml = None

VALID_ASPECT_RATIOS = [
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4",
    "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
]
VALID_SIZES = ["1K", "2K", "4K"]

PRESETS_DIR = Path(__file__).parent / "presets"


def load_preset(path: str) -> dict:
    """讀取 YAML preset 檔，回傳 dict。"""
    if yaml is None:
        raise ImportError("pyyaml 未安裝，請執行: uv add pyyaml")

    preset_path = Path(path)
    if not preset_path.is_absolute():
        # 先找 presets/ 目錄下，支援省略 .yaml 副檔名
        candidate = PRESETS_DIR / path
        if not candidate.exists():
            for ext in (".yaml", ".yml"):
                c2 = PRESETS_DIR / (path + ext)
                if c2.exists():
                    candidate = c2
                    break
        if candidate.exists():
            preset_path = candidate
        elif not preset_path.exists():
            raise FileNotFoundError(f"找不到 preset: {path} (也找了 {PRESETS_DIR / path})")

    with open(preset_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"YAML 格式錯誤，應為 key-value mapping: {preset_path}")
    return data


def list_presets():
    """列出 presets/ 目錄下所有 YAML 檔。"""
    if not PRESETS_DIR.exists():
        print("(沒有 presets/ 目錄)")
        return

    yamls = sorted(PRESETS_DIR.glob("*.yaml")) + sorted(PRESETS_DIR.glob("*.yml"))
    if not yamls:
        print("(presets/ 目錄下尚無 YAML 檔)")
        return

    print(f"Presets ({PRESETS_DIR}):")
    for yf in yamls:
        try:
            data = load_preset(str(yf))
            prompt = (data.get("prompt") or "")[:50]
            si = (data.get("system_instruction") or "")[:40]
            ar = data.get("aspect_ratio", "-")
            sz = data.get("size", "-")
            print(f"  {yf.name:<30} {ar:>5} {sz:>3}  {prompt}")
            if si:
                print(f"  {'':<30}        📋 {si}")
        except Exception:
            print(f"  {yf.name:<30} (讀取失敗)")


def parse_args():
    p = argparse.ArgumentParser(
        description="Gemini 圖片生成 — 部落格配圖專用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
部落格常用尺寸建議:
  16:9   封面橫幅（hero image / Open Graph）
  2:3    文章插圖（直立，適合手機捲動）
  1:1    方形縮圖 / 社群預覽
  21:9   超寬橫幅

風格 system_instruction 範例:
  "極簡向量插畫，深色主題，科技感，無文字"
  "溫暖水彩風格，柔和色調，留白多"
  "寫實攝影風格，自然光，淺景深"

YAML preset 格式:
  prompt: "圖片描述"
  system_instruction: "風格指令"
  aspect_ratio: "16:9"
  size: "1K"
        """,
    )
    p.add_argument("prompt", nargs="?", default=None,
                   help="圖片描述（支援中英文；若 YAML 已有 prompt 可省略）")
    p.add_argument("-p", "--preset", default=None,
                   help="YAML preset 檔路徑（自動搜尋 presets/ 目錄）")
    p.add_argument("--list-presets", action="store_true",
                   help="列出現有 presets")
    p.add_argument("-s", "--system-instruction", default=None,
                   help="系統指令：控制整體風格、色調、構圖")
    p.add_argument("-a", "--aspect-ratio", default=None,
                   choices=VALID_ASPECT_RATIOS, help="圖片比例")
    p.add_argument("-z", "--size", default=None,
                   choices=VALID_SIZES, help="圖片尺寸")
    p.add_argument("-o", "--output", default=None,
                   help="輸出檔名（預設: 自動以時間戳命名）")
    p.add_argument("-t", "--temperature", type=float, default=None,
                   help="創意溫度 0-2")
    p.add_argument("-n", "--count", type=int, default=1,
                   help="產生張數（預設: 1）")
    p.add_argument("--model", default="gemini-3.1-flash-image-preview",
                   help="模型名稱")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="安靜模式，只輸出圖片路徑")
    return p.parse_args()


def merge_args(args) -> dict:
    """合併 CLI 參數與 YAML preset：CLI > YAML > 預設值。"""
    cfg = {
        "prompt": args.prompt,
        "system_instruction": args.system_instruction,
        "aspect_ratio": args.aspect_ratio,
        "size": args.size,
        "temperature": args.temperature,
        "output": args.output,
        "model": args.model,
        "quiet": args.quiet,
    }

    # YAML preset 當作 baseline，CLI 值覆蓋
    if args.preset:
        yaml_data = load_preset(args.preset)
        for key in ("prompt", "system_instruction", "aspect_ratio",
                     "size", "temperature", "output"):
            if cfg[key] is None and key in yaml_data:
                cfg[key] = yaml_data[key]

    # 最終預設值（CLI 和 YAML 都沒給的）
    if cfg["prompt"] is None:
        raise ValueError("請提供 prompt（命令列或 YAML preset 中）")
    if cfg["aspect_ratio"] is None:
        cfg["aspect_ratio"] = "16:9"
    if cfg["size"] is None:
        cfg["size"] = "1K"
    if cfg["temperature"] is None:
        cfg["temperature"] = 1.0

    return cfg


def build_system_instruction(text: str | None) -> types.Content | None:
    if not text:
        return None
    return types.Content(
        role="user",
        parts=[types.Part.from_text(text=text)],
    )


def collect_images(chunk, image_count: int, prefix: str) -> tuple[int, list[str]]:
    saved = []
    if not chunk.candidates:
        return image_count, saved

    for candidate in chunk.candidates:
        if not (candidate.content and candidate.content.parts):
            continue
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                image_count += 1
                mime = part.inline_data.mime_type or "image/png"
                ext = mime.split("/")[-1] if "/" in mime else "png"
                if ext == "jpeg":
                    ext = "jpg"
                filename = f"{prefix}_{image_count}.{ext}"
                with open(filename, "wb") as f:
                    f.write(part.inline_data.data)
                saved.append(filename)
    return image_count, saved


def generate(cfg: dict):
    client = genai.Client(
        api_key=os.environ.get("GOOGLE_CLOUD_API_KEY"),
    )

    system_instruction = build_system_instruction(cfg["system_instruction"])

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=cfg["prompt"])],
        ),
    ]

    config = types.GenerateContentConfig(
        temperature=cfg["temperature"],
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        system_instruction=system_instruction,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        image_config=types.ImageConfig(
            aspect_ratio=cfg["aspect_ratio"],
            image_size=cfg["size"],
        ),
        thinking_config=types.ThinkingConfig(
            thinking_level="MINIMAL",
        ),
    )

    prefix = cfg["output"] or f"genimg_{time.strftime('%Y%m%d_%H%M%S')}"

    image_count = 0
    all_saved = []

    for chunk in client.models.generate_content_stream(
        model=cfg["model"],
        contents=contents,
        config=config,
    ):
        # 手動迭代 parts 印文字，避免 SDK 的 chunk.text 在遇到圖片時
        # 發出 "non-text parts in the response" 警告
        if not cfg["quiet"] and chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            print(part.text, end="")

        image_count, saved = collect_images(chunk, image_count, prefix)
        all_saved.extend(saved)

    if not cfg["quiet"]:
        print(f"\n{'='*40}")
        print(f"📐 {cfg['aspect_ratio']} @ {cfg['size']}")
        print(f"🎨 prompt: {cfg['prompt']}")
        if cfg["system_instruction"]:
            print(f"📋 system: {cfg['system_instruction'][:60]}...")
        for f in all_saved:
            size_kb = os.path.getsize(f) / 1024
            print(f"✅ {f} ({size_kb:.0f} KB)")
    else:
        for f in all_saved:
            print(f)


def main():
    args = parse_args()

    if args.list_presets:
        list_presets()
        return

    try:
        cfg = merge_args(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        return

    generate(cfg)


if __name__ == "__main__":
    load_dotenv()
    main()
