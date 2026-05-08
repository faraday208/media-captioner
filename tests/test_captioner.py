"""Captioner: package import, prompt loading, json_to_txt, run.py argparse."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------- Package import ----------

def test_package_imports():
    from caption_core import batch_client, json_to_txt
    assert batch_client is not None
    assert json_to_txt is not None


def test_batch_client_has_pass_config():
    from caption_core.batch_client import PASS_CONFIG
    # 5 pass tanımlı
    assert set(PASS_CONFIG.keys()) == {1, 2, 3, 4, 5}
    # Her pass'in dosya tanımı var
    for cfg in PASS_CONFIG.values():
        assert "file" in cfg
        assert "suffix" in cfg


def test_batch_client_supported_extensions():
    from caption_core.batch_client import SUPPORTED_EXTENSIONS
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".png" in SUPPORTED_EXTENSIONS


# ---------- Prompts ----------

def test_prompt_files_exist():
    """5 pass prompt dosyası caption_core/prompts/ altında var mı?"""
    prompts_dir = REPO_ROOT / "caption_core" / "prompts"
    assert prompts_dir.is_dir()
    for i in range(1, 6):
        # Pass dosya ismini PASS_CONFIG'den al
        from caption_core.batch_client import PASS_CONFIG
        fname = PASS_CONFIG[i]["file"]
        assert (prompts_dir / fname).is_file(), f"{fname} eksik"


def test_load_prompt_returns_text():
    from caption_core.batch_client import load_prompt
    text = load_prompt(1)
    assert isinstance(text, str)
    assert len(text) > 0


# ---------- json_to_txt ----------

def test_extract_captions_short(caption_dataset: Path, capsys):
    from caption_core.json_to_txt import extract_captions
    extract_captions(str(caption_dataset), "short")
    # img1.txt + img2.txt yazıldı
    assert (caption_dataset / "img1.txt").exists()
    assert (caption_dataset / "img2.txt").exists()
    # İçerik
    assert "red car" in (caption_dataset / "img1.txt").read_text()


def test_extract_captions_long(caption_dataset: Path):
    from caption_core.json_to_txt import extract_captions
    extract_captions(str(caption_dataset), "long")
    assert (caption_dataset / "img1.txt").exists()
    text = (caption_dataset / "img1.txt").read_text()
    assert "golden hour" in text


def test_extract_captions_filters_pass_files(caption_dataset: Path, capsys):
    """Pass JSON dosyaları (img1_pass1_face.json) atlanmalı."""
    from caption_core.json_to_txt import extract_captions
    extract_captions(str(caption_dataset), "medium")
    # img1_pass1_face.txt YAZILMADIĞINI kanıtla
    assert not (caption_dataset / "img1_pass1_face.txt").exists()


def test_extract_captions_invalid_dir(tmp_path: Path, capsys):
    from caption_core.json_to_txt import extract_captions
    extract_captions(str(tmp_path / "nope"), "short")
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "bulunamadı" in out.lower()


# ---------- run.py ----------

def test_run_parser_defaults():
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from run import _build_parser
        args = _build_parser().parse_args(["-i", "/tmp/x"])
        assert args.input == "/tmp/x"
        assert args.model == "qwen2.5-vl:7b"
        assert args.workers == 4
        assert args.caption_type == "medium"
    finally:
        sys.path.pop(0)


def test_run_parser_full_flags():
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from run import _build_parser
        args = _build_parser().parse_args([
            "-i", "/tmp/x",
            "--model", "qwen3-vl:30b",
            "--server", "http://1.2.3.4:11434",
            "--workers", "8",
            "--pass", "3",
            "--caption-type", "long",
        ])
        assert args.model == "qwen3-vl:30b"
        assert args.server == "http://1.2.3.4:11434"
        assert args.workers == 8
        assert args.pass_num == 3
    finally:
        sys.path.pop(0)


def test_run_input_required(monkeypatch):
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from run import main
        monkeypatch.setattr(sys, "argv", ["run.py"])
        with pytest.raises(SystemExit):
            main()
    finally:
        sys.path.pop(0)


def test_run_export_only_works(monkeypatch, caption_dataset: Path):
    """--export-only Ollama'ya bağlanmadan JSON → TXT yapar."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from run import main
        monkeypatch.setattr(sys, "argv", [
            "run.py", "-i", str(caption_dataset),
            "--export-only", "--caption-type", "short",
        ])
        rc = main()
        assert rc == 0
        # img1.txt yazıldı
        assert (caption_dataset / "img1.txt").exists()
    finally:
        sys.path.pop(0)


def test_run_undo_with_invalid_report(monkeypatch, tmp_path: Path):
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from run import main
        monkeypatch.setattr(sys, "argv", ["run.py", "--undo", str(tmp_path / "nope.json")])
        rc = main()
        assert rc == 1
    finally:
        sys.path.pop(0)
