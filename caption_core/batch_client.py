"""
Multi-Pass Batch Client for Image Captioning (v6)

5-Pass sistemi:
  Pass 1: Yüz + Saç
  Pass 2: Vücut + Poz
  Pass 3: Kıyafet + Aksesuarlar
  Pass 4: Sahne + Teknik
  Pass 5: Natural Language Captioning (JSON-aware)

v6 Akış:
  Pass 1-4 → Pre-merge → Pass 5 (Image + Merged JSON) → Final Merge

Kullanım:
    # Local test (Ollama)
    python batch_client.py /path/to/images --model qwen2.5-vl:7b

    # Production (RunPod)
    python batch_client.py /path/to/images \\
        --server http://<RUNPOD_IP>:11434 \\
        --model huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct

    # Tek pass çalıştır
    python batch_client.py /path/to/images --pass 1

    # Sadece captioning (Pass 5)
    python batch_client.py /path/to/images --pass 5

    # JSON'ları birleştir
    python batch_client.py /path/to/images --merge
"""

import os
import sys
import json
import time
import base64
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# TQDM ile çakışmaması için logları sadece dosyaya veya kritik hatalarda basabiliriz
# Ya da sadece tqdm kullanacağımız için logları azaltabiliriz.
logger.setLevel(logging.WARNING) 

# ============================================ 
# Configuration
# ============================================ 
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
MAX_WORKERS = 4  # Paralel işlem sayısı
RETRY_COUNT = 3
RETRY_DELAY = 5

# Prompt dosyaları
PROMPTS_DIR = Path(__file__).parent / "prompts"
PASS_CONFIG = {
    1: {"file": "pass1_face_hair.txt", "suffix": "_pass1_face"},
    2: {"file": "pass2_body_pose.txt", "suffix": "_pass2_body"},
    3: {"file": "pass3_clothing.txt", "suffix": "_pass3_clothing"},
    4: {"file": "pass4_scene.txt", "suffix": "_pass4_scene"},
    5: {"file": "pass5_captioning.txt", "suffix": "_pass5_caption", "requires_merge": True},
}

# v6 metadata
VERSION = "6.0"


def load_prompt(pass_num: int) -> str:
    """Prompt dosyasını yükle"""
    config = PASS_CONFIG.get(pass_num)
    if not config:
        raise ValueError(f"Invalid pass number: {pass_num}")

    prompt_file = PROMPTS_DIR / config["file"]
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    return prompt_file.read_text(encoding="utf-8")


def prepare_pass5_prompt(image_path: Path, base_prompt: str) -> str:
    """Pass 5 için merged JSON'ı prompt'a enjekte et"""
    # Önce pass 1-4 dosyalarını dene
    merged = merge_json_files_partial(image_path, passes=[1, 2, 3, 4])

    # Eğer pass dosyaları yoksa, mevcut merged JSON'ı oku
    if not merged:
        final_json_path = image_path.with_suffix(".json")
        if final_json_path.exists():
            merged = json.loads(final_json_path.read_text(encoding="utf-8"))
            # captioning alanını çıkar (varsa) - sadece structured data kullan
            merged.pop("captioning", None)
            merged.pop("version", None)
            merged.pop("timestamp", None)

    if not merged:
        raise ValueError(f"No JSON data found for {image_path.name}. Run passes 1-4 first or ensure merged JSON exists.")

    # JSON'ı prompt'a enjekte et
    merged_json_str = json.dumps(merged, indent=2, ensure_ascii=False)
    return base_prompt.replace("{merged_json}", merged_json_str)


def encode_image_base64(image_path: Path) -> str:
    """Görseli base64'e çevir"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: Path) -> str:
    """Görsel MIME type"""
    suffix = image_path.suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".bmp": "image/bmp",
    }.get(suffix, "image/jpeg")


def call_ollama(
    server_url: str,
    image_path: Path,
    prompt: str,
    model: str,
    max_tokens: int = 1024,
    temperature: float = 0.3
) -> str:
    """Ollama API'ye istek (Vision modeli için)"""
    endpoint = f"{server_url.rstrip('/')}/api/chat"

    image_b64 = encode_image_base64(image_path)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64]
            }
        ],
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature
        }
    }

    for attempt in range(RETRY_COUNT):
        try:
            response = requests.post(endpoint, json=payload, timeout=300)
            response.raise_for_status()
            result = response.json()

            if "message" in result and "content" in result["message"]:
                return result["message"]["content"]
            raise Exception(f"Unexpected response: {result}")

        except Exception:
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise


