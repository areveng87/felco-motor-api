"""
FercoMotors API (FastAPI + SQLite)

Mismos endpoints y contrato que consume la app .NET MAUI:
  GET    /v1/cars            (filtros: q, fuel, maxPrice, minYear, maxMileage, body, sort)
  GET    /v1/cars/{id}
  POST   /v1/cars
  PUT    /v1/cars/{id}
  DELETE /v1/cars/{id}
  POST   /v1/contact

Arrancar:
  uvicorn main:app --host 0.0.0.0 --port 5080
Docs interactivas:  http://localhost:5080/docs
"""
import json
import os
import threading
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import mailer
import models
import notifications
import schemas
import sync as sync_module
import translate
from auth import get_current_user
from database import Base, SessionLocal, engine

# Configuracion de sincronizacion (via variables de entorno)
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "")               # si se define, protege POST /v1/sync
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", "12"))  # 0 = desactivado


def _ensure_columns():
    """Auto-migracion ligera: añade columnas nuevas a 'cars' si faltan (SQLite/Postgres)."""
    insp = inspect(engine)
    if "cars" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("cars")}
    # (nombre, tipo SQL, valor por defecto para rellenar los NULL)
    faltan = []
    if "details" not in existing:
        faltan.append(("details", "JSON", "'{}'"))
    if "features" not in existing:
        faltan.append(("features", "JSON", "'[]'"))
    if "monthly_payment" not in existing:
        faltan.append(("monthly_payment", "FLOAT", "0"))
    if "description_es" not in existing:
        faltan.append(("description_es", "TEXT", "''"))
    if "features_es" not in existing:
        faltan.append(("features_es", "JSON", "'[]'"))
    if not faltan:
        return
    with engine.begin() as conn:
        for name, sql_type, default in faltan:
            conn.execute(text(f"ALTER TABLE cars ADD COLUMN {name} {sql_type}"))
            conn.execute(text(f"UPDATE cars SET {name} = {default} WHERE {name} IS NULL"))


Base.metadata.create_all(bind=engine)
_ensure_columns()

app = FastAPI(title="FercoMotors API", version="1.0")

# CORS abierto para desarrollo (restringe en produccion)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CAR_FIELDS = [
    "vin", "make", "model", "version", "year", "price", "monthly_payment", "mileage", "fuel",
    "transmission", "power", "doors", "color", "body", "location",
    "description", "description_es", "images", "details", "features", "features_es",
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def seed_inventory():
    """Si la tabla esta vacia, carga inventory.json (inventario real)."""
    db = SessionLocal()
    try:
        if db.query(models.Car).count() > 0:
            return
        path = os.path.join(os.path.dirname(__file__), "inventory.json")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for raw in data:
            low = {k.lower(): v for k, v in raw.items()}
            car = models.Car(**{f: low.get(f) for f in CAR_FIELDS if low.get(f) is not None})
            db.add(car)
        db.commit()
        print(f"Sembrados {len(data)} coches desde inventory.json")
    finally:
        db.close()


