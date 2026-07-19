"""
Envio de notificaciones push por Firebase Cloud Messaging (FCM).

Necesita las credenciales de una cuenta de servicio de Firebase en la variable
de entorno FIREBASE_CREDENTIALS (el JSON completo como texto). Si no esta
definida, las funciones no fallan: simplemente no envian.
"""
import json
import os

_initialized = False
_available = None  # None = sin comprobar, True/False = disponible o no


def _ensure_init() -> bool:
    global _initialized, _available
    if _available is not None:
        return _available

    creds_json = os.getenv("FIREBASE_CREDENTIALS", "").strip()
    if not creds_json:
        print("FIREBASE_CREDENTIALS no definida: notificaciones desactivadas.")
        _available = False
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not _initialized:
            cred = credentials.Certificate(json.loads(creds_json))
            firebase_admin.initialize_app(cred)
            _initialized = True
        _available = True
    except Exception as e:  # noqa: BLE001
        print("No se pudo inicializar Firebase Admin:", e)
        _available = False
    return _available


def send_to_tokens(tokens, title: str, body: str, data: dict | None = None) -> dict:
    """Envia una notificacion a una lista de tokens FCM. Devuelve estadisticas
    y la lista de tokens invalidos (para poder limpiarlos)."""
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        return {"sent": 0, "failed": 0, "invalid": [], "reason": "sin tokens"}
    if not _ensure_init():
        return {"sent": 0, "failed": 0, "invalid": [], "reason": "sin credenciales FCM"}

    from firebase_admin import messaging

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        tokens=tokens,
    )

    try:
        resp = messaging.send_each_for_multicast(message)
    except AttributeError:
        # Versiones antiguas de firebase-admin
        resp = messaging.send_multicast(message)

    invalid = []
    for i, r in enumerate(resp.responses):
        if not r.success:
            err = str(getattr(r, "exception", ""))
            if "not-registered" in err.lower() or "invalid-argument" in err.lower():
                invalid.append(tokens[i])

    return {"sent": resp.success_count, "failed": resp.failure_count, "invalid": invalid}
