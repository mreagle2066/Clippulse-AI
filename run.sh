#!/bin/bash

# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Ensure output and uploads directories exist
mkdir -p uploads output/cache

echo "🚀 Starting ClipPulse AI Web Dashboard..."
echo "🌐 Open your browser at: http://localhost:8000"
echo ""

python3 app.py
