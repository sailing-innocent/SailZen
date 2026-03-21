# Auto-update mobile API IP address for Expo Go
param()

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Expo Go Network Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Get all IPv4 addresses
$allIPs = ipconfig | findstr "IPv4" | ForEach-Object {
    if ($_ -match '(\d+\.\d+\.\d+\.\d+)') {
        $matches[1]
    }
}

# Find the best LAN IP (192.168.x.x is usually WiFi)
$lanIP = $allIPs | Where-Object { $_ -like '192.168.*' } | Select-Object -First 1

# Fallback to other private IPs
if (-not $lanIP) {
    $lanIP = $allIPs | Where-Object { 
        ($_ -like '10.*') -or 
        ($_ -match '^172\.(1[6-9]|2[0-9]|3[01])\.')
    } | Select-Object -First 1
}

# Final fallback
if (-not $lanIP) {
    $lanIP = "localhost"
    Write-Host "[WARN] Could not detect LAN IP!" -ForegroundColor Red
    Write-Host "Please check your WiFi connection." -ForegroundColor Yellow
    exit 1
}

Write-Host "Detected WiFi IP: $lanIP" -ForegroundColor Green
Write-Host ""

# Update .env.development
$envFile = "$PSScriptRoot\..\.env.development"
if (Test-Path $envFile) {
    $content = Get-Content $envFile -Raw
    $newContent = $content -replace 'http://[^/]+:4399', "http://$lanIP`:4399"
    
    if ($content -ne $newContent) {
        Set-Content -Path $envFile -Value $newContent -NoNewline
        Write-Host "Updated API URL to: http://$lanIP`:4399/api/v1" -ForegroundColor Green
    } else {
        Write-Host "IP address unchanged: http://$lanIP`:4399/api/v1" -ForegroundColor Cyan
    }
} else {
    Write-Host "Error: .env.development not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  IMPORTANT: Backend Server Setup" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "The backend must accept connections from your phone!" -ForegroundColor White
Write-Host ""
Write-Host "Option 1 - Modify .env.dev (Recommended):" -ForegroundColor Cyan
Write-Host "  1. Open: D:\ws\repos\SailZen\.env.dev" -ForegroundColor Gray
Write-Host "  2. Change: SERVER_HOST=0.0.0.0" -ForegroundColor Gray
Write-Host "  3. Restart server: uv run server.py --dev" -ForegroundColor Gray
Write-Host ""
Write-Host "Option 2 - Environment variable:" -ForegroundColor Cyan
Write-Host "  SERVER_HOST=0.0.0.0 uv run server.py --dev" -ForegroundColor Gray
Write-Host ""
Write-Host "Current backend config check:" -ForegroundColor Cyan
$envDevPath = "$PSScriptRoot\..\..\.env.dev"
if (Test-Path $envDevPath) {
    $envContent = Get-Content $envDevPath | findstr "SERVER_HOST"
    if ($envContent -match "localhost") {
        Write-Host "  $envContent" -ForegroundColor Red
        Write-Host "  WARNING: Server is configured for localhost only!" -ForegroundColor Red
        Write-Host "  Please change to SERVER_HOST=0.0.0.0" -ForegroundColor Yellow
    } else {
        Write-Host "  $envContent" -ForegroundColor Green
        Write-Host "  Good! Server should accept LAN connections." -ForegroundColor Green
    }
}
Write-Host ""
Write-Host "Network Test:" -ForegroundColor Cyan
Write-Host "  From your phone, try: ping $lanIP" -ForegroundColor Gray
Write-Host "  If ping fails, check Windows Firewall settings." -ForegroundColor Gray
Write-Host ""
Write-Host "Done! Starting Expo..." -ForegroundColor Green
Write-Host ""
