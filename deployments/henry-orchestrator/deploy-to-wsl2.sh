#!/bin/bash
# ============================================
#  deploy-to-wsl2.sh — Deploy Henry to OpenClaw
# ============================================
#
#  WHAT THIS DOES:
#    1. Finds your OpenClaw installation
#    2. Copies Henry's system prompt, config, memory, and protocols
#    3. Tests the gateway connection
#
#  HOW TO RUN:
#    chmod +x deploy-to-wsl2.sh
#    ./deploy-to-wsl2.sh
#
#  OR with a specific OpenClaw path:
#    ./deploy-to-wsl2.sh /path/to/openclaw
#
# ============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
NC='\033[0m'

status()  { echo -e "${CYAN}[*]${NC} $1"; }
success() { echo -e "${GREEN}[+]${NC} $1"; }
fail()    { echo -e "${RED}[!]${NC} $1"; }
info()    { echo -e "${GRAY}    $1${NC}"; }

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Henry Orchestrator — Deploy to OpenClaw${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# -------------------------------------------
# Step 1: Find the script directory (where Henry files are)
# -------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/HENRY.solmd" ]; then
    fail "Cannot find HENRY.solmd in $SCRIPT_DIR"
    info "Make sure this script is in the same directory as HENRY.solmd"
    exit 1
fi

success "Found Henry files at: $SCRIPT_DIR"

# -------------------------------------------
# Step 2: Find OpenClaw installation
# -------------------------------------------
OPENCLAW_DIR=""

# Check if path was provided as argument
if [ -n "$1" ]; then
    OPENCLAW_DIR="$1"
    status "Using provided path: $OPENCLAW_DIR"
else
    status "Searching for OpenClaw installation..."

    # Check common locations
    SEARCH_PATHS=(
        "$HOME/.openclaw"
        "$HOME/.config/openclaw"
        "$HOME/.local/share/openclaw"
        "$HOME/openclaw"
        "/opt/openclaw"
        "$HOME/.config/open-claw"
        "$HOME/.open-claw"
    )

    for path in "${SEARCH_PATHS[@]}"; do
        if [ -d "$path" ]; then
            OPENCLAW_DIR="$path"
            success "Found OpenClaw at: $path"
            break
        fi
    done

    # If not found in common locations, search home (but validate matches)
    if [ -z "$OPENCLAW_DIR" ]; then
        info "Not found in common locations. Searching home directory..."
        # Find candidates but validate they look like OpenClaw config dirs
        for CANDIDATE in $(find "$HOME" -maxdepth 4 -type d \( -iname "*openclaw*" -o -iname "*open-claw*" \) 2>/dev/null); do
            # Validate: must contain config files OR be empty (fresh install)
            # Skip directories that are clearly not config dirs (e.g., git repos, source code)
            if [ -f "$CANDIDATE/config.yaml" ] || [ -f "$CANDIDATE/config.json" ] || \
               [ -f "$CANDIDATE/system.solmd" ] || [ -f "$CANDIDATE/HENRY.solmd" ] || \
               [ -z "$(ls -A "$CANDIDATE" 2>/dev/null)" ]; then
                OPENCLAW_DIR="$CANDIDATE"
                success "Found OpenClaw config at: $CANDIDATE"
                break
            fi
        done

        # If still not found, don't silently pick a random match
        if [ -z "$OPENCLAW_DIR" ]; then
            info "Found directories with 'openclaw' in name, but none appear to be config directories."
        fi
    fi

    # If still not found, check for running process (look for executable path, not flags)
    if [ -z "$OPENCLAW_DIR" ]; then
        info "Checking running processes..."
        # Get the executable path from /proc if available, avoiding command-line args
        # Use proper ERE alternation (| not \|) for pgrep
        for pid in $(pgrep -i "openclaw|open-claw" 2>/dev/null); do
            if [ -f "/proc/$pid/exe" ]; then
                PROC_EXE=$(readlink -f "/proc/$pid/exe" 2>/dev/null)
                if [ -n "$PROC_EXE" ] && [ -f "$PROC_EXE" ]; then
                    OPENCLAW_DIR="$(dirname "$PROC_EXE")"
                    success "Found OpenClaw process running from: $OPENCLAW_DIR"
                    break
                fi
            fi
        done
    fi

    # Last resort: create default location
    if [ -z "$OPENCLAW_DIR" ]; then
        echo ""
        fail "Could not auto-detect OpenClaw installation."
        echo ""
        info "Options:"
        info "  1. Run with path:  ./deploy-to-wsl2.sh /path/to/openclaw"
        info "  2. Create default: ./deploy-to-wsl2.sh ~/.openclaw"
        echo ""
        read -p "    Enter OpenClaw path (or press Enter for ~/.openclaw): " USER_PATH
        OPENCLAW_DIR="${USER_PATH:-$HOME/.openclaw}"
    fi
fi

# Create directory if it doesn't exist
if [ ! -d "$OPENCLAW_DIR" ]; then
    status "Creating directory: $OPENCLAW_DIR"
    mkdir -p "$OPENCLAW_DIR"
fi

echo ""

# -------------------------------------------
# Step 3: Deploy Henry files
# -------------------------------------------
status "Deploying Henry to $OPENCLAW_DIR..."
echo ""

# Copy main system prompt
info "Copying HENRY.solmd (main system prompt)..."
cp "$SCRIPT_DIR/HENRY.solmd" "$OPENCLAW_DIR/HENRY.solmd"
# Also copy as system.solmd (common default name)
cp "$SCRIPT_DIR/HENRY.solmd" "$OPENCLAW_DIR/system.solmd"
success "System prompt installed"

# Copy config
info "Copying config.yaml..."
cp "$SCRIPT_DIR/config.yaml" "$OPENCLAW_DIR/config.yaml"
success "Configuration installed"

# Copy memory template
info "Setting up memory directory..."
mkdir -p "$OPENCLAW_DIR/memory"
if [ ! -f "$OPENCLAW_DIR/memory/henry_memory.json" ]; then
    cp "$SCRIPT_DIR/memory/henry_memory.json" "$OPENCLAW_DIR/memory/henry_memory.json"
    success "Memory template installed"
else
    info "Memory file already exists — keeping existing data"
    success "Memory preserved"
fi

# Copy protocols
info "Copying protocols..."
mkdir -p "$OPENCLAW_DIR/protocols"
cp "$SCRIPT_DIR/protocols/"*.md "$OPENCLAW_DIR/protocols/"
success "Protocols installed ($(ls "$SCRIPT_DIR/protocols/"*.md | wc -l) files)"

echo ""

# -------------------------------------------
# Step 4: Test gateway connection
# -------------------------------------------
GATEWAY_URL="http://localhost:18789"

status "Testing OpenClaw gateway at $GATEWAY_URL..."

if command -v curl &>/dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/agents" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        success "Gateway is running! (HTTP $HTTP_CODE)"
    elif [ "$HTTP_CODE" = "000" ]; then
        info "Gateway not reachable at $GATEWAY_URL"
        info "This is OK if the gateway runs on Windows side"
        info "WSL2 can usually access Windows localhost"
    else
        info "Gateway responded with HTTP $HTTP_CODE"
    fi
else
    info "curl not installed — skipping gateway test"
    info "Install with: sudo apt install curl"
fi

echo ""

# -------------------------------------------
# Step 5: Show results
# -------------------------------------------
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Deployment Complete!${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
success "Henry is installed at: $OPENCLAW_DIR"
echo ""
info "Files deployed:"
info "  $OPENCLAW_DIR/HENRY.solmd         — System prompt"
info "  $OPENCLAW_DIR/system.solmd        — System prompt (alt name)"
info "  $OPENCLAW_DIR/config.yaml         — Configuration"
info "  $OPENCLAW_DIR/memory/             — Persistent memory"
info "  $OPENCLAW_DIR/protocols/          — Operating protocols"
echo ""
info "How to use Henry:"
info "  Web UI:  http://localhost:18789/agents"
info "  CLI:     openclaw --system-prompt $OPENCLAW_DIR/HENRY.solmd"
echo ""
info "Quick test — say to Henry:"
info '  "Henry, introduce yourself."'
info '  "Henry, what needs my attention today?"'
info '  "Henry, run a Monte Carlo on [any decision]."'
echo ""
