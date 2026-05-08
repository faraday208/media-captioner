#!/bin/bash
# ============================================
# RunPod Setup Script (Ollama + Python)
# ============================================
# TÜM KURULUMLAR /workspace içine yapılır.
# Pod silinse bile Network Volume'da kalır.
#
# Ilk kurulumda: ./setup.sh
# Yeni Pod'da: source /workspace/activate.sh
# ============================================

set -e

WORKSPACE="/workspace"
VENV_DIR="$WORKSPACE/venv"
OLLAMA_MODELS_DIR="$WORKSPACE/ollama/models"

echo "=========================================="
echo "RunPod Setup - Ollama + Python"
echo "=========================================="
echo "Workspace: $WORKSPACE"
echo ""

# ============================================
# 1. Sistem Paketleri
# ============================================
echo "Installing system packages..."
apt-get update -qq
apt-get install -y -qq htop nvtop tmux curl wget > /dev/null 2>&1
echo "System packages done"

# ============================================
# 2. Ollama
# ============================================
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "Ollama installed"
else
    echo "Ollama already installed"
fi

# Ollama models dizini
mkdir -p "$OLLAMA_MODELS_DIR"

# ============================================
# 3. Python venv
# ============================================
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv..."
    python3 -m venv "$VENV_DIR"
    echo "venv created"
else
    echo "venv already exists"
fi

source "$VENV_DIR/bin/activate"

# ============================================
# 4. Python Packages
# ============================================
if ! pip show requests > /dev/null 2>&1; then
    echo "Installing Python packages..."
    pip install --upgrade pip -q
    pip install requests tqdm -q
    echo "Python packages installed"
else
    echo "Python packages already installed"
fi

# ============================================
# 5. Activation Script
# ============================================
cat > "$WORKSPACE/activate.sh" << 'EOF'
#!/bin/bash
# Usage: source /workspace/activate.sh

# Python venv
source /workspace/venv/bin/activate

# Ollama models dizini
export OLLAMA_MODELS=/workspace/ollama/models

echo "Environment activated!"
echo "  Python: $(python --version)"
echo "  Ollama models: $OLLAMA_MODELS"
EOF
chmod +x "$WORKSPACE/activate.sh"

# .bashrc'ye ekle
if ! grep -q "workspace/activate.sh" ~/.bashrc 2>/dev/null; then
    echo "source /workspace/activate.sh" >> ~/.bashrc
fi

# ============================================
# 6. Summary
# ============================================
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Persistent locations:"
echo "  Python venv:   $VENV_DIR"
echo "  Ollama models: $OLLAMA_MODELS_DIR"
echo ""
echo "Next steps:"
echo "  1. source /workspace/activate.sh"
echo "  2. ollama serve &"
echo "  3. ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
echo ""
echo "=========================================="
