#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f "bin/cloudflared" ]; then
    echo "Downloading cloudflared..."
    curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz" | tar -xz -C bin/
    chmod +x bin/cloudflared
fi

echo "=========================================================="
echo "🌐 Launching Public Live HTTPS Tunnel..."
echo "=========================================================="
./bin/cloudflared tunnel --url http://127.0.0.1:8000
