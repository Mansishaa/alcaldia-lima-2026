$ErrorActionPreference = 'Stop'
$dist = Join-Path $PSScriptRoot 'sitio_alcaldes_lima\dist'
$url = 'http://127.0.0.1:8765/'

try {
    Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null
} catch {
    $python = (Get-Command python -ErrorAction Stop).Source
    Start-Process -FilePath $python -ArgumentList '-m', 'http.server', '8765', '--bind', '127.0.0.1' -WorkingDirectory $dist -WindowStyle Hidden
    Start-Sleep -Milliseconds 900
}

Start-Process $url
