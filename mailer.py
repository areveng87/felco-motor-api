"""
Envio de emails por SMTP. Configuracion por variables de entorno:
  SMTP_HOST, SMTP_PORT (def 587), SMTP_USER, SMTP_PASS, SMTP_FROM (def = SMTP_USER)
Si no esta configurado o falla, no rompe: devuelve False.
"""
import os
import smtplib
from email.mime.text import MIMEText


def _cfg():
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    sender = os.getenv("SMTP_FROM", "").strip() or user
    return host, port, user, pwd, sender


def send_email(to: str, subject: str, html: str) -> bool:
    host, port, user, pwd, sender = _cfg()
    if not host or not to:
        print("SMTP no configurado o sin destinatario; email no enviado.")
        return False
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            if user and pwd:
                s.login(user, pwd)
            s.sendmail(sender, [to], msg.as_string())
        return True
    except Exception as e:  # noqa: BLE001
        print("Error enviando email:", e)
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
