"""
Envio de emails. En Render Free el SMTP saliente esta BLOQUEADO, asi que se usa
una API por HTTPS (no bloqueada). Se elige el transporte segun las variables de
entorno disponibles (en este orden):

  1) SendGrid  -> SENDGRID_API_KEY   (+ MAIL_FROM = remitente verificado)
  2) Resend    -> RESEND_API_KEY     (+ MAIL_FROM)
  3) SMTP      -> SMTP_HOST/PORT/USER/PASS  (solo funciona en Render de pago)

Si no hay ninguno configurado o falla, devuelve False (no rompe).
"""
import os

import requests


def _mail_from() -> str:
    return os.getenv("MAIL_FROM", "").strip() or os.getenv("SMTP_FROM", "").strip() or "FercoMotors <onboarding@resend.dev>"


def _from_email() -> str:
    """Extrae solo la direccion de MAIL_FROM (admite 'Nombre <correo>')."""
    raw = _mail_from()
    if "<" in raw and ">" in raw:
        return raw[raw.index("<") + 1:raw.index(">")].strip()
    return raw.strip()


def _from_name() -> str:
    raw = _mail_from()
    if "<" in raw:
        return raw[:raw.index("<")].strip() or "FercoMotors"
    return "FercoMotors"


def send_email(to: str, subject: str, html: str) -> bool:
    if not to:
        return False
    if _send_brevo(to, subject, html):
        return True
    if _send_sendgrid(to, subject, html):
        return True
    if _send_resend(to, subject, html):
        return True
    if _send_smtp(to, subject, html):
        return True
    print("Email no enviado: sin transporte (BREVO_API_KEY / SENDGRID_API_KEY / RESEND_API_KEY / SMTP_*).")
    return False


def _send_brevo(to: str, subject: str, html: str) -> bool:
    key = os.getenv("BREVO_API_KEY", "").strip()
    if not key:
        return False
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": key, "Content-Type": "application/json", "accept": "application/json"},
            json={
                "sender": {"email": _from_email(), "name": _from_name()},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201, 202):
            return True
        print("Brevo error", resp.status_code, resp.text[:200])
    except Exception as e:  # noqa: BLE001
        print("Brevo excepcion:", e)
    return False


def _send_sendgrid(to: str, subject: str, html: str) -> bool:
    key = os.getenv("SENDGRID_API_KEY", "").strip()
    if not key:
        return False
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": _from_email(), "name": _from_name()},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=30,
        )
        if resp.status_code in (200, 202):
            return True
        print("SendGrid error", resp.status_code, resp.text[:200])
    except Exception as e:  # noqa: BLE001
        print("SendGrid excepcion:", e)
    return False


def _send_resend(to: str, subject: str, html: str) -> bool:
    key = os.getenv("RESEND_API_KEY", "").strip()
    if not key:
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"from": _mail_from(), "to": [to], "subject": subject, "html": html},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True
        print("Resend error", resp.status_code, resp.text[:200])
    except Exception as e:  # noqa: BLE001
        print("Resend excepcion:", e)
    return False


def _send_smtp(to: str, subject: str, html: str) -> bool:
    import smtplib
    from email.mime.text import MIMEText

    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return False
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    sender = _mail_from()
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                if user and pwd:
                    s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                if user and pwd:
                    s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        return True
    except Exception as e:  # noqa: BLE001
        print("SMTP excepcion:", e)
    return False


def build_alert_html(alert_name: str, cars) -> str:
    rows = []
    for c in cars:
        price = f"${int(c.price):,}" if c.price else ""
        img = (c.images or [None])[0] if c.images else None
        img_tag = f'<img src="{img}" width="180" style="border-radius:8px;display:block;margin-bottom:6px">' if img else ""
        url = c.source_url if getattr(c, "source_url", None) else "https://fercomotors.com"
        rows.append(
            f'<div style="margin:0 0 18px 0;font-family:Arial,sans-serif">'
            f'{img_tag}'
            f'<div style="font-size:16px;font-weight:bold">{c.make} {c.model} {c.year}</div>'
            f'<div style="color:#555">{c.version or ""}</div>'
            f'<div style="color:#0B1F3A;font-weight:bold;font-size:16px">{price}</div>'
            f'<a href="{url}" style="color:#E63946">Ver coche</a>'
            f'</div>'
        )
    body = "".join(rows)
    return (
        f'<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto">'
        f'<h2 style="color:#0B1F3A">FercoMotors · {alert_name}</h2>'
        f'<p>Hemos encontrado coches que coinciden con tu alerta:</p>'
        f'{body}'
        f'<hr><p style="color:#888;font-size:12px">Recibes este email porque creaste una alerta en la app de FercoMotors.</p>'
        f'</div>'
    )