def call_vllm(
    server_url: str,
    image_path: Path,
    prompt: str,
    model: str,
    max_tokens: int = 1024,
    temperature: float = 0.3
) -> str:
    """vLLM API'ye istek (OpenAI compatible)"""
    endpoint = f"{server_url.rstrip('/')}/v1/chat/completions"

    image_b64 = encode_image_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    image_url = f"data:{mime_type};base64,{image_b64}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    for attempt in range(RETRY_COUNT):
        try:
            response = requests.post(endpoint, json=payload, timeout=300)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            raise Exception(f"Unexpected response: {result}")

        except Exception:
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise


def extract_json(text: str) -> dict:
    """Metinden JSON çıkar"""
    original_text = text
    text = text.strip()

    # Markdown code block temizle
    if text.startswith("```"):
        lines = text.split("\n")
        # ```json veya ``` ile başlayan satırı atla
        start_idx = 1
        # Son ``` satırını atla
        end_idx = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start_idx:end_idx])
        text = text.strip()

    # Direkt parse dene
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # JSON objesini bul
    start = text.find("{")
    end = text.rfind("}") + 1

    if start != -1 and end > start:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Daha detaylı hata mesajı
            raise ValueError(f"Invalid JSON at position {e.pos}: {e.msg}. Text preview: {json_str[:100]}...")

    raise ValueError(f"No JSON object found in response. Preview: {original_text[:200]}...")


def process_single_image_pass(
    image_path: Path,
    server_url: str,
    pass_num: int,
    model: str,
    max_tokens: int,
    character_name: str = "woman",
    overwrite: bool = False,
    backend: str = "ollama"
) -> tuple[Path, bool, str]:
    """Tek görsel için tek pass"""

    config = PASS_CONFIG[pass_num]
    json_path = image_path.with_name(f"{image_path.stem}{config['suffix']}.json")

    if json_path.exists() and not overwrite:
        return image_path, True, "skipped"

    try:
        prompt = load_prompt(pass_num)

        # Pass 5 için özel işlem: merged JSON'ı prompt'a enjekte et
        if pass_num == 5:
            prompt = prepare_pass5_prompt(image_path, prompt)
        else:
            # Karakter ismi mantığı (Pass 1-4 için)
            if character_name and character_name not in ["woman", "man"]:
                prompt = prompt.replace("{character_name}", character_name)
            else:
                prompt = prompt.replace('CHARACTER NAME: "{character_name}"', 'CHARACTER NAME: Use "woman" or "man" as appropriate.')
                prompt = prompt.replace('CHARACTER: "{character_name}"', 'CHARACTER: Use "woman" or "man" as appropriate.')
                prompt = prompt.replace('"character": "{character_name}"', '"character": ""')

        # Backend seçimi
        if backend == "ollama":
            response = call_ollama(server_url, image_path, prompt, model, max_tokens)
        else:
            response = call_vllm(server_url, image_path, prompt, model, max_tokens)

        data = extract_json(response)
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return image_path, True, "done"

    except Exception as e:
        return image_path, False, f"error: {e}"


def merge_json_files_partial(image_path: Path, passes: list[int]) -> dict:
    """Belirli pass'ların JSON'larını birleştir (Pass 5 için pre-merge)"""
    merged = {}
    for pass_num in passes:
        config = PASS_CONFIG.get(pass_num)
        if not config:
            continue
        json_path = image_path.with_name(f"{image_path.stem}{config['suffix']}.json")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            merged = _deep_merge(merged, data)
    return merged


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge with array deduplication"""
    result = base.copy()
    for key, value in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Array merge: unique değerler
                combined = result[key] + value
                # Deduplicate while preserving order
                seen = set()
                unique = []
                for item in combined:
                    # Convert dict to tuple for hashability
                    hashable = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
                    if hashable not in seen:
                        seen.add(hashable)
                        unique.append(item)
                result[key] = unique
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def merge_json_files(image_path: Path, include_pass5: bool = True) -> dict:
    """Tüm pass JSON'larını birleştir (v6 format)"""
    merged = {}

    # Önce mevcut merged JSON'ı oku (varsa)
    final_json_path = image_path.with_suffix(".json")
    if final_json_path.exists():
        merged = json.loads(final_json_path.read_text(encoding="utf-8"))

    # Hangi pass'ları dahil edeceğimizi belirle
    passes_to_merge = [1, 2, 3, 4]
    if include_pass5:
        passes_to_merge.append(5)

    # Pass dosyalarını merge et (varsa)
    for pass_num in passes_to_merge:
        config = PASS_CONFIG.get(pass_num)
        if not config:
            continue
        json_path = image_path.with_name(f"{image_path.stem}{config['suffix']}.json")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            merged = _deep_merge(merged, data)

    # v6 metadata ekle
    if merged:
        merged["version"] = VERSION
        merged["timestamp"] = datetime.now(timezone.utc).isoformat()

    return merged


