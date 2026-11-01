$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot 'venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python. Create the environment first: py -3.12 -m venv venv"
}

$backendArgs = @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000')
$modelArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001')
$frontendArgs = @('run', 'dev', '--', '--host', '0.0.0.0', '--port', '5173')

Start-Process -FilePath $python -ArgumentList $backendArgs -WorkingDirectory $repoRoot -WindowStyle Minimized
Start-Process -FilePath $python -ArgumentList $modelArgs -WorkingDirectory $repoRoot -WindowStyle Minimized
Start-Process -FilePath 'npm' -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $repoRoot 'frontend') -WindowStyle Minimized

Write-Host 'Started local services:'
Write-Host '  - Backend API: http://127.0.0.1:8000'
Write-Host '  - Model API: http://127.0.0.1:8001'
Write-Host '  - Frontend: http://127.0.0.1:5173'
