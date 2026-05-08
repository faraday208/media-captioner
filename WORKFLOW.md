# Image Captioner Workflow (v6)

> AI görsel dataset'leri için multi-pass captioning sistemi

**Son Güncelleme**: 2026-01-21
**Versiyon**: 6.0

### v6 Değişiklikleri
- 5-Pass sistemi (Pass 5: Natural Language Captioning)
- JSON-aware captioning (structured data ile tutarlı caption üretimi)
- Karakter ismi desteği (caption'larda kullanılır)
- `json_to_txt.py` - Caption'ları TXT'ye çıkarma aracı

---

## Genel Bakış

```
┌─────────────────────────────────────────────────────────────────┐
│                        WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ┌─────────────────┐              ┌─────────────────────────────┐│
│ │  LOCAL CLIENT   │              │      REMOTE SERVER          ││
│ │                 │              │                             ││
│ │  [Resimler]     │    HTTP      │  Phase 1: Ollama (7B) local ││
│ │  Local Disk     │ ──────────►  │  Phase 2: Ollama (30B)      ││
│ │                 │   base64     │           RunPod            ││
│ │  batch_client   │ ◄──────────  │  A40 48GB                   ││
│ │                 │    JSON      │                             ││
│ │  [JSON Output]  │              │                             ││
│ └─────────────────┘              └─────────────────────────────┘│
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Phase 1: LOCAL TEST                                           │
│   ├── Ollama + Qwen2.5-VL-7B                                    │
│   ├── 12GB VRAM yeterli                                         │
│   └── Prompt'ları doğrula (ücretsiz)                            │
│                                                                  │
│   Phase 2: RUNPOD PRODUCTION                                    │
│   ├── Ollama + Qwen3-VL-30B-A3B                                 │
│   ├── A40 48GB (tek kart)                                       │
│   └── 4-Pass Captioning                                         │
│                                                                  │
│   5-PASS: Yüz → Vücut → Kıyafet → Sahne → Captioning            │
│                                                                  │
│   OUTPUT: [5 JSON] → [Merge] → [Final JSON] → [TXT]             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Local Test

### Neden Local Test?

- Prompt'ları ücretsiz test et
- JSON output formatını doğrula
- Hataları erken yakala
- RunPod maliyetinden tasarruf

### Gereksinimler

| Bileşen | Gereksinim |
|---------|------------|
| VRAM | 12GB (7B model için) |
| RAM | 16GB+ |
| Model | Qwen2.5-VL-7B |
| Backend | Ollama |

### Kurulum

```bash
# 1. Ollama kur (kurulu değilse)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Model indir (~5GB)
ollama pull qwen2.5-vl:7b

# 3. Test
ollama run qwen2.5-vl:7b "Merhaba"
```

### Test Çalıştır

```bash
cd /opt/media-pipeline/dataset-prep/06-caption

# Tek pass test
python client/batch_client.py ./test_images \
    --backend ollama \
    --model qwen2.5-vl:7b \
    --server http://localhost:11434 \
    --character "TestCharacter" \
    --pass 1

# Tüm pass'ları test (otomatik merge yapar)
python client/batch_client.py ./test_images \
    --backend ollama \
    --model qwen2.5-vl:7b \
    --character "TestCharacter" \
    --pass all
```

### Kontrol Listesi

- [ ] Pass 1 JSON çıktısı valid mi?
- [ ] Pass 2 JSON çıktısı valid mi?
- [ ] Pass 3 JSON çıktısı valid mi?
- [ ] Pass 4 JSON çıktısı valid mi?
- [ ] Merge işlemi düzgün çalışıyor mu?
- [ ] Tüm alanlar dolduruluyor mu?

---

## Phase 2: RunPod Production

### Model Bilgileri

**Qwen3-VL-30B-A3B-Instruct-abliterated**

| Özellik | Değer |
|---------|-------|
| Toplam Parametre | 30B |
| Aktif Parametre | 3B (MoE) |
| Tip | Vision-Language Model |
| Ollama Model | `huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct` |

### VRAM Gereksinimleri (Ollama)

| Quantization | VRAM | GPU Önerisi |
|--------------|------|-------------|
| Q4_K_M | ~20-25GB | RTX 4090 24GB |
| **Q8_0** | ~35-40GB | **A40 48GB** (Önerilen) |
| FP16 | ~70-80GB | A100 80GB |

**Seçilen:** Ollama Q8_0 + Tek A40 48GB

### Neden Ollama?

| Özellik | vLLM | Ollama |
|---------|------|--------|
| Kurulum | Karmaşık | `curl + pull` |
| MoE Desteği | Sorunlu | Stabil |
| Quantization | Manuel | Otomatik |
| Model Yönetimi | HuggingFace | Ollama Registry |

### RunPod Pod Oluştur

```
GPU:      A40 48GB (tek kart yeterli)
Template: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04
Volume:   Network Volume → /workspace
```

### İlk Kurulum (Bir Kere)

```bash
# Dosyaları /workspace'e yükle
cd /workspace/image-captioner/server

# Setup çalıştır (Ollama + Python)
chmod +x setup.sh start_ollama.sh
./setup.sh
```

### Model İndir (Bir Kere)

```bash
# Ollama models dizinini ayarla (persistent)
export OLLAMA_MODELS=/workspace/ollama/models

# Model indir (~20-30GB)
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct
```

---

## Production Kullanım

### Adım 1: Server Başlat (RunPod'da)

```bash
# tmux session aç
tmux new -s ollama

# Ollama server başlat
cd /workspace/image-captioner/server
./start_ollama.sh

# Detach: Ctrl+B, D
# Reattach: tmux attach -t ollama
```

Server hazır olduğunda:
```
Ollama is running
API: http://0.0.0.0:11434
```

### Adım 2: Client'tan Çalıştır (Local Makinede)

Resimler local disk'te, client uzak server'a bağlanır:

```bash
cd /opt/media-pipeline/dataset-prep/06-caption

# RunPod pod IP'sini al (RunPod dashboard'dan)
RUNPOD_IP="xxx.xxx.xxx.xxx"

# Tüm pass'ları çalıştır (otomatik merge yapar)
python client/batch_client.py ./images \
    --backend ollama \
    --server http://${RUNPOD_IP}:11434 \
    --model huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct \
    --character "CharacterName" \
    --workers 4 \
    --pass all

# Sadece merge işlemi (mevcut pass dosyalarını birleştirmek için)
python client/batch_client.py ./images --merge
```

**Not:** `--pass all` kullanıldığında otomatik merge yapılır, ayrıca `--merge` çalıştırmaya gerek yoktur.

### Adım 3: Sonuçlar (Local'de Oluşur)

`--pass all` kullanıldığında:
```
./images/
├── image001.jpg
└── image001.json    ← Tüm pass'ların birleştirilmiş hali
```

Tek pass çalıştırıldığında:
```
./images/
├── image001.jpg
├── image001_pass1_face.json    ← Pass 1 sonucu
├── image001_pass2_body.json    ← Pass 2 sonucu
├── image001_pass3_clothing.json← Pass 3 sonucu
└── image001_pass4_scene.json   ← Pass 4 sonucu
```

### Network Gereksinimleri

| Yön | Boyut | Açıklama |
|-----|-------|----------|
| Upload (client → server) | ~1.3MB/resim/pass | Base64 encoded image |
| Download (server → client) | ~1-2KB/pass | JSON response |
| **Toplam (1000 resim)** | ~5-6GB upload | 4 pass × 1000 resim |

**Not:** Upload hızınız önemli. 20 Mbps upload ile ~30-40 dk upload overhead.

---

## 5-Pass Sistemi (v6)

| Pass | Odak | Çıktı |
|------|------|-------|
| **1** | Saç (uzunluk, stil, doku, ayrım) + Yüz (ifade, bakış, makyaj) | `*_pass1_face.json` |
| **2** | Vücut (tip, poz, duruş, el/kol pozisyonu) | `*_pass2_body.json` |
| **3** | Kıyafet (üst, alt, iç çamaşırı) + Aksesuarlar | `*_pass3_clothing.json` |
| **4** | Sahne (ortam, ışık, arka plan) + Teknik (çekim, kadraj) | `*_pass4_scene.json` |
| **5** | Natural Language Captioning (short/medium/long) | `*_pass5_caption.json` |

### v6 Akış

```
Pass 1 → Pass 2 → Pass 3 → Pass 4
              ↓
      PRE-MERGE (JSON 1-4)
              ↓
    Pass 5 (Image + Merged JSON → Caption)
              ↓
      FINAL MERGE (JSON + Caption)
              ↓
    json_to_txt.py (Caption → TXT)
```

### Neden 5-Pass?

- Her pass kendi alanına odaklanır
- Daha detaylı ve tutarlı sonuç
- Model dikkatini dağıtmaz
- Hata durumunda sadece ilgili pass tekrarlanır
- **Pass 5 JSON-aware:** Structured data'yı görerek tutarlı caption üretir

### Pass 5: Captioning Özellikleri

- **JSON-aware:** Pass 1-4'ten gelen structured data'yı okur
- **Karakter ismi:** `--character Aria` → Caption'larda "Aria" kullanılır
- **3 caption uzunluğu:**
  - `short`: 15-25 kelime, 1 cümle
  - `medium`: 40-60 kelime, 2-3 cümle
  - `long`: 80-120 kelime, 4-5 cümle

### Auto-Merge Özelliği

`--pass all` kullanıldığında tüm pass'lar çalıştırıldıktan sonra otomatik olarak birleştirilir:
- 5 ayrı pass JSON dosyası oluşturulur
- Tümü tek bir `image.json` dosyasına merge edilir
- Pass dosyaları (`*_pass1_face.json`, vb.) silinir

### JSON'dan TXT'ye Çıkarma

```bash
# Caption'ları TXT dosyalarına çıkar
python3 json_to_txt.py /path/to/images --type long --overwrite

# Seçenekler: short, medium, long
python3 json_to_txt.py /path/to/images --type short
python3 json_to_txt.py /path/to/images --type medium
```

---

## Mimari

```
┌──────────────────┐         ┌──────────────────────────────┐
│   LOCAL CLIENT   │         │      RUNPOD SERVER           │
│                  │         │                              │
│  [Resimler]      │  HTTP   │  [vLLM / Ollama]             │
│  Local Disk      │ ──────► │  Qwen3-VL-30B                │
│                  │ base64  │                              │
│  batch_client.py │ ◄────── │  JSON Response               │
│                  │         │                              │
└──────────────────┘         └──────────────────────────────┘
     ▲
     │ Her resim base64 encode edilip
     │ API'ye gönderilir
     │ (paralel workers ile)
```

### Veri Akışı

1. Client local disk'ten resmi okur
2. Base64 encode eder (~%33 boyut artışı)
3. HTTP POST ile server'a gönderir
4. Server model ile işler
5. JSON response döner
6. Client JSON'u kaydeder

---

## Performans & Maliyet

### Tek Resim Süreleri

| Backend | Model | Upload | Inference | Toplam/Pass |
|---------|-------|--------|-----------|-------------|
| Ollama (local) | 7B | 0 | ~3-5 sn | ~3-5 sn |
| Ollama (remote) | 30B | ~0.3-0.5 sn | ~3-5 sn | ~4-6 sn |

### 1000 Resim için Toplam (4 Worker)

| Metrik | Local (7B) | Remote (30B) |
|--------|------------|--------------|
| API Çağrısı | 4000 | 4000 |
| Upload Data | 0 | ~4GB (1MB/resim × 4 pass) |
| Upload Süresi | 0 | ~20-30 dk |
| İşlem Süresi | ~4-6 saat | ~6-8 saat |
| **Toplam Süre** | ~4-6 saat | ~6-8 saat |
| Maliyet | $0 | ~$3-4 |

### Worker Sayısı Etkisi

| Workers | Süre (1000 resim) | Network Load |
|---------|-------------------|--------------|
| 2 | ~12-16 saat | Düşük |
| 4 | ~6-8 saat | Orta |
| 6 | ~4-5 saat | Yüksek |
| 8 | ~3-4 saat | Çok Yüksek |

**Öneri:** 4 worker optimal denge

### Maliyet Detayı (RunPod)

| Kaynak | Birim Fiyat | Süre | Toplam |
|--------|-------------|------|--------|
| A40 48GB | ~$0.39/saat | ~6-8 saat | ~$2.5-3.5 |
| Network egress | Free | - | $0 |

---

## Dosya Yapısı

```
06-caption/
├── WORKFLOW.md               # Bu dosya
├── README.md                 # Genel kullanım
│
├── server/                   # RunPod Server
│   ├── setup.sh              # İlk kurulum (Ollama + Python)
│   ├── start_ollama.sh       # Ollama server başlatma
│   ├── requirements.txt      # Server Python bağımlılıkları
│   └── README.md             # Server docs
│
└── client/                   # Captioning Client
    ├── batch_client.py       # Ana işlem scripti (v6)
    ├── json_to_txt.py        # JSON'dan TXT caption çıkarma
    ├── requirements.txt      # Client Python bağımlılıkları
    ├── v6_detailed_json.txt  # v6 JSON şeması (referans)
    └── prompts/              # 5-Pass prompt dosyaları (v6)
        ├── pass1_face_hair.txt   # Saç + Yüz ifadesi
        ├── pass2_body_pose.txt   # Vücut + Poz
        ├── pass3_clothing.txt    # Kıyafet + Aksesuarlar
        ├── pass4_scene.txt       # Sahne + Teknik
        └── pass5_captioning.txt  # Natural Language Captioning
```

---

## Troubleshooting

### Ollama: Model bulunamadı
```bash
ollama list                    # Mevcut modelleri gör
ollama pull qwen2.5-vl:7b      # Model indir (local test)
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct  # Production
```

### Ollama: Out of Memory
```bash
# Daha düşük quantization dene
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct-q4
# veya OLLAMA_NUM_PARALLEL=1 (tek istek)
```

### JSON parse hatası
- Model bazen markdown code block ekliyor
- `batch_client.py` bunu temizliyor
- Hala sorun varsa prompt'u kontrol et

### Yavaş inference
```bash
# Worker sayısını artır (dikkatli)
python batch_client.py /path --workers 4

# Veya max_tokens düşür
python batch_client.py /path --max-tokens 512
```

---

## Sonraki Adımlar

- [x] Local test ortamını kur
- [x] Prompt'ları test et (v5 - single-person dataset optimized)
- [x] JSON output'ları doğrula
- [x] v6: Pass 5 Natural Language Captioning ekle
- [x] v6: json_to_txt.py aracı ekle
- [x] v6: Karakter ismi desteği (caption'larda)
- [ ] RunPod'da production batch çalıştır (opsiyonel)
