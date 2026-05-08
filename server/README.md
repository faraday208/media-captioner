# RunPod Server Setup (Ollama)

Bu klasör RunPod Dedicated Pod üzerinde çalıştırılacak dosyaları içerir.

## Gereksinimler

- RunPod Dedicated Pod (GPU)
- Network Volume (model cache için)
- PyTorch + CUDA base image

## Hızlı Başlangıç

### 1. Pod Başlat

RunPod'dan GPU Pod başlat:
- **GPU:** A40 48GB (önerilen) veya A100 80GB
- **Template:** `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
- **Network Volume:** Mount et (`/workspace`)
- **TCP Ports:** `11434` (Ollama API için - ÖNEMLİ!)

#### Port Açma (Zorunlu)

Pod oluştururken veya sonrasında:
1. RunPod Dashboard → Pod → "Connect" veya "Edit Pod"
2. "Expose TCP Ports" bölümünde `11434` ekle
3. Save/Deploy

Pod IP'ni al: Dashboard'da "Connect" → "TCP Port Mappings" → `11434` karşısındaki IP:PORT

### 2. Setup Script Çalıştır

```bash
cd /workspace/image-captioner/server
chmod +x setup.sh start_ollama.sh
./setup.sh
```

### 3. Model İndir (İlk Seferde)

```bash
# Ollama models dizinini persistent yap
export OLLAMA_MODELS=/workspace/ollama/models

# Model indir (~20-30GB)
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct
```

### 4. Server Başlat

```bash
# tmux ile (session kalıcı olsun)
tmux new -s ollama
./start_ollama.sh

# Detach: Ctrl+B, D
# Reattach: tmux attach -t ollama
```

## API Kullanımı

Server başladıktan sonra Ollama API:

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
    "messages": [
      {
        "role": "user",
        "content": "Describe this image",
        "images": ["<base64_encoded_image>"]
      }
    ],
    "stream": false
  }'
```

## Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `setup.sh` | İlk kurulum (Ollama + Python) |
| `start_ollama.sh` | Ollama server başlatma |
| `requirements.txt` | Python bağımlılıkları |

## VRAM Kullanımı

| Model | Quantization | VRAM |
|-------|--------------|------|
| Qwen3-VL-30B-A3B | Q4_K_M | ~20-25GB |
| Qwen3-VL-30B-A3B | Q8_0 | ~35-40GB |
| Qwen3-VL-30B-A3B | FP16 | ~70-80GB |

## Troubleshooting

### Model yüklenmiyor
```bash
# Model listesi
ollama list

# Yeniden indir
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct
```

### Out of Memory
```bash
# Daha düşük quantization
ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct-q4

# Paralel istek sayısını sınırla
export OLLAMA_NUM_PARALLEL=1
```

### Port çakışması
```bash
# Farklı port kullan
OLLAMA_HOST=0.0.0.0:11435 ollama serve
```
