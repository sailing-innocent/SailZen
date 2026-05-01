# Shadow Agent one-click startup script (PowerShell)
# Usage: .\scripts\start-shadow-agent.ps1 [-Fg]

param([switch]$Fg)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot\..

Write-Host "[Agent] Checking prerequisites..."

# 1. Check Sail Server
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:1974/health" -TimeoutSec 2
    Write-Host "[Agent] Sail Server is running"
} catch {
    Write-Host "[Agent] Sail Server not running. Starting in background..."
    $proc = Start-Process -FilePath "uv" -ArgumentList "run","server.py","--dev" -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:1974/health" -TimeoutSec 2
        Write-Host "[Agent] Sail Server started (PID $($proc.Id))"
    } catch {
        Write-Error "[Agent] Failed to start Sail Server"
        Pop-Location
        exit 1
    }
}

# 2. Check agent.yaml
if (!(Test-Path "agent.yaml")) {
    Write-Host "[Agent] Creating default agent.yaml..."
    @"
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
"@ | Set-Content -Path "agent.yaml" -Encoding UTF8
}

# 3. Start Agent
if ($Fg) {
    Write-Host "[Agent] Starting in foreground..."
    uv run cli/agent.py start --fg -c agent.yaml
} else {
    Write-Host "[Agent] Starting daemon..."
    uv run cli/agent.py start -c agent.yaml
    Start-Sleep -Seconds 1
    uv run cli/agent.py status
}

Pop-Location
