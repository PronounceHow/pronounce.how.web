#!/usr/bin/env bash
set -euo pipefail

echo "=== pronounceHow dependency setup ==="

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux"
    echo "Installing system packages..."
    sudo apt-get update -qq
    sudo apt-get install -y espeak-ng ffmpeg

    echo "Downloading Rhubarb Lip Sync..."
    RHUBARB_VERSION="1.13.0"
    RHUBARB_URL="https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v${RHUBARB_VERSION}/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-Linux.zip"
    RHUBARB_DIR="$HOME/.local/bin"
    mkdir -p "$RHUBARB_DIR"
    TMP_ZIP=$(mktemp /tmp/rhubarb-XXXXXX.zip)
    curl -sL "$RHUBARB_URL" -o "$TMP_ZIP"
    unzip -o "$TMP_ZIP" -d /tmp/rhubarb-extract
    cp /tmp/rhubarb-extract/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-Linux/rhubarb "$RHUBARB_DIR/"
    chmod +x "$RHUBARB_DIR/rhubarb"
    rm -rf "$TMP_ZIP" /tmp/rhubarb-extract
    echo "Rhubarb installed to $RHUBARB_DIR/rhubarb"

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS"
    echo "Installing system packages..."
    brew install espeak-ng ffmpeg

    echo "Downloading Rhubarb Lip Sync..."
    RHUBARB_VERSION="1.13.0"
    RHUBARB_URL="https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v${RHUBARB_VERSION}/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-macOS.zip"
    RHUBARB_DIR="$HOME/.local/bin"
    mkdir -p "$RHUBARB_DIR"
    TMP_ZIP=$(mktemp /tmp/rhubarb-XXXXXX.zip)
    curl -sL "$RHUBARB_URL" -o "$TMP_ZIP"
    unzip -o "$TMP_ZIP" -d /tmp/rhubarb-extract
    cp /tmp/rhubarb-extract/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-macOS/rhubarb "$RHUBARB_DIR/"
    chmod +x "$RHUBARB_DIR/rhubarb"
    rm -rf "$TMP_ZIP" /tmp/rhubarb-extract
    echo "Rhubarb installed to $RHUBARB_DIR/rhubarb"

else
    echo "Unsupported OS: $OSTYPE"
    echo "Please install espeak-ng, ffmpeg, and Rhubarb manually."
fi

# Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r "$(dirname "$0")/../requirements.txt"

# Node dependencies
echo ""
echo "Installing Node dependencies..."
if command -v npm &> /dev/null; then
    npm install @aspect-build/lipsync-engine
else
    echo "WARNING: npm not found. Skipping Node dependency installation."
    echo "Install Node.js and run: npm install @aspect-build/lipsync-engine"
fi

echo ""
echo "=== Setup complete ==="
echo "Verify with:"
echo "  espeak-ng --version"
echo "  ffmpeg -version | head -1"
echo "  rhubarb --version"
echo "  python -c 'import eng_to_ipa; print(\"eng-to-ipa OK\")'"
