$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'dist/index.html'))) { npm run build; if ($LASTEXITCODE -ne 0) { throw 'React build failed' } }
New-Item -ItemType Directory -Force -Path (Join-Path $taskRoot 'storage') | Out-Null
$port = & (Join-Path $taskRoot '.ragvenv/Scripts/python.exe') -c "from api.db import connection_options; import os; print(os.getenv('WEB_PORT', '8501'))"
if ($LASTEXITCODE -ne 0) { throw 'Could not read backend configuration' }
if (Get-NetTCPConnection -State Listen -LocalPort ([int]$port) -ErrorAction SilentlyContinue) { throw "Port $port already in use. Stop the previous BIG_RAG process first." }
$web = Start-Process -FilePath (Join-Path $taskRoot '.ragvenv/Scripts/python.exe') -ArgumentList '-m','scripts.serve' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot 'storage/web.out.log') -RedirectStandardError (Join-Path $taskRoot 'storage/web.err.log') -PassThru
@{web=$web.Id} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'storage/processes.json')
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($web.HasExited) { throw 'Python backend failed to start. See storage/web.err.log.' }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        if ($health.backend -eq 'python') { Write-Output "BIG_RAG Python: http://localhost:$port - logs: storage/logs/api.log, storage/logs/api-error.log (npm run logs:errors)"; return }
    } catch { Start-Sleep -Milliseconds 500 }
}
throw 'Python backend did not become ready. See storage/web.err.log.'
