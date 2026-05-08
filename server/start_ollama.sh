#!/bin/bash
# ============================================
# Ollama Server Start Script
# ============================================
# Huihui-Qwen3-VL-30B-A3B-Instruct-abliterated
#
# Kullanim:
#   ./start_ollama.sh              # Foreground (tmux icin)
#   ./start_ollama.sh --background # Background
# ============================================

set -e

MODEL="huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
BACKGROUND=false

# Argument parse
if [[ "$1" == "--background" ]] || [[ "$1" == "-b" ]]; then
    BACKGROUND=true
fi

# Ollama models /workspace icine (persistent)
export OLLAMA_MODELS=/workspace/ollama/models
mkdir -p "$OLLAMA_MODELS"

# Uzaktan erisim icin 0.0.0.0'a bind et
export OLLAMA_HOST="0.0.0.0:11434"

# GPU kontrolu
GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l || echo "0")

echo "=========================================="
echo "Ollama Server - Qwen3-VL-30B"
echo "=========================================="
echo "Model:  $MODEL"
echo "GPUs:   $GPU_COUNT"
echo "Host:   $OLLAMA_HOST"
echo "Models: $OLLAMA_MODELS"
echo "=========================================="

# Ollama zaten calisiyor mu?
if pgrep -x "ollama" > /dev/null; then
    echo "Ollama already running"
    echo "Stopping existing instance..."
    pkill -x ollama || true
    sleep 2
fi

# Model var mi kontrol et (serve baslamadan once check edemeyiz)
# Model yoksa ilk istekte indirilecek veya manuel pull gerekecek

echo ""
echo "Starting Ollama server..."
echo "API will be available at: http://0.0.0.0:11434"
echo ""

if [ "$BACKGROUND" = true ]; then
    # Background mode
    ollama serve > /workspace/ollama/server.log 2>&1 &
    OLLAMA_PID=$!
    echo "Ollama started in background (PID: $OLLAMA_PID)"
    echo "Log: /workspace/ollama/server.log"

    # Model pull (background'da)
    sleep 3
    if ! ollama list 2>/dev/null | grep -q "qwen3-vl-abliterated"; then
        echo "Model not found. Pulling..."
        ollama pull "$MODEL"
    fi

    echo ""
    echo "=========================================="
    echo "Ready! Test with:"
    echo "  curl http://localhost:11434/api/tags"
    echo "=========================================="
else
    # Foreground mode (tmux icin)
    echo "Running in foreground. Press Ctrl+C to stop."
    echo ""

    # Model kontrolu icin once background'da baslat
    ollama serve &
    OLLAMA_PID=$!
    sleep 3

    # Model var mi?
    if ! ollama list 2>/dev/null | grep -q "qwen3-vl-abliterated"; then
        echo "Model not found. Pulling (this may take a while)..."
        ollama pull "$MODEL"
    else
        echo "Model ready: $MODEL"
    fi

    # Foreground'a gec
    echo ""
    echo "=========================================="
    echo "Server ready! API: http://0.0.0.0:11434"
    echo "=========================================="
    echo ""

    # PID'i bekle (foreground gibi davran)
    wait $OLLAMA_PID
fi
