#!/usr/bin/env python3
"""
JSON to TXT Caption Extractor

JSON dosyalarından caption çıkarıp TXT'ye yazar.

Kullanım:
    python json_to_txt.py /path/to/folder --type short
    python json_to_txt.py /path/to/folder --type medium
    python json_to_txt.py /path/to/folder --type long
"""

import argparse
import json
from pathlib import Path


def extract_captions(folder_path: str, caption_type: str, overwrite: bool = False):
    """JSON dosyalarından caption çıkar ve TXT'ye yaz"""
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        return

    json_files = list(folder.glob("*.json"))

    # Pass dosyalarını filtrele (sadece merged JSON'lar)
    json_files = [f for f in json_files if not any(
        suffix in f.name for suffix in ["_pass1_", "_pass2_", "_pass3_", "_pass4_", "_pass5_"]
    )]

    if not json_files:
        print(f"Warning: No JSON files found in {folder}")
        return

    print(f"Found {len(json_files)} JSON files")
    print(f"Extracting '{caption_type}' captions...")

    success = 0
    skipped = 0
    errors = []

    for json_path in json_files:
        txt_path = json_path.with_suffix(".txt")

        # Overwrite kontrolü
        if txt_path.exists() and not overwrite:
            skipped += 1
            continue

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))

            # Caption'ı al
            captioning = data.get("captioning", {})
            caption = captioning.get(caption_type, "")

            if not caption:
                errors.append((json_path.name, f"No '{caption_type}' caption found"))
                continue

            # TXT'ye yaz
            txt_path.write_text(caption, encoding="utf-8")
            success += 1

        except json.JSONDecodeError as e:
            errors.append((json_path.name, f"Invalid JSON: {e}"))
        except Exception as e:
            errors.append((json_path.name, str(e)))

    # Özet
    print(f"\nResults:")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {len(errors)}")

    if errors:
        print(f"\nErrors:")
        for name, err in errors[:10]:
            print(f"  - {name}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")


def main():
    parser = argparse.ArgumentParser(description="Extract captions from JSON to TXT")
    parser.add_argument("folder", type=str, help="Folder containing JSON files")
    parser.add_argument("--type", dest="caption_type", type=str, required=True,
                        choices=["short", "medium", "long"],
                        help="Caption type to extract: short, medium, or long")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing TXT files")

    args = parser.parse_args()

    extract_captions(args.folder, args.caption_type, args.overwrite)


if __name__ == "__main__":
    main()
