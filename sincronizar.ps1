# Lanza la sincronizacion COMPLETA del inventario contra fercomotors.com.
# Recupera details, features y descripciones reales (upsert por VIN).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File sincronizar.ps1
#   powershell -ExecutionPolicy Bypass -File sincronizar.ps1 -MaxPages 1   # prueba rapida
#
# Ajusta SYNC_TOKEN con el valor de la variable de entorno SYNC_TOKEN en Render.

param(
    [int]$MaxPages = 0   # 0 = todo el inventario
)

$BaseUrl   = "https://felco-motor-api.onrender.com"
$SyncToken = "786ecc5d2e410696e143ab537100e9c1"

$uri = "$BaseUrl/v1/sync"
if ($MaxPages -gt 0) { $uri += "?maxPages=$MaxPages" }

Write-Host "Sincronizando... (puede tardar 1-2 min con el inventario completo)" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Method Post -Uri $uri `
        -Headers @{ "X-Sync-Token" = $SyncToken } -TimeoutSec 600
    Write-Host "Resultado:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Host "Error:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}