@app.get("/")
def root():
    """Raiz: util como comprobacion rapida y para keep-alive."""
    return {"service": "FercoMotors API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    """Endpoint ligero para pings de keep-alive / monitorizacion."""
    return {"status": "ok"}


@app.get("/v1/cars", response_model=List[schemas.CarOut])
def list_cars(
    q: Optional[str] = None,
    fuel: Optional[str] = None,
    maxPrice: Optional[float] = None,
    minYear: Optional[int] = None,
    maxMileage: Optional[int] = None,
    body: Optional[str] = None,
    sort: Optional[str] = Query(None, description="priceAsc | priceDesc | make"),
    db: Session = Depends(get_db),
):
    # Solo inventario activo (nunca coches ya retirados/vendidos).
    query = db.query(models.Car).filter(models.Car.status != "sold")

    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Car.make.ilike(like)
            | models.Car.model.ilike(like)
            | models.Car.version.ilike(like)
        )
    if fuel:
        query = query.filter(models.Car.fuel == fuel)
    if body:
        query = query.filter(models.Car.body == body)
    if maxPrice is not None:
        query = query.filter(models.Car.price <= maxPrice)
    if minYear is not None:
        query = query.filter(models.Car.year >= minYear)
    if maxMileage is not None:
        query = query.filter(models.Car.mileage <= maxMileage)

    if sort == "priceAsc":
        query = query.order_by(models.Car.price.asc())
    elif sort == "priceDesc":
        query = query.order_by(models.Car.price.desc())
    elif sort == "make":
        query = query.order_by(models.Car.make.asc(), models.Car.model.asc())
    else:
        query = query.order_by(models.Car.created_at.desc())

    return query.all()


@app.get("/v1/cars/{car_id}", response_model=schemas.CarOut)
def get_car(car_id: str, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    return car


@app.post("/v1/cars/{car_id}/translate", response_model=schemas.CarOut)
def translate_car(car_id: str, db: Session = Depends(get_db)):
    """Traduce (EN->ES) la descripcion y el equipamiento de un coche BAJO DEMANDA
    y lo guarda. Idempotente: si ya esta traducido, no vuelve a gastar credito."""
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")

    if not (car.description_es or "").strip():
        car.description_es = translate.translate_text(car.description or "")
        feats = car.features or []
        car.features_es = translate.translate_texts(feats) if feats else []
        db.commit()
        db.refresh(car)
    return car


@app.post("/v1/cars", response_model=schemas.CarOut, status_code=status.HTTP_201_CREATED)
def create_car(payload: schemas.CarIn, db: Session = Depends(get_db)):
    car = models.Car(**payload.model_dump())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


@app.put("/v1/cars/{car_id}", response_model=schemas.CarOut)
def update_car(car_id: str, payload: schemas.CarIn, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    for field, value in payload.model_dump().items():
        setattr(car, field, value)
    db.commit()
    db.refresh(car)
    return car


@app.delete("/v1/cars/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_car(car_id: str, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    db.delete(car)
    db.commit()


@app.get("/v1/me")
def me(user=Depends(get_current_user)):
    """Devuelve el usuario autenticado (a partir del token de Firebase)."""
    return {"uid": user["uid"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture")}


@app.get("/v1/favorites", response_model=List[schemas.CarOut])
def list_favorites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Coches marcados como favoritos por el usuario autenticado."""
    ids = [f.car_id for f in db.query(models.Favorite).filter(models.Favorite.user_uid == user["uid"]).all()]
    if not ids:
        return []
    return db.query(models.Car).filter(models.Car.id.in_(ids)).all()


@app.post("/v1/favorites/{car_id}", status_code=status.HTTP_201_CREATED)
def add_favorite(car_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Marca un coche como favorito para el usuario."""
    if db.get(models.Car, car_id) is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    exists = db.query(models.Favorite).filter_by(user_uid=user["uid"], car_id=car_id).first()
    if exists is None:
        db.add(models.Favorite(user_uid=user["uid"], car_id=car_id))
        db.commit()
    return {"status": "ok", "carId": car_id}


@app.delete("/v1/favorites/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(car_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Quita un coche de favoritos del usuario."""
    fav = db.query(models.Favorite).filter_by(user_uid=user["uid"], car_id=car_id).first()
    if fav is not None:
        db.delete(fav)
        db.commit()


# ---------- Alertas (busquedas guardadas + propuestas por email) ----------

def _alert_matches(db: Session, crit: dict):
    """Query de coches disponibles que cumplen los criterios de una alerta."""
    q = db.query(models.Car).filter(models.Car.status != "sold")
    s = crit or {}
    if s.get("q"):
        like = f"%{s['q']}%"
        q = q.filter(models.Car.make.ilike(like) | models.Car.model.ilike(like) | models.Car.version.ilike(like))
    if s.get("make"):
        q = q.filter(models.Car.make == s["make"])
    if s.get("model"):
        q = q.filter(models.Car.model == s["model"])
    if s.get("year"):
        try:
            q = q.filter(models.Car.year == int(s["year"]))
        except ValueError:
            pass
    if s.get("body"):
        if s["body"] == "Hybrid":
            q = q.filter(models.Car.fuel == "Híbrido")
        else:
            q = q.filter(models.Car.body == s["body"])

    def _num(key):
        try:
            return float(s[key])
        except (KeyError, ValueError, TypeError):
            return None

    mn, mx = _num("minPrice"), _num("maxPrice")
    if mn is not None:
        q = q.filter(models.Car.price >= mn)
    if mx is not None:
        q = q.filter(models.Car.price <= mx)
    return q


def _process_alert(db: Session, alert: "models.Alert", limit: int = 20) -> int:
    """Envia por email los coches que cumplen la alerta y aun no se enviaron."""
    sent = {r.car_id for r in db.query(models.AlertSent).filter_by(alert_id=alert.id).all()}
    matches = [c for c in _alert_matches(db, alert.criteria or {}).all() if c.id not in sent][:limit]
    if not matches:
        return 0
    html = mailer.build_alert_html(alert.name, matches)
    if not mailer.send_email(alert.email, f"FercoMotors · {alert.name}", html):
        return 0
    for c in matches:
        db.add(models.AlertSent(alert_id=alert.id, car_id=c.id))
    db.commit()
    return len(matches)


def process_alerts(db: Session) -> None:
    for a in db.query(models.Alert).all():
        try:
            _process_alert(db, a)
        except Exception as e:  # noqa: BLE001
            print("Error procesando alerta:", e)


def _process_alert_bg(alert_id: str) -> None:
    db = SessionLocal()
    try:
        a = db.get(models.Alert, alert_id)
        if a:
            _process_alert(db, a)
    except Exception as e:  # noqa: BLE001
        print("Error alerta bg:", e)
    finally:
        db.close()


@app.get("/v1/alerts", response_model=List[schemas.AlertOut])
def list_alerts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Alert).filter_by(user_uid=user["uid"]).order_by(models.Alert.created_at.asc()).all()


@app.post("/v1/alerts", response_model=schemas.AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(payload: schemas.AlertIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(models.Alert).filter_by(user_uid=user["uid"]).all()
    names = {a.name for a in existing}

    name = (payload.name or "").strip()
    if not name:
        n = len(existing) + 1
        name = f"Alerta {n}"
        while name in names:
            n += 1
            name = f"Alerta {n}"
    if name in names:
        raise HTTPException(status_code=409, detail="Ya tienes una alerta con ese nombre")

    email = user.get("email") or ""
    criteria = {k: str(v) for k, v in (payload.criteria or {}).items() if v not in (None, "", "0")}
    alert = models.Alert(user_uid=user["uid"], email=email, name=name, criteria=criteria)
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Envio inicial de propuestas en segundo plano (no bloquea la respuesta).
    threading.Thread(target=_process_alert_bg, args=(alert.id,), daemon=True).start()
    return alert


@app.delete("/v1/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(models.Alert).filter_by(id=alert_id, user_uid=user["uid"]).first()
    if a is not None:
        db.query(models.AlertSent).filter_by(alert_id=a.id).delete()
        db.delete(a)
        db.commit()


@app.get("/v1/devices")
def list_devices(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Lista los dispositivos (tokens) registrados por el usuario. Util para verificar."""
    devs = db.query(models.Device).filter_by(user_uid=user["uid"]).all()
    return [{"token": d.token[:24] + "…", "platform": d.platform, "created_at": str(d.created_at)} for d in devs]


@app.post("/v1/devices", status_code=status.HTTP_201_CREATED)
def register_device(payload: schemas.DeviceIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Registra (o actualiza) el token FCM del dispositivo del usuario autenticado."""
    dev = db.query(models.Device).filter_by(token=payload.token).first()
    if dev is None:
        dev = models.Device(user_uid=user["uid"], token=payload.token, platform=payload.platform or "android")
        db.add(dev)
    else:
        dev.user_uid = user["uid"]
        dev.platform = payload.platform or dev.platform
    db.commit()
    return {"status": "ok"}


@app.delete("/v1/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(token: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Quita el token del dispositivo (p. ej. al cerrar sesion)."""
    dev = db.query(models.Device).filter_by(token=token).first()
    if dev is not None:
        db.delete(dev)
        db.commit()


def _notify_all(db: Session, title: str, body: str, data: dict | None = None) -> dict:
    """Envia una notificacion a todos los dispositivos registrados y limpia los invalidos."""
    tokens = [d.token for d in db.query(models.Device).all()]
    result = notifications.send_to_tokens(tokens, title, body, data)
    for bad in result.get("invalid", []):
        d = db.query(models.Device).filter_by(token=bad).first()
        if d:
            db.delete(d)
    if result.get("invalid"):
        db.commit()
    return result


@app.post("/v1/notify")
def notify(payload: schemas.NotifyIn, x_sync_token: Optional[str] = Header(None),
           db: Session = Depends(get_db)):
    """Envia una notificacion manual a todos los dispositivos. Protegido con SYNC_TOKEN."""
    if SYNC_TOKEN and x_sync_token != SYNC_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalido")

    # Construir el 'data' final a partir de los atajos de destino.
    data = dict(payload.data or {})
    if payload.car_id:
        data.setdefault("type", "car")
        data["carId"] = payload.car_id
    elif payload.route:
        data.setdefault("type", "section")
        data["route"] = payload.route

    return _notify_all(db, payload.title, payload.body, data)


@app.post("/v1/test-drive", status_code=status.HTTP_202_ACCEPTED)
def schedule_test_drive(payload: schemas.TestDriveIn, db: Session = Depends(get_db)):
    """Solicitud de test drive: se guarda y se avisa a Ferco por email."""
    msg = models.ContactMessage(
        car_id=payload.car_vin,
        car_title=payload.car_title,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=(f"[TEST DRIVE] Preferencia: {payload.preferred_time or '-'}\n"
                 f"Coche: {payload.car_title or '-'} (VIN {payload.car_vin or '-'})\n"
                 f"Comentarios: {payload.comments or '-'}"),
    )
    db.add(msg)
    db.commit()

    to = os.getenv("TEST_DRIVE_TO", "info@fercomotors.com")
    html = (
        "<h3>Nueva solicitud de test drive (app)</h3>"
        f"<p><b>Nombre:</b> {payload.name}<br>"
        f"<b>Teléfono:</b> {payload.phone or '-'}<br>"
        f"<b>Email:</b> {payload.email}<br>"
        f"<b>Preferencia:</b> {payload.preferred_time or '-'}<br>"
        f"<b>Coche:</b> {payload.car_title or '-'} (VIN {payload.car_vin or '-'})<br>"
        f"<b>Comentarios:</b> {payload.comments or '-'}</p>"
    )
    mailer.send_email(to, "Test drive - FercoMotors app", html)
    return {"id": msg.id}


@app.post("/v1/contact", status_code=status.HTTP_202_ACCEPTED)
def send_contact(payload: schemas.ContactIn, db: Session = Depends(get_db)):
    msg = models.ContactMessage(
        car_id=payload.carId,
        car_title=payload.carTitle,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
    )
    db.add(msg)
    db.commit()
    return {"id": msg.id}


_sync_running = False   # evita solapar sincronizaciones


def _run_sync_job(max_pages, max_cars):
    """Ejecuta la sincronizacion (bloqueante) y avisa si hay coches nuevos."""
    global _sync_running
    try:
        stats = sync_module.run(max_pages=max_pages, max_cars=max_cars)
        print("Sync terminado:", stats)
        db = SessionLocal()
        try:
            if stats.get("created", 0) > 0:
                n = stats["created"]
                _notify_all(
                    db,
                    "Nuevos coches en FercoMotors",
                    f"{n} coche{'s' if n != 1 else ''} nuevo{'s' if n != 1 else ''} disponible{'s' if n != 1 else ''}.",
                    {"type": "new_cars"},
                )
            # Revisar alertas y enviar propuestas por email (coches nuevos que cumplan).
            process_alerts(db)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print("Error en la sincronizacion:", e)
    finally:
        _sync_running = False


@app.post("/v1/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    maxPages: Optional[int] = Query(None, description="Limitar nº de páginas (para probar; p.ej. 1)"),
    maxCars: Optional[int] = Query(None, description="Limitar nº de coches (para probar)"),
    x_sync_token: Optional[str] = Header(None),
):
    """
    Lanza la sincronizacion con la web EN SEGUNDO PLANO y responde al instante
    (asi el proxy de Render no corta la peticion por tardar 1-2 min).
    Devuelve {"status":"started"} o {"status":"already_running"}.
    """
    if SYNC_TOKEN and x_sync_token != SYNC_TOKEN:
        raise HTTPException(status_code=401, detail="Token de sincronizacion invalido")

    global _sync_running
    if _sync_running:
        return {"status": "already_running"}
    _sync_running = True
    threading.Thread(target=_run_sync_job, args=(maxPages, maxCars), daemon=True).start()
    return {"status": "started"}


# ---- Programador: sincroniza cada SYNC_INTERVAL_HOURS horas ----
_scheduler = None


@app.on_event("startup")
def start_scheduler():
    global _scheduler
    if SYNC_INTERVAL_HOURS <= 0:
        print("Sincronizacion automatica desactivada (SYNC_INTERVAL_HOURS=0).")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print("apscheduler no instalado; sincronizacion automatica desactivada.")
        return

    def job():
        try:
            stats = sync_module.run()
            print("Sync automatica:", stats)
            if stats.get("created", 0) > 0:
                db = SessionLocal()
                try:
                    n = stats["created"]
                    _notify_all(db, "Nuevos coches en FercoMotors",
                                f"{n} coche{'s' if n != 1 else ''} nuevo{'s' if n != 1 else ''} disponible{'s' if n != 1 else ''}.",
                                {"type": "new_cars"})
                finally:
                    db.close()
        except Exception as e:  # noqa: BLE001
            print("Error en sync automatica:", e)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(job, "interval", hours=SYNC_INTERVAL_HOURS, id="ferco_sync")
    _scheduler.start()
    print(f"Sincronizacion automatica cada {SYNC_INTERVAL_HOURS} h activada.")


@app.on_event("shutdown")
def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)