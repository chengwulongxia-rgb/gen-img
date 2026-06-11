"""gen-img 測試 — 不呼叫實際 API，只測邏輯層。"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import base64

# 讓測試能 import main
sys.path.insert(0, str(Path(__file__).parent.parent))

import main
from google.genai import types


# ═══════════════════════════════════════════
# build_system_instruction
# ═══════════════════════════════════════════

class TestBuildSystemInstruction:
    def test_none_returns_none(self):
        assert main.build_system_instruction(None) is None

    def test_empty_string_returns_none(self):
        assert main.build_system_instruction("") is None

    def test_returns_content_with_text(self):
        result = main.build_system_instruction("極簡風格")
        assert isinstance(result, types.Content)
        assert result.parts[0].text == "極簡風格"


# ═══════════════════════════════════════════
# collect_images
# ═══════════════════════════════════════════

class TestCollectImages:
    def test_no_candidates_returns_unchanged(self):
        chunk = MagicMock()
        chunk.candidates = None
        count, saved = main.collect_images(chunk, 0, "test")
        assert count == 0
        assert saved == []

    def test_empty_candidates(self):
        chunk = MagicMock()
        chunk.candidates = []
        count, saved = main.collect_images(chunk, 5, "test")
        assert count == 5
        assert saved == []

    def test_no_inline_data(self):
        part = types.Part.from_text(text="hello")
        candidate = MagicMock()
        candidate.content = MagicMock()
        candidate.content.parts = [part]
        chunk = MagicMock()
        chunk.candidates = [candidate]

        count, saved = main.collect_images(chunk, 0, "test")
        assert count == 0
        assert saved == []

    def test_saves_image_with_jpeg_mime(self, tmp_path):
        os.chdir(tmp_path)
        image_bytes = b"fake-image-data"

        part = MagicMock()
        part.inline_data = MagicMock()
        part.inline_data.data = image_bytes
        part.inline_data.mime_type = "image/jpeg"

        candidate = MagicMock()
        candidate.content = MagicMock()
        candidate.content.parts = [part]

        chunk = MagicMock()
        chunk.candidates = [candidate]

        count, saved = main.collect_images(chunk, 0, "myimg")
        assert count == 1
        assert saved == ["myimg_1.jpg"]
        assert Path("myimg_1.jpg").read_bytes() == image_bytes

    def test_saves_image_png_fallback(self, tmp_path):
        os.chdir(tmp_path)
        image_bytes = b"png-data"

        part = MagicMock()
        part.inline_data = MagicMock()
        part.inline_data.data = image_bytes
        part.inline_data.mime_type = None  # fallback to png

        candidate = MagicMock()
        candidate.content = MagicMock()
        candidate.content.parts = [part]

        chunk = MagicMock()
        chunk.candidates = [candidate]

        count, saved = main.collect_images(chunk, 0, "img")
        assert saved == ["img_1.png"]

    def test_increments_counter(self, tmp_path):
        os.chdir(tmp_path)
        image_bytes = b"data"

        part = MagicMock()
        part.inline_data = MagicMock()
        part.inline_data.data = image_bytes
        part.inline_data.mime_type = "image/png"

        candidate = MagicMock()
        candidate.content = MagicMock()
        candidate.content.parts = [part]

        chunk = MagicMock()
        chunk.candidates = [candidate]

        count, saved = main.collect_images(chunk, 3, "x")
        assert count == 4
        assert saved == ["x_4.png"]


# ═══════════════════════════════════════════
# load_preset
# ═══════════════════════════════════════════

class TestLoadPreset:
    def test_loads_valid_yaml(self, tmp_path):
        # 建立臨時 preset
        preset = tmp_path / "test.yaml"
        preset.write_text("system_instruction: '極簡'\naspect_ratio: '1:1'\n")

        with patch.object(main, "PRESETS_DIR", tmp_path):
            data = main.load_preset("test")
            assert data["system_instruction"] == "極簡"
            assert data["aspect_ratio"] == "1:1"

    def test_auto_appends_yaml_extension(self, tmp_path):
        preset = tmp_path / "mypreset.yaml"
        preset.write_text("size: 2K\n")

        with patch.object(main, "PRESETS_DIR", tmp_path):
            data = main.load_preset("mypreset")  # 不加 .yaml
            assert data["size"] == "2K"

    def test_yml_extension(self, tmp_path):
        preset = tmp_path / "style.yml"
        preset.write_text("size: 4K\n")

        with patch.object(main, "PRESETS_DIR", tmp_path):
            data = main.load_preset("style")  # 不加 .yml
            assert data["size"] == "4K"

    def test_file_not_found(self, tmp_path):
        with patch.object(main, "PRESETS_DIR", tmp_path):
            try:
                main.load_preset("nonexistent")
                assert False, "應該拋出例外"
            except FileNotFoundError:
                pass

    def test_absolute_path(self, tmp_path):
        preset = tmp_path / "abs.yaml"
        preset.write_text("prompt: hello\n")

        data = main.load_preset(str(preset))
        assert data["prompt"] == "hello"

    def test_not_a_dict_raises(self, tmp_path):
        preset = tmp_path / "bad.yaml"
        preset.write_text("- item1\n- item2\n")  # list, not dict

        with patch.object(main, "PRESETS_DIR", tmp_path):
            try:
                main.load_preset("bad")
                assert False
            except ValueError as e:
                assert "mapping" in str(e)


# ═══════════════════════════════════════════
# merge_args
# ═══════════════════════════════════════════

class TestMergeArgs:
    def _make_args(self, **overrides):
        """建立模擬 args namespace。"""
        defaults = {
            "prompt": None,
            "system_instruction": None,
            "aspect_ratio": None,
            "size": None,
            "temperature": None,
            "output": None,
            "model": "gemini-3.1-flash-image-preview",
            "quiet": False,
            "preset": None,
        }
        defaults.update(overrides)
        ns = MagicMock()
        for k, v in defaults.items():
            setattr(ns, k, v)
        return ns

    def test_cli_only_with_defaults(self):
        args = self._make_args(prompt="一隻貓")
        cfg = main.merge_args(args)
        assert cfg["prompt"] == "一隻貓"
        assert cfg["aspect_ratio"] == "16:9"
        assert cfg["size"] == "1K"
        assert cfg["temperature"] == 1.0

    def test_cli_overrides_defaults(self):
        args = self._make_args(
            prompt="test",
            aspect_ratio="1:1",
            size="2K",
            temperature=0.5,
            output="out",
        )
        cfg = main.merge_args(args)
        assert cfg["aspect_ratio"] == "1:1"
        assert cfg["size"] == "2K"
        assert cfg["temperature"] == 0.5
        assert cfg["output"] == "out"

    def test_preset_provides_defaults(self, tmp_path):
        preset = tmp_path / "cfg.yaml"
        preset.write_text(
            "system_instruction: '水彩風'\n"
            "aspect_ratio: '2:3'\n"
            "size: 2K\n"
        )
        args = self._make_args(prompt="風景", preset=str(preset))
        cfg = main.merge_args(args)
        assert cfg["prompt"] == "風景"
        assert cfg["system_instruction"] == "水彩風"
        assert cfg["aspect_ratio"] == "2:3"
        assert cfg["size"] == "2K"

    def test_cli_overrides_preset(self, tmp_path):
        preset = tmp_path / "cfg.yaml"
        preset.write_text("aspect_ratio: '2:3'\nsize: 2K\n")
        args = self._make_args(
            prompt="貓",
            aspect_ratio="1:1",  # CLI 蓋過 YAML
            preset=str(preset),
        )
        cfg = main.merge_args(args)
        assert cfg["aspect_ratio"] == "1:1"  # CLI wins
        assert cfg["size"] == "2K"  # from YAML

    def test_prompt_from_yaml(self, tmp_path):
        preset = tmp_path / "cfg.yaml"
        preset.write_text("prompt: 'YAML 裡的 prompt'\n")
        args = self._make_args(preset=str(preset))
        cfg = main.merge_args(args)
        assert cfg["prompt"] == "YAML 裡的 prompt"

    def test_missing_prompt_raises(self):
        args = self._make_args()  # no prompt, no preset
        try:
            main.merge_args(args)
            assert False
        except ValueError as e:
            assert "prompt" in str(e)

    def test_temperature_from_yaml(self, tmp_path):
        preset = tmp_path / "cfg.yaml"
        preset.write_text("temperature: 0.3\n")
        args = self._make_args(prompt="test", preset=str(preset))
        cfg = main.merge_args(args)
        assert cfg["temperature"] == 0.3


# ═══════════════════════════════════════════
# CLI argument parsing
# ═══════════════════════════════════════════

class TestCLI:
    def _parse(self, argv):
        """用給定的 argv 呼叫 argparse。"""
        with patch.object(sys, "argv", ["main.py"] + argv):
            return main.parse_args()

    def test_prompt_positional(self):
        args = self._parse(["一隻貓"])
        assert args.prompt == "一隻貓"
        assert args.aspect_ratio is None

    def test_short_flags(self):
        args = self._parse([
            "test", "-s", "style", "-a", "1:1",
            "-z", "2K", "-o", "out", "-t", "0.5", "-q",
        ])
        assert args.system_instruction == "style"
        assert args.aspect_ratio == "1:1"
        assert args.size == "2K"
        assert args.output == "out"
        assert args.temperature == 0.5
        assert args.quiet is True

    def test_preset_flag(self):
        args = self._parse(["-p", "my-style", "prompt text"])
        assert args.preset == "my-style"
        assert args.prompt == "prompt text"

    def test_list_presets(self):
        args = self._parse(["--list-presets"])
        assert args.list_presets is True

    def test_invalid_aspect_ratio(self):
        try:
            self._parse(["test", "-a", "99:99"])
            assert False
        except SystemExit:
            pass

    def test_prompt_optional_with_preset(self):
        # prompt 應該可以是 None（若 YAML 有提供）
        args = self._parse(["-p", "my-preset"])
        assert args.prompt is None
        assert args.preset == "my-preset"


# ═══════════════════════════════════════════
# list_presets（不測試 stdout，只測不崩潰）
# ═══════════════════════════════════════════

class TestListPresets:
    def test_empty_dir_does_not_crash(self, tmp_path, capsys):
        with patch.object(main, "PRESETS_DIR", tmp_path):
            main.list_presets()
        captured = capsys.readouterr()
        assert "尚無" in captured.out or "沒有" in captured.out

    def test_lists_yaml_files(self, tmp_path, capsys):
        (tmp_path / "a.yaml").write_text("aspect_ratio: '1:1'\n")
        (tmp_path / "b.yml").write_text("size: 2K\n")
        (tmp_path / "not-yaml.txt").write_text("nope\n")

        with patch.object(main, "PRESETS_DIR", tmp_path):
            main.list_presets()
        captured = capsys.readouterr()
        assert "a.yaml" in captured.out
        assert "b.yml" in captured.out
        assert "not-yaml.txt" not in captured.out

    def test_missing_dir(self, capsys):
        with patch.object(main, "PRESETS_DIR", Path("/nonexistent/path")):
            main.list_presets()
        captured = capsys.readouterr()
        assert "沒有" in captured.out
