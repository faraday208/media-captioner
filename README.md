# media-captioner

> Medya görsellerini Qwen3-VL (Ollama) ile multi-pass JSON caption üretimi.
> 5 ayrı detay pass'i (yüz, vücut, kıyafet, sahne, doğal dil) → birleştirilmiş
> JSON → TXT export.

[![tests](https://github.com/faraday208/media-captioner/actions/workflows/tests.yml/badge.svg)](https://github.com/faraday208/media-captioner/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/built%20with-uv-261230)](https://github.com/astral-sh/uv)

`media-dataset-prep` pipeline'ının **06. adımı**. Standalone kullanılabilir.

---

## 🎯 Ne yapıyor?

5-pass captioning sistemi:

| Pass | Odak | Çıktı suffix |
|---|---|---|
| 1 | Yüz + Saç | `_pass1_face.json` |
| 2 | Vücut + Poz | `_pass2_body.json` |
| 3 | Kıyafet + Aksesuarlar | `_pass3_clothing.json` |
| 4 | Sahne + Teknik | `_pass4_scene.json` |
| 5 | Natural Language Captioning (JSON-aware) | `_pass5_caption.json` |

Akış:
1. Pass 1-4 paralel çalışır (her pass image + custom prompt → structured JSON)
2. Pre-merge: JSON'lar birleştirilir
3. Pass 5: image + merged JSON → 3 farklı uzunlukta caption (`short`, `medium`, `long`)
4. Final merge: `<image>.json` (tüm pass'ler + caption'lar)
5. Export: `<image>.txt` (seçilen caption_type)

LoRA training için `<image>.jpg ↔ <image>.txt` eşleşmesi pipeline'ın çıktısı.

---

## 🚀 Kurulum

```bash
git clone https://github.com/faraday208/media-captioner
cd media-captioner
uv sync
```

`media-dataset-prep` workspace altında: `make install`

### Ollama backend

```bash
ollama pull qwen2.5-vl:7b              # Lokal hızlı test
ollama pull qwen3-vl-abliterated:30b   # Production quality
```

Server localhost'ta default. Remote için `--server http://IP:11434`.

---

## 🛠️ Kullanım — CLI

### Tek komut: tüm pass'ler + export (önerilen)

```bash
uv run python run.py -i ./dataset --model qwen2.5-vl:7b
```

### Production (RunPod / remote Ollama)

```bash
uv run python run.py -i ./dataset \
    --model huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct \
    --server http://<RUNPOD_IP>:11434 \
    --workers 8
```

### Sadece tek pass

```bash
uv run python run.py -i ./dataset --pass 5
```

### Sadece export (önceki run'dan kalan JSON'lardan TXT)

```bash
uv run python run.py -i ./dataset --export-only --caption-type long
```

### Geri al (caption JSON + TXT dosyalarını sil)

```bash
uv run python run.py --undo ./dataset/caption_report.json
```

### Direkt batch_client (tüm zengin flag'ler)

```bash
python -m caption_core.batch_client /path/to/images --model qwen2.5-vl:7b
python -m caption_core.batch_client /path/to/images --pass 1
python -m caption_core.batch_client /path/to/images --merge
```

---

## 📋 Operation modes — özet

| Mod | Komut | Etki | Undo |
|---|---|---|---|
| **Full caption + export** (default) | `run.py -i ./ds` | 5 pass + JSON + TXT | ✓ |
| **Tek pass** | `--pass N` | Sadece pass N JSON | – |
| **Export only** | `--export-only` | Mevcut JSON'lardan TXT | – |
| **Undo** | `--undo REPORT` | JSON + TXT dosyalarını sil | – |

---

## 🚩 Tüm CLI flag'leri

| Flag | Tip | Default | Açıklama |
|---|---|---|---|
| `-i, --input` | str | – | Input klasörü (zorunlu, `--undo` hariç) |
| `--model` | str | `qwen2.5-vl:7b` | Ollama model adı |
| `--server` | str | `http://localhost:11434` | Ollama server URL |
| `--workers` | int | 4 | Paralel worker sayısı |
| `--pass` | int (1-5) | – | Sadece tek pass çalıştır |
| `--export-only` | flag | False | Sadece JSON → TXT (caption etmeden) |
| `--caption-type` | `short\|medium\|long` | `medium` | Export caption uzunluğu |
| `--report` | str | `<input>/caption_report.json` | Sidecar JSON yolu |
| `--undo` | str | – | Caption raporundan dosyaları sil |

---

## 🔌 In-process (library) kullanım

```python
from caption_core import batch_client, json_to_txt

# Multi-pass çalıştır (subprocess yerine)
# (batch_client.py CLI ana — refactor sonrası fonksiyon-tabanlı API gelecek)

# JSON → TXT export
json_to_txt.extract_captions("./dataset", "medium")
```

---

## 📄 Rapor formatı

```jsonc
{
  "version": "1",
  "tool": "media-captioner",
  "source_root": "/abs/path",
  "timestamp": "2026-05-09T...",
  "config": {
    "model": "qwen2.5-vl:7b",
    "server": "http://localhost:11434",
    "workers": 4,
    "pass": null,
    "export_caption_type": "medium"
  },
  "summary": {"captioned": 100, "exported": 100},
  "actions": [
    {"created_files": [
      "/abs/.../img1.json",
      "/abs/.../img1.txt",
      "/abs/.../img1_pass1_face.json"
    ]}
  ]
}
```

`actions[].created_files` `--undo` için kullanılır.

---

## 🧪 Test

```bash
uv sync --group dev
uv run pytest
```

15 test: package import + PASS_CONFIG + prompt loading + json_to_txt (filter pass dosyaları + export) + run.py argparse + export-only e2e + undo snapshot-diff (yabancı dosya koruması).

---

## ⚠️ Limitations

- **Ollama backend gerekli** (lokal veya remote). Bağımsız VLM yok
- Tüm modeller `Qwen2.5-VL` veya `Qwen3-VL-30B` test edildi; başka VLM'ler için prompt'lar tune gerekir
- `--undo` sadece **bu run'da yaratılan** JSON + TXT dosyaları siler (snapshot-diff ile yabancı dosyalardan ayırt edilir); selective değil — çağrının tüm çıktılarını topluca siler
- Multi-pass uzun sürer: 7B model ~10 sn/dosya, 30B ~30 sn/dosya
- İmage encoding base64 — büyük görsellerde RAM tüketimi
- Pre-merge için kullanıcı manuel doğrulama gerekebilir (Pass 1-4 JSON tutarlılığı)

---

## 🏷️ Sürüm

**v1.0.1** — kritik undo veri kaybı bug fix. Önceki davranışta `--undo` dataset klasöründeki TÜM `*.json` ve `*.txt` dosyalarını siliyordu (önceki pipeline adımlarından kalan `quality_report.json`, kullanıcının `README.txt` notları, vb. dahil). Snapshot-diff yaklaşımıyla artık sadece bu run'da yaratılan dosyalar undo listesine giriyor. +1 regression testi (15 toplam).

**v1.0.0** — clean release. `image-captioner` → `media-captioner`. Convention §uyumlu refactor:
- 5 alt-klasör (client/, server/, tools/, archive/) → `caption_core/` paketi
- Gradio json-debugger (tools/json-debugger) silindi (ayrı tool olabilir)
- Server scripts (Ollama setup) silindi (kullanıcının sorumluluğu)
- archive/ silindi (eski versiyon backup)
- run.py wrapper (argparse) eklendi — sidecar JSON üretir
- pyproject: gradio + pandas + numpy dependency'leri kaldırıldı (sadece requests + tqdm + pillow)
- 15 test (package + prompt + json_to_txt + CLI + undo snapshot-diff güvenliği)

batch_client.py'nin 584 satırlık multi-pass logic'i korundu (zengin flag'leri ile direkt erişilebilir).

---

## 📜 Lisans

[MIT](LICENSE)
