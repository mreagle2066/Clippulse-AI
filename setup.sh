#!/bin/bash
set -e

echo "=========================================================="
echo "🎬 ClipPulse AI - Automated Setup Script (macOS / Linux)"
echo "=========================================================="

# Check if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Check for Xcode Command Line Tools
    if ! xcode-select -p &>/dev/null; then
        echo "⚠️  macOS Command Line Tools not detected."
        echo "👉 Prompting Xcode Command Line Tools installation..."
        xcode-select --install || true
        echo "Please complete the Apple installer prompt and re-run this script."
        exit 1
    fi

    # Check for Homebrew
    if ! command -v brew &>/dev/null; then
        echo "📦 Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    fi

    # Check for FFmpeg
    if ! command -v ffmpeg &>/dev/null; then
        echo "🎥 Installing FFmpeg via Homebrew..."
        brew install ffmpeg
    fi

    # Check for Python 3
    if ! command -v python3 &>/dev/null; then
        echo "🐍 Installing Python via Homebrew..."
        brew install python
    fi
fi

# Create virtual environment
echo "📁 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Create .env if not exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

echo ""
echo "✅ Setup Complete!"
echo "----------------------------------------------------------"
echo "1. Add your Gemini API Key in .env (or in the Web UI):"
echo "   open .env"
echo "2. Launch the Web UI with:"
echo "   ./run.sh"
echo "=========================================================="
