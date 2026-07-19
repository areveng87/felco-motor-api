# Envia una notificacion de prueba a TODOS los dispositivos registrados.
# Uso:  powershell -ExecutionPolicy Bypass -File notificar.ps1
# Ajusta SYNC_TOKEN con el valor que tienes en Render (variable de entorno SYNC_TOKEN).

$BaseUrl   = "https://felco-motor-api.onrender.com"
$SyncToken = "PON_AQUI_TU_SYNC_TOKEN"

$Titulo  = "FercoMotors"
$Mensaje = "Prueba de notificacion con la app cerrada"

$body = @{
    title = $Titulo
    body  = $Mensaje
    data  = @{ tipo = "test" }
} | ConvertTo-Json

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
