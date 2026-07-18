"""
Verificacion de tokens de Firebase Authentication.

La app inicia sesion con Firebase (email/contrasena o Google) y obtiene un
"ID token" (JWT). La app lo envia en la cabecera Authorization: Bearer <token>.
Aqui se verifica ese token contra las claves publicas de Firebase, sin necesidad
de un service account: solo hace falta el ID del proyecto (FIREBASE_PROJECT_ID).
"""
import os
import time
from typing import Optional

import jwt
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from fastapi import Header, HTTPException, status

_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

_certs: dict = {}
_certs_expira: float = 0.0


def _get_certs() -> dict:
    """Descarga (y cachea) los certificados publicos de Firebase."""
    global _certs, _certs_expira
    if _certs and time.time() < _certs_expira:
        return _certs

    r = requests.get(_CERTS_URL, timeout=10)
    r.raise_for_status()
    _certs = r.json()

    # Respetar el max-age de la cabecera Cache-Control
    max_age = 3600
    for part in r.headers.get("Cache-Control", "").split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                max_age = int(part.split("=", 1)[1])
            except ValueError:
                pass
    _certs_expira = time.time() + max_age
    return _certs


def verify_firebase_token(id_token: str, project_id: str) -> dict:
    """Verifica el ID token de Firebase y devuelve sus claims (sub=uid, email...)."""
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("El token no tiene 'kid'")

    cert_pem = _get_certs().get(kid)
    if not cert_pem:
        raise ValueError("Clave (kid) no encontrada en los certificados de Firebase")

    public_key = x509.load_pem_x509_certificate(
        cert_pem.encode(), default_backend()
    ).public_key()

    return jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=project_id,
        issuer=f"https://securetoken.google.com/{project_id}",
    )


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Dependencia FastAPI: exige un token de Firebase valido y devuelve el usuario."""
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    if not project_id:
        raise HTTPException(status_code=500, detail="FIREBASE_PROJECT_ID no configurado en el servidor")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta el token de autenticacion")

    token = authorization[7:].strip()
    try:
        payload = verify_firebase_token(token, project_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalido: {e}")

    uid = payload.get("sub") or payload.get("user_id")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin identificador de usuario")

    return {
        "uid": uid,
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }
