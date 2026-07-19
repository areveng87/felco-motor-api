"""
Scraper del inventario de fercomotors.com.

Recorre /search (paginado), entra en cada ficha y extrae los datos del coche
(incluido el VIN) leyendo la tabla de especificaciones. Devuelve una lista de
diccionarios con las mismas claves que el modelo Car.
"""
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

BASE = "https://fercomotors.com"

DETAIL_RE = re.compile(
    r"https://fercomotors\.com/used-[a-z0-9%\-]+/\d{4}-[a-z0-9%\-]+-miami-fl-([a-z0-9]+)",
    re.I,
)
IMG_RE = re.compile(
    r"https://fercomotors\.com/inventory_images/[^\"'\s)]+?large_[^\"'\s)]+?\.jpg", re.I
)
PRICE_RE = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,})(?:\.[0-9]{2})?(\s*/\s*mo)?", re.I)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "FercoMotorsSync/1.0 (+internal inventory import)"})
    return s


def collect_detail_urls(session, max_pages: Optional[int] = None, delay: float = 0.3) -> List[str]:
    urls, seen = [], set()
    page = 1
    while True:
        if max_pages and page > max_pages:
            break
        r = session.get(f"{BASE}/search?page={page}", timeout=30)
        if r.status_code != 200:
            break
        found = {m.group(0) for m in DETAIL_RE.finditer(r.text)}
        new = [u for u in found if u not in seen]
        if not new:
            break
        for u in new:
            seen.add(u)
        urls.extend(new)
        page += 1
        time.sleep(delay)
    return urls


def _map_fuel(f: str) -> str:
    t = (f or "").lower()
    if "hybrid" in t:
        return "Híbrido"
    if "electric" in t:
        return "Eléctrico"
    if "diesel" in t:
        return "Diésel"
    if "gasolin" in t or "gas" in t or "petrol" in t:
        return "Gasolina"
    return f or "Gasolina"


def _map_transmission(t: str) -> str:
    return "Manual" if "manual" in (t or "").lower() else "Automático"


def _map_body(b: str) -> str:
    b = (b or "").lower()
    if any(x in b for x in ("convertible", "roadster", "cabrio", "spyder", "spider")):
        return "Convertible"
    if "coupe" in b:
        return "Coupe"
    if "hatchback" in b:
        return "Hatchback"
    if "sedan" in b:
        return "Sedan"
    if any(x in b for x in ("sport utility", "suv", "crossover", "wagon")):
        return "SUV/Crossover"
    if "van" in b:
        return "Van"
    if any(x in b for x in ("truck", "pickup", "cab")):
        return "Truck"
    return ""


def parse_detail(html: str, url: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Tabla de especificaciones: filas con 2 celdas -> label: valor
    specs = {}
    for tr in soup.select("table tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) != 2:
            continue
        k = cells[0].get_text(strip=True).rstrip(":").strip()
        v = cells[1].get_text(strip=True)
        if k and v and k not in specs:
            specs[k] = v

    make = specs.get("Make", "").strip()
    model = specs.get("Model", "").strip()
    if not make or not model:
        return None

    vin = specs.get("VIN", "").strip().upper()
    if not vin:
        m = DETAIL_RE.search(url)
        vin = m.group(1).upper() if m else ""

    def num(key):
        return int(re.sub(r"[^0-9]", "", specs.get(key, "")) or 0)

    year = num("Year")
    mileage = num("Mileage")

    body_raw = specs.get("Body", "")
    dm = re.match(r"\s*(\d)\s*[dD]", body_raw)
    doors = int(dm.group(1)) if dm else num("Doors")

    # Precio: mayor importe (sobre el texto sin etiquetas) que no sea la cuota "/mo"
    text = soup.get_text(" ")
    price = 0.0
    for pm in PRICE_RE.finditer(text):
        if pm.group(1) and not pm.group(2):
            price = max(price, float(pm.group(1).replace(",", "")))

    images = []
    for im in IMG_RE.finditer(html):
        if im.group(0) not in images:
            images.append(im.group(0))

    trim = specs.get("Trim", "")
    version = " ".join(x for x in [trim, body_raw] if x).strip()
    fuel = _map_fuel(specs.get("Fuel Type", "") or specs.get("Fuel", ""))

    page_text = soup.get_text("\n")

    # Descripcion real: bloque "Vehicle Description" ... hasta "Vehicle Features".
    description = f"{year} {make} {model} {version}. VIN {vin}. Ubicado en Miami, FL.".replace("  ", " ")
    dm2 = re.search(r"Vehicle Description(.*?)Vehicle Features", page_text, re.S | re.I)
    if dm2:
        d = re.sub(r"[ \t]+", " ", dm2.group(1))
        d = re.sub(r"\n\s*\n+", "\n\n", d).strip()
        if len(d) > 20:
            description = d[:4000]

    # Equipamiento: los <li> bajo la seccion "Vehicle Features/Options".
    features = []
    for node in soup.find_all(string=re.compile(r"Vehicle Features", re.I)):
        parent = getattr(node, "parent", None)
        lst = parent.find_next(["ul", "ol"]) if parent else None
        if lst:
            for li in lst.find_all("li"):
                t = li.get_text(" ", strip=True)
                if t and t not in features:
                    features.append(t)
        if features:
            break
    features = features[:150]

    return {
        "vin": vin,
        "make": make,
        "model": model,
        "version": version,
        "year": year,
        "price": price,
        "mileage": mileage,
        "fuel": fuel,
        "transmission": _map_transmission(specs.get("Transmission", "")),
        "power": 0,
        "doors": doors,
        "color": specs.get("Exterior Color", ""),
        "body": _map_body(body_raw),
        "location": "Miami, FL",
        "description": description,
        "images": images,
        "details": dict(specs),      # TODAS las especificaciones de la ficha
        "features": features,
        "source_url": url,
    }


def fetch_inventory(max_pages: Optional[int] = None, max_cars: Optional[int] = None,
                    delay: float = 0.3) -> List[dict]:
    """Devuelve el inventario actual de la web como lista de dicts."""
    s = _session()
    urls = collect_detail_urls(s, max_pages=max_pages, delay=delay)
    if max_cars:
        urls = urls[:max_cars]

    cars = []
    for u in urls:
        try:
            r = s.get(u, timeout=30)
            if r.status_code != 200:
                continue
            car = parse_detail(r.text, u)
            if car and car["vin"]:
                cars.append(car)
        except requests.RequestException:
            pass
        time.sleep(delay)
    return cars
