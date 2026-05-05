#!/bin/bash
# Shadow Agent one-click startup script
# Usage: ./scripts/start-shadow-agent.sh [--fg]

set -e

cd "$(dirname "$0")/.."

echo "[Agent] Checking prerequisites..."

# 1. Check Sail Server
if ! curl -s http://localhost:1974/health > /dev/null 2>&1; then
    echo "[Agent] Sail Server not running. Starting in background..."
    uv run server.py --dev &
    SS_PID=$!
    sleep 3
    if ! curl -s http://localhost:1974/health > /dev/null 2>&1; then
        echo "[Agent] Failed to start Sail Server"
        exit 1
    fi
    echo "[Agent] Sail Server started (PID $SS_PID)"
else
    echo "[Agent] Sail Server is running"
fi

# 2. Check agent.yaml
if [ ! -f "agent.yaml" ]; then
    echo "[Agent] Creating default agent.yaml..."
    cat > agent.yaml << 'EOF'
agent:
  name: "dev-shadow-agent"
  data_dir: "./data/agent"
  log_level: INFO

  admin_api:
    host: "127.0.0.1"
    port: 1975

  vaults:
    - name: "notes"
      url: "./vaults/notes"
      local_path: "./vaults/notes"
      branch: "main"
      sync_interval_minutes: 30

  analysis:
    enabled: true
    scan_interval_minutes: 60
    orphan_detection: true
    daily_gap_detection: true
    todo_extraction: true
    broken_link_detection: true

  patch:
    enabled: true
    cron: "0 23 * * *"
    output_dir: "./patches"
    auto_generate_topic: true
EOF
fi

# 3. Start Agent
if [ "$1" == "--fg" ]; then
    echo "[Agent] Starting in foreground..."
    exec uv run cli/agent.py start --fg -c agent.yaml
else
    echo "[Agent] Starting daemon..."
    uv run cli/agent.py start -c agent.yaml
    sleep 1
    uv run cli/agent.py status
fi
