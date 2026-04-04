#!/bin/bash

# Henry Orchestrator Installer
# Automatically detects OpenClaw and installs Henry

set -e

echo "========================================"
echo "  Henry Orchestrator Installer v1.0"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to find OpenClaw directory
find_openclaw() {
    # Check common locations
    local locations=(
        "$HOME/.config/openclaw"
        "$HOME/.openclaw"
        "$HOME/Library/Application Support/openclaw"
        "$APPDATA/openclaw"
        "/etc/openclaw"
    )

    for loc in "${locations[@]}"; do
        if [ -d "$loc" ]; then
            echo "$loc"
            return 0
        fi
    done

    # Try to find it
    local found=$(find "$HOME" -type d -name "*openclaw*" 2>/dev/null | head -1)
    if [ -n "$found" ]; then
        echo "$found"
        return 0
    fi

    return 1
}

# Check for target directory argument
if [ -n "$1" ]; then
    TARGET_DIR="$1"
    echo "[*] Using provided directory: $TARGET_DIR"
else
    echo "[*] Searching for OpenClaw installation..."
    if TARGET_DIR=$(find_openclaw); then
        echo "[*] Found OpenClaw at: $TARGET_DIR"
    else
        echo ""
        echo "[!] Could not find OpenClaw installation."
        echo ""
        echo "Please provide the path manually:"
        echo "  ./install.sh /path/to/openclaw"
        echo ""
        echo "Or create a new directory:"
        echo "  mkdir -p ~/.openclaw && ./install.sh ~/.openclaw"
        exit 1
    fi
fi

echo ""
echo "[*] Installing Henry to: $TARGET_DIR"
echo ""

# Create directories
echo "[1/4] Creating directories..."
mkdir -p "$TARGET_DIR/memory"
mkdir -p "$TARGET_DIR/protocols"

# Copy main system prompt
echo "[2/4] Installing HENRY.solmd..."
cp "$SCRIPT_DIR/HENRY.solmd" "$TARGET_DIR/"

# Also copy as system.solmd in case that's the expected name
cp "$SCRIPT_DIR/HENRY.solmd" "$TARGET_DIR/system.solmd" 2>/dev/null || true

# Copy config
echo "[3/4] Installing configuration..."
cp "$SCRIPT_DIR/config.yaml" "$TARGET_DIR/"

# Copy memory template (preserve existing memory on re-install)
if [ -f "$TARGET_DIR/memory/henry_memory.json" ]; then
    echo "    Existing memory found — preserving (backup created)"
    cp "$TARGET_DIR/memory/henry_memory.json" "$TARGET_DIR/memory/henry_memory.json.backup.$(date +%Y%m%d_%H%M%S)"
else
    cp "$SCRIPT_DIR/memory/henry_memory.json" "$TARGET_DIR/memory/"
fi

# Copy protocols
echo "[4/4] Installing protocols..."
cp "$SCRIPT_DIR/protocols/"*.md "$TARGET_DIR/protocols/"

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Files installed to: $TARGET_DIR"
echo ""
echo "Contents:"
ls -la "$TARGET_DIR/"
echo ""
echo "Next steps:"
echo ""
echo "1. If OpenClaw uses a config file, point it to:"
echo "   system_prompt: \"$TARGET_DIR/HENRY.solmd\""
echo ""
echo "2. Or set environment variable:"
echo "   export OPENCLAW_SYSTEM_PROMPT=\"$TARGET_DIR/HENRY.solmd\""
echo ""
echo "3. Start OpenClaw and test:"
echo "   > Henry, what needs my attention today?"
echo ""
echo "See DEPLOY.md for full documentation."
