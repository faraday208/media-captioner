# Image Captioner (v6)

Qwen3-VL-30B ile görsel captioning için multi-pass sistem.

**v6 Yenilikleri:**
- 5-Pass sistemi (Pass 5: Natural Language Captioning)
- JSON-aware captioning (structured data ile tutarlı)
- 3 caption uzunluğu: short/medium/long
- `json_to_txt.py` - Caption'ları TXT'ye çıkarma

## Mimari

```
┌─────────────────┐              ┌─────────────────────────────┐
│  LOCAL CLIENT   │    HTTP      │      REMOTE SERVER          │
│                 │ ──────────►  │                             │
│  [Resimler]     │   base64     │  Ollama / vLLM              │
│  batch_client   │ ◄──────────  │  Qwen3-VL-30B               │
│  [JSON Output]  │    JSON      │                             │
└─────────────────┘              └─────────────────────────────┘
```

## Yapı

```
06-caption/
├── WORKFLOW.md           # Detaylı workflow dokümanı
├── README.md             # Bu dosya
│
├── server/               # RunPod Server (Ollama)
│   ├── setup.sh          # İlk kurulum
│   ├── start_ollama.sh   # Ollama server başlatma
│   └── README.md
│
└── client/               # Local Client
    ├── batch_client.py   # Ana captioning scripti (v6)
    ├── json_to_txt.py    # JSON'dan TXT caption çıkarma
    ├── requirements.txt  # Python bağımlılıkları
    ├── v6_detailed_json.txt  # v6 JSON şeması
    └── prompts/          # 5-pass prompt dosyaları
        ├── pass1_face_hair.txt
        ├── pass2_body_pose.txt
        ├── pass3_clothing.txt
        ├── pass4_scene.txt
        └── pass5_captioning.txt  # Natural language captioning
```

## Hızlı Başlangıç

### Local Kullanım (Önerilen)

```bash
cd /opt/media-pipeline/dataset-prep/06-caption

# Ollama localhost'ta çalışıyorsa
python3 client/batch_client.py /path/to/images \
    --backend ollama \
    --server http://localhost:11434 \
    --model huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct \
    --character "CharacterName" \
    --pass all \
    --workers 1
```

### Remote Server (RunPod)

```bash
# Tüm pass'ları çalıştır
python client/batch_client.py ./images \
    --backend ollama \
    --server http://<RUNPOD_IP>:11434 \
    --model huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct \
    --workers 4 \
    --pass all
```

## CLI Parametreleri

### batch_client.py

| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| `folder` | (zorunlu) | Görsel klasörü |
| `--backend` | `ollama` | Backend: `ollama` veya `vllm` |
| `--server` | `http://localhost:11434` | Server URL |
| `--model` | `huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct` | Model adı |
| `--pass` | `all` | Pass numarası: `1`, `2`, `3`, `4`, `5` veya `all` |
| `--character` | `woman` | Karakter adı (prompt'larda ve caption'larda kullanılır) |
| `--workers` | `4` | Paralel işlem sayısı |
| `--max-tokens` | `1024` | Maksimum token sayısı |
| `--overwrite` | `false` | Mevcut JSON'ları üzerine yaz |
| `--merge` | `false` | Sadece mevcut pass dosyalarını birleştir |

### json_to_txt.py

| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| `folder` | (zorunlu) | JSON dosyalarının bulunduğu klasör |
| `--type` | (zorunlu) | Caption tipi: `short`, `medium`, `long` |
| `--overwrite` | `false` | Mevcut TXT'leri üzerine yaz |

```bash
# Örnek kullanım
python3 json_to_txt.py /path/to/images --type long --overwrite
```

## 5-Pass Sistemi (v6)

| Pass | Odak | Output |
|------|------|--------|
| 1 | Saç + Yüz İfadesi | `*_pass1_face.json` |
| 2 | Vücut + Poz | `*_pass2_body.json` |
| 3 | Kıyafet + Aksesuarlar | `*_pass3_clothing.json` |
| 4 | Sahne + Teknik | `*_pass4_scene.json` |
| 5 | Natural Language Captioning | `*_pass5_caption.json` |

### v6 Akış

```
Pass 1-4 → Structured JSON
    ↓
Pass 5 (Image + Merged JSON → Captioning)
    ↓
Final Merge → image.json (structured + captions)
    ↓
json_to_txt.py → image.txt (training için)
```

### Captioning Özellikleri

- **JSON-aware:** Pass 5, structured data'yı görerek tutarlı caption üretir
- **Karakter ismi:** `--character Aria` → Caption'larda "Aria" kullanılır
- **3 uzunluk:**
  - `short`: 15-25 kelime, 1 cümle
  - `medium`: 40-60 kelime, 2-3 cümle
  - `long`: 80-120 kelime, 4-5 cümle

`--pass all` kullanıldığında tüm pass'lar çalıştırılır ve otomatik olarak tek bir JSON dosyasına birleştirilir (`image.json`).

## Gereksinimler

**Client (Local):**
- Python 3.10+
- `requests`, `tqdm`

**Server (Ollama):**
- Ollama kurulu
- Qwen3-VL modeli (`ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct`)

## Detaylı Dokümantasyon

Tam workflow için: [WORKFLOW.md](WORKFLOW.md)
