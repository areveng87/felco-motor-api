# FercoMotors API (Python / FastAPI)

Backend REST en **FastAPI + SQLite** con los mismos endpoints y contrato JSON que consume la app .NET MAUI. No hay que cambiar nada en la app.

## Requisitos

- Python 3.10+
- Instalar dependencias:
  ```
  pip install -r requirements.txt
  ```

> Si ya tenías una `ferco.db` de una versión anterior, **bórrala** antes de arrancar: se añadieron columnas nuevas (`vin`, `status`, `updated_at`) y SQLite no las agrega a una tabla ya creada.
> ```
> del ferco.db
> ```

## Arrancar

```
cd C:\D\FercoMotors\ferco-api-python
uvicorn main:app --host 0.0.0.0 --port 5080
```

Al arrancar por primera vez crea `ferco.db` (SQLite) y **carga los 205 coches reales** desde `inventory.json`. Docs interactivas: http://localhost:5080/docs

> Se usa el puerto **5080** para que coincida con la app (`ApiConfig.Target = AndroidUsbReverse` → `http://localhost:5080/`).

## Conectar el móvil (igual que antes)

Por USB con `adb reverse` (lo más fiable):
```
adb reverse tcp:5080 tcp:5080
```
Luego abre la app: los datos entran por el túnel USB. En el navegador del móvil `http://localhost:5080/v1/cars` debe dar el JSON.

## Endpoints

| Método | Ruta | Descripción |
|-------|------|-------------|
| GET | `/v1/cars` | Lista. Filtros: `q`, `fuel`, `body`, `maxPrice`, `minYear`, `maxMileage`, `sort` (`priceAsc`/`priceDesc`/`make`) |
| GET | `/v1/cars/{id}` | Coche por id |
| POST | `/v1/cars` | Crear |
| PUT | `/v1/cars/{id}` | Actualizar |
| DELETE | `/v1/cars/{id}` | Eliminar |
| POST | `/v1/contact` | Registrar solicitud de contacto |
| POST | `/v1/sync` | Sincroniza el inventario con fercomotors.com (params opcionales `maxPages`, `maxCars`) |

## Sincronización automática con la web

El backend puede mantenerse al día solo con fercomotors.com. La sincronización, por **VIN**:

- Coche nuevo (VIN no visto) → se **crea**.
- Coche existente (mismo VIN) → se **actualiza** (precio, km, etc.).
- Coche que ya no aparece en la web → se marca como **`sold`** (no se borra).

Formas de lanzarla:

1. **Manual por HTTP** (útil para probar; empieza con pocos para no esperar):
   ```
   curl -X POST "http://localhost:5080/v1/sync?maxPages=1"
   curl -X POST "http://localhost:5080/v1/sync"          # inventario completo (1-2 min)
   ```
   Devuelve p.ej. `{"created":3,"updated":200,"sold":2,"seen":205,"scraped":205}`.

2. **Programada** (automática): se ejecuta cada `SYNC_INTERVAL_HOURS` horas (por defecto **12**). Para cambiarla o desactivarla, define la variable de entorno antes de arrancar:
   ```
   set SYNC_INTERVAL_HOURS=6     &  :: cada 6 horas   (0 = desactivar)
   uvicorn main:app --host 0.0.0.0 --port 5080
   ```

3. **Como script / cron** (sin la API):
   ```
   python sync.py         # inventario completo
   python sync.py 1       # solo la primera página (prueba rápida)
   ```

Opcional: protege el endpoint definiendo `SYNC_TOKEN=loquesea`; entonces hay que enviar la cabecera `X-Sync-Token: loquesea` en el `POST /v1/sync`.

> Nota: sincronizar entra en ~205 fichas de la web con una pequeña espera entre peticiones, así que tarda un par de minutos. No la lances en bucle.

## Recargar el inventario

El seed solo se ejecuta si la tabla está vacía. Para recargar desde `inventory.json`, borra la BD y arranca de nuevo:
```
del ferco.db
uvicorn main:app --host 0.0.0.0 --port 5080
```

## Desplegar

FastAPI es fácil de publicar. Opciones:

- **Servidor propio / VPS**: `uvicorn main:app --host 0.0.0.0 --port 8000` (o detrás de nginx). Para producción real: `gunicorn -k uvicorn.workers.UvicornWorker main:app`.
- **PaaS** (Render, Railway, Fly.io, Azure App Service): comando de inicio `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **Base de datos**: SQLite vale para empezar, pero en plataformas con disco efímero se borra en cada despliegue. Para producción usa Postgres definiendo la variable de entorno:
  ```
  DATABASE_URL=postgresql+psycopg://usuario:clave@host:5432/ferco
  ```
  (instala también `psycopg[binary]`). El código toma esa URL automáticamente.

Cuando lo tengas en un dominio público con HTTPS, en la app pon
`ApiConfig.Target = ApiTarget.Production` y ajusta la URL en `BaseUrl` (rama Production).

## Estructura

```
ferco-api-python/
├─ main.py           Rutas FastAPI + seed
├─ models.py         Tablas (Car, ContactMessage)
├─ schemas.py        Contrato Pydantic (JSON de la app)
├─ database.py       Conexión (SQLite por defecto; DATABASE_URL para otras)
├─ inventory.json    205 coches reales de Ferco
└─ requirements.txt
```