def check_server_health(server_url: str, backend: str) -> bool:
    """Server'a bağlantıyı kontrol et"""
    try:
        if backend == "ollama":
            endpoint = f"{server_url.rstrip('/')}/api/tags"
        else:
            endpoint = f"{server_url.rstrip('/')}/v1/models"

        response = requests.get(endpoint, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def process_folder(
    folder_path: str,
    server_url: str,
    pass_nums: list,
    model: str,
    max_tokens: int,
    max_workers: int,
    character_name: str,
    overwrite: bool,
    merge_only: bool,
    backend: str = "ollama",
    progress_cb=None,
    cancel_event=None,
):
    """Klasördeki görselleri işle.

    progress_cb: opsiyonel Callable[[int, int, int, int, str, dict], None] —
                 (pass_idx_1based, total_passes, current_img, total_imgs, msg, stats)
                 olarak çağrılır. `stats` = tüm pass'lar boyunca kümülatif
                 {"success": int, "skipped": int, "failed": int}. UI img/s ve ETA
                 hesabı için success'i baz alır (skipped'lerde gerçek inference yok).
                 CLI tqdm bağımsız çalışmaya devam eder.
    cancel_event: opsiyonel threading.Event — set olursa pending future'lar
                  iptal edilir ve process_folder döner.
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        return

    images = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not images:
        print(f"Warning: No images found in {folder}")
        return

    print(f"Found {len(images)} images in {folder}")
    total_passes = len(pass_nums) if not merge_only else 1

    def _is_cancelled() -> bool:
        return bool(cancel_event is not None and cancel_event.is_set())

    if merge_only:
        print("Merging JSON files...")
        merged_count = 0
        deleted_count = 0
        # Merge için stats: her tamamlanan dosya "success" sayılır (gerçek iş, hızlı)
        merge_stats = {"success": 0, "skipped": 0, "failed": 0}
        if progress_cb:
            progress_cb(
                1, 1, 0, len(images), "Merging başlatılıyor…",
                dict(merge_stats),
            )
        for idx, img in enumerate(tqdm(images, desc="Merging"), 1):
            if _is_cancelled():
                if progress_cb:
                    progress_cb(
                        1, 1, idx - 1, len(images), "İptal edildi",
                        dict(merge_stats),
                    )
                print("Cancelled by user")
                return
            merged = merge_json_files(img)
            if merged:
                final_path = img.with_suffix(".json")
                final_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
                merged_count += 1

                # Pass dosyalarını sil
                for pass_num, config in PASS_CONFIG.items():
                    pass_file = img.with_name(f"{img.stem}{config['suffix']}.json")
                    if pass_file.exists():
                        pass_file.unlink()
                        deleted_count += 1
            merge_stats["success"] += 1
            if progress_cb:
                progress_cb(
                    1, 1, idx, len(images), f"Merge: {idx}/{len(images)}",
                    dict(merge_stats),
                )

        print(f"Merge complete: {merged_count}/{len(images)} files")
        print(f"Deleted {deleted_count} pass files")
        return

    # Server health check
    print(f"Checking server connection: {server_url}")
    if not check_server_health(server_url, backend):
        print(f"Error: Cannot connect to server at {server_url}")
        print("Make sure the server is running and accessible.")
        return
    print("Server OK")

    # Track overall statistics
    total_stats = {"success": 0, "skipped": 0, "failed": 0}

    for pass_idx, pass_num in enumerate(pass_nums, 1):
        if _is_cancelled():
            print("Cancelled before pass start")
            if progress_cb:
                progress_cb(
                    pass_idx, total_passes, 0, len(images), "İptal edildi",
                    dict(total_stats),
                )
            return

        print(f"\n{'='*50}")
        print(f"Processing Pass {pass_num}/5: {PASS_CONFIG[pass_num]['file']}")
        print(f"{'='*50}")

        pass_stats = {"success": 0, "skipped": 0, "failed": 0}
        failed_images = []
        completed = 0

        if progress_cb:
            progress_cb(
                pass_idx, total_passes, 0, len(images),
                f"Pass {pass_num} başlatılıyor",
                dict(total_stats),
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    process_single_image_pass,
                    img, server_url, pass_num, model, max_tokens, character_name, overwrite, backend
                ) for img in images
            ]

            with tqdm(total=len(images), desc=f"Pass {pass_num}", unit="img") as pbar:
                cancelled = False
                for future in as_completed(futures):
                    if _is_cancelled():
                        # Pending future'ları iptal et, döngüden çık.
                        # cancel_futures=True → henüz başlamamış olanları drop'lar;
                        # in-flight olanlar HTTP timeout süresince devam edebilir.
                        executor.shutdown(wait=False, cancel_futures=True)
                        cancelled = True
                        break

                    img_path, ok, msg = future.result()

                    # pass_stats + total_stats anında güncellenir → UI rate hesabı
                    # skipped'leri payda dışı tutabilsin diye total_stats canlı akar.
                    if ok:
                        if msg == "skipped":
                            pass_stats["skipped"] += 1
                            total_stats["skipped"] += 1
                        else:
                            pass_stats["success"] += 1
                            total_stats["success"] += 1
                    else:
                        pass_stats["failed"] += 1
                        total_stats["failed"] += 1
                        failed_images.append((img_path.name, msg))
                        pbar.write(f"FAIL {img_path.name}: {msg}")

                    completed += 1
                    pbar.update(1)
                    if progress_cb:
                        progress_cb(
                            pass_idx, total_passes, completed, len(images),
                            f"Pass {pass_num}: {completed}/{len(images)}",
                            dict(total_stats),
                        )

        if cancelled:
            print(f"Pass {pass_num} cancelled at {completed}/{len(images)}")
            if progress_cb:
                progress_cb(
                    pass_idx, total_passes, completed, len(images),
                    f"Pass {pass_num} iptal edildi",
                    dict(total_stats),
                )
            return

        # Pass summary
        print(f"\nPass {pass_num} Summary:")
        print(f"  Success: {pass_stats['success']}")
        print(f"  Skipped: {pass_stats['skipped']}")
        print(f"  Failed:  {pass_stats['failed']}")

        if failed_images:
            print(f"\nFailed images:")
            for name, err in failed_images[:5]:
                print(f"  - {name}: {err[:50]}...")
            if len(failed_images) > 5:
                print(f"  ... and {len(failed_images) - 5} more")
        # total_stats artık per-future güncelleniyor; duplicate toplama gerekmez.

    # Final summary
    print(f"\n{'='*50}")
    print("FINAL SUMMARY")
    print(f"{'='*50}")
    print(f"Total Success: {total_stats['success']}")
    print(f"Total Skipped: {total_stats['skipped']}")
    print(f"Total Failed:  {total_stats['failed']}")
    print(f"{'='*50}")

    # Eğer tüm pass'lar çalıştıysa otomatik merge yap
    if pass_nums == [1, 2, 3, 4, 5]:
        print(f"\nAuto-merging JSON files...")
        merged_count = 0
        deleted_count = 0
        for img in images:
            merged = merge_json_files(img)
            if merged:
                final_path = img.with_suffix(".json")
                final_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
                merged_count += 1

                # Pass dosyalarını sil
                for pass_num, config in PASS_CONFIG.items():
                    pass_file = img.with_name(f"{img.stem}{config['suffix']}.json")
                    if pass_file.exists():
                        pass_file.unlink()
                        deleted_count += 1

        print(f"Merge complete: {merged_count} files")
        print(f"Deleted {deleted_count} pass files")


def main():
    parser = argparse.ArgumentParser(description="Multi-pass image captioning")
    parser.add_argument("folder", type=str, help="Image folder path")
    parser.add_argument("--backend", type=str, default="ollama", choices=["ollama", "vllm"],
                        help="Backend: ollama (default) or vllm")
    parser.add_argument("--server", type=str, default="http://localhost:11434",
                        help="Server URL (default: http://localhost:11434 for Ollama)")
    parser.add_argument("--model", type=str, default="huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
                        help="Model name")
    parser.add_argument("--pass", dest="pass_num", type=str, default="all",
                        help="Pass number (1-5) or 'all' (default: all)")
    parser.add_argument("--character", type=str, default="woman",
                        help="Character name to use in prompts")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--merge", action="store_true", help="Merge existing pass files")

    args = parser.parse_args()

    # Pass numarasını parse et
    if args.pass_num == "all":
        pass_nums = [1, 2, 3, 4, 5]
    else:
        pass_num = int(args.pass_num)
        if pass_num < 1 or pass_num > 5:
            print(f"Error: Invalid pass number: {pass_num}. Must be 1-5 or 'all'")
            return
        pass_nums = [pass_num]

    # vLLM için default port değiştir
    if args.backend == "vllm" and args.server == "http://localhost:11434":
        args.server = "http://localhost:8000"

    print(f"Backend: {args.backend}")
    print(f"Server: {args.server}")
    print(f"Model: {args.model}")

    process_folder(
        folder_path=args.folder,
        server_url=args.server,
        pass_nums=pass_nums,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.workers,
        character_name=args.character,
        overwrite=args.overwrite,
        merge_only=args.merge,
        backend=args.backend
    )


if __name__ == "__main__":
    main()