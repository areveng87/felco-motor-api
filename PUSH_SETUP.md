# Notificaciones push (FCM)

Arquitectura: la app obtiene un **token FCM** y lo registra en el backend (`POST /v1/devices`, autenticado). El backend envía notificaciones a esos tokens con **Firebase Admin**. Solo se registran dispositivos de **usuarios con sesión iniciada**.

## 1. Backend: credenciales de envío (service account)

Para que el servidor pueda enviar, necesita una **cuenta de servicio** de tu proyecto Firebase:

1. Firebase Console → ⚙ **Configuración del proyecto → Cuentas de servicio** → **Generar nueva clave privada** → descarga un JSON.
2. En **Render → tu servicio → Environment** añade la variable:
   - Key: `FIREBASE_CREDENTIALS`
   - Value: **todo el contenido del JSON** (pégalo tal cual, en una sola variable).
3. `firebase-admin` ya está en `requirements.txt`. Redeploya.

Sin esta variable, la API **no falla**: simplemente no envía (los endpoints responden pero con `sent: 0`).

## 2. App: ya configurada

- Paquete `Plugin.Firebase.CloudMessaging` añadido al `.csproj`, con `google-services.json` enlazado (`GoogleServicesJson`).
- Permiso `POST_NOTIFICATIONS` (Android 13+) en el manifiesto.
- Al **iniciar sesión**, la app pide permiso, obtiene el token y lo registra en `/v1/devices`. Al **cerrar sesión**, lo da de baja.

> Si al compilar el token no se obtiene (algunas configuraciones lo requieren), añade en el arranque de Android `CrossFirebase.Initialize(activity)` (en `MainActivity`/lifecycle `OnCreate`). En muchos casos Firebase se auto-inicializa desde `google-services.json` y no hace falta.

## 3. Enviar notificaciones

**Manual (a todos):** `POST /v1/notify` con la cabecera `X-Sync-Token` (el mismo SYNC_TOKEN):
```
curl -X POST https://felco-motor-api.onrender.com/v1/notify \
  -H "Content-Type: application/json" \
  -H "X-Sync-Token: TU_TOKEN" \
  -d '{"title":"Ofertas FercoMotors","body":"Nuevos coches esta semana","data":{"type":"promo"}}'
```

**Automática (coches nuevos):** al ejecutar `POST /v1/sync`, si aparecen coches nuevos, se envía solo un aviso "Nuevos coches en FercoMotors". Lo mismo con la sincronización programada.

## Endpoints nuevos

| Método | Ruta | Descripción |
|-------|------|-------------|
| POST | `/v1/devices` | Registra el token FCM del usuario (auth) |
| DELETE | `/v1/devices/{token}` | Da de baja el token (auth) |
| POST | `/v1/notify` | Envía una notificación a todos (X-Sync-Token) |

## Prueba de extremo a extremo

1. Redeploy backend con `FIREBASE_CREDENTIALS` puesta.
2. Compila e instala la app, **inicia sesión** (esto registra el token).
3. Envía un `POST /v1/notify` → debe llegar la notificación al móvil.
