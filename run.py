#!/usr/bin/env python3
"""
Media Captioner — CLI wrapper

Multi-pass image captioning (Qwen3-VL, Ollama backend). batch_client.py'nin
zengin pass logic'i korundu; bu wrapper convention §uyumlu standart flag'ler
(-i, --output, --recursive, --report) sunar ve sidecar JSON rapor üretir.

Direkt batch_client kullanımı (5-pass + threading + retry) için:
  python -m caption_core.batch_client /path/to/images --model qwen2.5-vl:7b

Bu wrapper kullanışlı:
  # Tek komut: tüm pass'ler + caption export
  python run.py -i ./dataset --model qwen2.5-vl:7b

  # Sadece export (önceki run'dan kalan JSON'ları text'e çıkar)
  python run.py -i ./dataset --export-only --caption-type medium

  # Geri al (caption JSON + TXT dosyalarını sil)
  python run.py --undo ./dataset/caption_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPORT_TOOL = "media-captioner"
DEFAULT_REPORT_NAME = "caption_report.json"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Media Captioner — multi-pass VLM captioning (Qwen3-VL/Ollama)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-i", "--input", help="Input klasörü (zorunlu, --undo hariç)")
    p.add_argument("--model", default="qwen2.5-vl:7b",
                   help="Ollama model adı (default: qwen2.5-vl:7b)")
    p.add_argument("--server", default="http://localhost:11434",
                   help="Ollama server URL (default: localhost:11434)")
    p.add_argument("--workers", type=int, default=4,
                   help="Paralel worker sayısı (default: 4)")
    p.add_argument("--pass", dest="pass_num", type=int, choices=[1, 2, 3, 4, 5],
                   help="Sadece tek pass çalıştır (1-5)")
    p.add_argument("--export-only", action="store_true",
                   help="Sadece JSON → TXT export (caption etmeden)")
    p.add_argument("--caption-type", choices=["short", "medium", "long"],
                   default="medium", help="Export için caption uzunluğu")
    p.add_argument("--report", help=f"Rapor JSON yolu (default: <input>/{DEFAULT_REPORT_NAME})")
    p.add_argument("--undo", help="Caption raporundan JSON+TXT dosyalarını sil")
    return p


def _run_undo(report_path: Path) -> int:
    """Caption raporundan oluşturulmuş JSON + TXT dosyalarını sil."""
    if not report_path.exists():
        print(f"Rapor bulunamadı: {report_path}", file=sys.stderr)
        return 1
    with open(report_path) as f:
        report = json.load(f)
    if report.get("tool") != REPORT_TOOL:
        print(f"Tool mismatch: {report.get('tool')!r}", file=sys.stderr)
        return 1
    removed = skipped = 0
    for entry in report.get("actions", []):
        for path_str in entry.get("created_files", []):
            p = Path(path_str)
            if p.exists():
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    skipped += 1
            else:
                skipped += 1
    print(f"Removed: {removed}, Skipped: {skipped}")
    return 0


def _run_caption(args: argparse.Namespace, input_dir: Path) -> int:
    """batch_client.py'yi sarmal — Multi-pass captioning çalıştır."""
    from caption_core import batch_client

    # batch_client'ın main fonksiyonu yok; CLI olarak subprocess gibi çağıramayız
    # Ama batch_client'ın __name__ == '__main__' bloğu var. Direct import
    # logic'i kullanıp çağırırız.
    # En basit: argparse ile aynı flag'leri batch_client'a geçir.
    sys.argv = ["batch_client.py", str(input_dir),
                "--model", args.model,
                "--server", args.server,
                "--workers", str(args.workers)]
    if args.pass_num:
        sys.argv += ["--pass", str(args.pass_num)]

    # batch_client.py module-level kod yok (her şey if __name__'de)
    # Module fonksiyonlarını direkt çağıramıyoruz; aslında batch_client.py
    # standalone CLI'dır. Subprocess yerine içe bağlamak için modül scriptini
    # exec et:
    import runpy
    try:
        runpy.run_module("caption_core.batch_client", run_name="__main__")
    except SystemExit as e:
        if e.code and e.code != 0:
            return int(e.code)
    return 0


def _run_export(input_dir: Path, caption_type: str) -> int:
    from caption_core.json_to_txt import extract_captions
    extract_captions(str(input_dir), caption_type, overwrite=False)
    return 0


def _write_report(input_dir: Path, args: argparse.Namespace,
                   *, captioned: int, exported: int, action_files: list[str]) -> Path:
    """Sidecar JSON — convention §4 uyumlu."""
    report_path = Path(args.report) if args.report else input_dir / DEFAULT_REPORT_NAME
    payload = {
        "version": "1",
        "tool": REPORT_TOOL,
        "source_root": str(input_dir.resolve()),
        "timestamp": datetime.now().isoformat(),
        "config": {
            "model": args.model,
            "server": args.server,
            "workers": args.workers,
            "pass": args.pass_num,
            "export_caption_type": args.caption_type,
        },
        "summary": {
            "captioned": captioned,
            "exported": exported,
        },
        # actions[]: undo için yaratılan dosyaların listesi
        "actions": [{"created_files": action_files}] if action_files else [],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return report_path


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.undo:
        return _run_undo(Path(args.undo))

    if not args.input:
        parser.error("--input gerekli (veya --undo kullan)")

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"Geçerli dizin değil: {input_dir}", file=sys.stderr)
        return 1

    print(f"\n{'='*70}")
    print(f"Media Captioner")
    print(f"{'='*70}")
    print(f"Input:   {input_dir}")
    print(f"Model:   {args.model}")
    print(f"Server:  {args.server}")
    print(f"Workers: {args.workers}")
    if args.pass_num:
        print(f"Pass:    {args.pass_num}")
    print(f"Mode:    {'export-only' if args.export_only else 'caption + export'}")
    print(f"{'='*70}\n")

    if args.export_only:
        rc = _run_export(input_dir, args.caption_type)
    else:
        rc = _run_caption(args, input_dir)
        if rc == 0:
            _run_export(input_dir, args.caption_type)

    # Rapor yaz (yaratılan dosyaları topla)
    action_files: list[str] = []
    for p in input_dir.rglob("*.json"):
        action_files.append(str(p))
    for p in input_dir.rglob("*.txt"):
        action_files.append(str(p))

    report = _write_report(
        input_dir, args,
        captioned=len(list(input_dir.rglob("*.json"))),
        exported=len(list(input_dir.rglob("*.txt"))),
        action_files=action_files,
    )
    print(f"\nRapor: {report}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
