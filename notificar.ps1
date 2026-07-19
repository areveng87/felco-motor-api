# Envia una notificacion de prueba a TODOS los dispositivos registrados.
#
# Uso (elige uno):
#   powershell -ExecutionPolicy Bypass -File notificar.ps1
#   powershell -ExecutionPolicy Bypass -File notificar.ps1 -Destino coche  -CarId "ID_DEL_COCHE"
#   powershell -ExecutionPolicy Bypass -File notificar.ps1 -Destino seccion -Route "favorites"
#
# Ajusta SYNC_TOKEN con el valor que tienes en Render (variable de entorno SYNC_TOKEN).

param(
    [ValidateSet("app", "coche", "seccion")]
    [string]$Destino = "app",
    [string]$CarId = "",
    [string]$Route = "favorites",   # catalog | favorites | contact | profile
    [string]$Titulo = "FercoMotors",
    [string]$Mensaje = "Tienes una novedad en FercoMotors"
)

$BaseUrl   = "https://felco-motor-api.onrender.com"
$SyncToken = "PON_AQUI_TU_SYNC_TOKEN"

$payload = @{ title = $Titulo; body = $Mensaje }
switch ($Destino) {
    "coche"   { $payload.car_id = $CarId }
    "seccion" { $payload.route  = $Route }
    default   { $payload.data   = @{ type = "app" } }
}
$body = $payload | ConvertTo-Json -Depth 5

try {
    $resp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/notify" `
        -Headers @{ "X-Sync-Token" = $SyncToken; "Content-Type" = "application/json" } `
        -Body $body
    Write-Host "Respuesta del backend:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Host "Error:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}
