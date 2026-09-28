# GEOSHIELD PowerShell Launcher
# Right-click -> "Run with PowerShell" OR run in terminal: .\run.ps1

$env:PYTHONUTF8 = "1"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  =============================================================" -ForegroundColor Cyan
Write-Host "    GEOSHIELD - AI Satellite Disaster Management System" -ForegroundColor Cyan
Write-Host "  =============================================================" -ForegroundColor Cyan
Write-Host ""

$port = 8501
while ($port -lt 8510) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try {
        $listener.Start()
        break
    }
    catch {
        $port++
    }
    finally {
        $listener.Stop()
    }
}

Write-Host "  [*] Starting dashboard at http://localhost:$port" -ForegroundColor Green
Write-Host "  [*] Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

streamlit run app/streamlit_app.py --server.port $port --server.headless false
