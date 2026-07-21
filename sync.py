"""
Sincronizacion del inventario con fercomotors.com.

- Coches nuevos (VIN que no existe) -> se crean.
- Coches existentes (mismo VIN)      -> se actualizan (precio, km, etc.).
- Coches que ya no aparecen en la web -> se BORRAN (con sus favoritos).

Uso por linea de comandos (one-off / cron):
    python sync.py            # sincroniza todo el inventario
    python sync.py 1          # solo la primera pagina (para probar rapido)
"""
from typing import List, Optional

from sqlalchemy.orm import Session

import models
import scraper
import translate
from database import Base, SessionLocal, engine

# Campos que se actualizan de un coche existente (no tocamos id/created_at)
UPDATABLE = [
    "make", "model", "version", "year", "price", "monthly_payment", "mileage", "fuel",
    "transmission", "power", "doors", "color", "body", "location",
    "description", "description_es", "images", "details", "features", "features_es",
]


def _fill_translation(c: dict, existing=None) -> None:
    """Rellena description_es y features_es (EN->ES) con DeepL.
    Solo traduce si es nuevo o si cambio la descripcion, para ahorrar cuota."""
    changed = (
        existing is None
        or (c.get("description") or "") != (existing.description or "")
        or not getattr(existing, "description_es", None)
    )
    if changed:
        c["description_es"] = translate.translate_text(c.get("description", "") or "")
        feats = c.get("features") or []
        c["features_es"] = translate.translate_texts(feats) if feats else []
    else:
        c["description_es"] = existing.description_es
        c["features_es"] = existing.features_es or []


def sync_inventory(db: Session, cars: List[dict]) -> dict:
    """Aplica el upsert por VIN sobre una lista de coches ya scrapeados."""
    seen = set()
    created = updated = 0

    for c in cars:
        vin = (c.get("vin") or "").strip().upper()
        if not vin:
            continue
        seen.add(vin)

        existing = db.query(models.Car).filter(models.Car.vin == vin).first()
        if existing:
            _fill_translation(c, existing)
            for k in UPDATABLE:
                if k in c:
                    setattr(existing, k, c[k])
            existing.status = "available"
            updated += 1
        else:
            _fill_translation(c, None)
            db.add(models.Car(vin=vin, status="available",
                              **{k: c.get(k) for k in UPDATABLE if c.get(k) is not None}))
            created += 1

    # Limpieza: borrar los coches que ya no aparecen en el inventario web
    # (junto con sus favoritos). Guardado: solo si el scrape trajo inventario,
    # para no vaciar la BD si la web fallo y devolvio 0 coches.
    removed = 0
    if seen:
        for car in db.query(models.Car).all():
            if (car.vin or "").upper() not in seen:
                db.query(models.Favorite).filter(
                    models.Favorite.car_id == car.id
                ).delete(synchronize_session=False)
                db.delete(car)
                removed += 1

    db.commit()
    return {"created": created, "updated": updated, "removed": removed, "seen": len(seen)}


def run(max_pages: Optional[int] = None, max_cars: Optional[int] = None) -> dict:
    """Scrapea la web y sincroniza la BD. Devuelve estadisticas."""
    Base.metadata.create_all(bind=engine)
    cars = scraper.fetch_inventory(max_pages=max_pages, max_cars=max_cars)
    db = SessionLocal()
    try:
        stats = sync_inventory(db, cars)
    finally:
        db.close()
    stats["scraped"] = len(cars)
    return stats


if __name__ == "__main__":
    import sys
    mp = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print("Sincronizando...", "(pagina 1)" if mp == 1 else "(inventario completo)")
    result = run(max_pages=mp)
    print("Resultado:", result)
