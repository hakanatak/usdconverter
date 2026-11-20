# USD Converter

Upload GIS data (GeoJSON, ArcGIS REST, GeoServer/WFS), set parameters, **preview the result in 3D in the browser**, and — if you like it — **pay to receive the files** (OpenUSD + GLB). Standalone: no dependency on any particular organisation's data, CRS or servers.

*(TR)* CBS verinizi (dosya, ArcGIS REST, GeoServer/WFS) yükleyin, parametreleri seçin, tarayıcıda 3B önizleyin; beğenirseniz ödeme yapıp OpenUSD + GLB dosyalarını indirin.

## Flow

1. Add layers (upload / URL / ArcGIS / WFS / built-in demo) and set parameters: target CRS (default **auto UTM**), optional source-CRS override per layer, optional manual reference point (anchor X/Y in the target CRS; requires an explicit EPSG target), tile size, line width, extrusion height or height field, Z offset, colour.
2. **Convert & preview** → free, *sampled* GLB preview with watermark, plus a price quote (features-based).
3. **Pay** (Stripe Checkout) → the full package unlocks: `scene.usda` + payloaded tiles (`tiles/*.usda`), `scene.glb`, `report.json`.

The full package is never served before payment (`402` on `/api/jobs/{id}/download`).

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
uvicorn usdconv.app:app_factory --factory --port 8000
# open http://localhost:8000
pytest -q
```
Docker: `docker compose up --build`.

## Protected services (login)

ArcGIS Server/Portal layers: username + password (a token is requested from the server's own token service) **or** a ready token. GeoServer/WFS and GeoJSON URLs: username + password (HTTP Basic) or a Bearer token. Credentials are used only for that job, held in memory, **never stored in the database, returned by the API, or written to logs/exports**, and never forwarded on redirects. Use a read-only service account. Servers on private/corporate networks are blocked by the SSRF guard (see roadmap: on-prem connector agent).

## Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `STRIPE_SECRET_KEY` | – | Enables real payments. Unset = **dev mock mode** (a "pay" button that does not charge; endpoint disabled once a key is set) |
| `STRIPE_WEBHOOK_SECRET` | – | Verifies `POST /api/stripe/webhook` (`checkout.session.completed`) |
| `USDC_BASE_URL` | `http://localhost:8000` | Used for Stripe success/cancel URLs |
| `USDC_DATA_DIR` | `data` | SQLite + job files |
| `USDC_MIN_PRICE_CENTS` / `USDC_PRICE_PER_1K_CENTS` | 900 / 100 | Pricing: min + per 1000 features |
| `USDC_MAX_UPLOAD_MB`, `USDC_MAX_FEATURES`, `USDC_PREVIEW_MAX_FEATURES`, `USDC_RETENTION_HOURS`, `USDC_WORKERS` | 50, 200000, 1500, 72, 2 | Limits |

Stripe setup: create a webhook endpoint `https://<host>/api/stripe/webhook` for `checkout.session.completed`.

## Design notes

- **Engine** (`usdconv/engine.py`): lines → ribbons, points → boxes, polygons → constrained-Delaunay triangulation (GEOS, no GPL/restricted triangulator) with optional extrusion; features bucketed into tiles; anchor = bbox centre snapped to the tile grid; output is local metres, Z-up.
- **CRS**: source detected (GeoJSON `crs`, override, or sanity-checked lon/lat — projected numbers without a declared CRS are *rejected*, never silently mis-placed); target auto-UTM or any projected `EPSG:xxxx`.
- **Security**: every outbound fetch goes through `usdconv/ssrf.py` (scheme/port allow-list, private/metadata ranges blocked, DNS pinning, redirect re-validation, size/time limits). Job ids are 128-bit random capabilities.
- **Viewer**: three.js, vendored under `usdconv/static/vendor` (MIT) — no CDN needed.

## Limits / roadmap

MVP: single process, SQLite, local disk, GeoJSON uploads. Next: GPKG/Shapefile/FGB uploads, DEM terrain (GeoTIFF) & vertical datum, S3 storage + queue workers, Postgres, accounts/orgs, tile fan-out for very large layers, 3D Tiles preview, on-prem connector agent.
