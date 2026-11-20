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

## Flow (3-step wizard)

1. **Data** — drag & drop GeoJSON files onto the big drop zone (or click it), add layers from a saved service, or try the demo. Each file is read immediately: geometry type, feature count, CRS and fields are detected. If a file has projected coordinates but no declared CRS, the wizard asks for it instead of guessing.
2. **Settings** — pre-filled from the data (colour from the layer name, building height from a `height`/`kat`/`floors` field, road width, tile size from the data extent, auto UTM). Each layer shows only one or two simple controls; everything else is under *Advanced*.
3. **Preview** — watermarked 3D preview, price, pay, download.

Shapefile/GPKG/KML are not supported yet — convert to GeoJSON first (e.g. `ogr2ogr -f GeoJSON out.geojson in.shp`).

## Sources (services) and catalog

**Sources** page → *Add service*: ArcGIS Server (services directory, a `FeatureServer`/`MapServer`, or a single layer URL), GeoServer/WFS (`GetCapabilities`) or a GeoJSON URL. Only the URL is saved. Open the **Catalog** to search layers, press **Info** (geometry type, record count, fields) and **+ Add** to put a layer into the conversion. Services that need a login ask for username/password/token when you connect; these are kept in the browser tab's memory only and sent per request — the server never stores them. Unreadable ArcGIS folders are skipped instead of breaking the catalog.

## Accounts and admin

Users sign up / sign in with e-mail + password (scrypt hashes, server-side sessions in an HttpOnly cookie, CSRF header, 5-failure lockout for 15 min). Every job belongs to its owner; other users get `404`. E-mails listed in `USDC_ADMIN_EMAILS` (comma-separated) become admins and get an **Admin** page (`/admin.html`): active sessions (user, IP, browser, last seen), all users, all jobs. Admins can open any job.

## Protected services (login)

ArcGIS Server/Portal layers: username + password (a token is requested from the server's own token service) **or** a ready token. GeoServer/WFS and GeoJSON URLs: username + password (HTTP Basic) or a Bearer token. Credentials are used only for that job, held in memory, **never stored in the database, returned by the API, or written to logs/exports**, and never forwarded on redirects. Use a read-only service account. Servers on private/corporate networks are blocked by the SSRF guard (see roadmap: on-prem connector agent).

## Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `STRIPE_SECRET_KEY` | – | Enables real payments. Unset = **dev mock mode** (a "pay" button that does not charge; endpoint disabled once a key is set) |
| `STRIPE_WEBHOOK_SECRET` | – | Verifies `POST /api/stripe/webhook` (`checkout.session.completed`) |
| `USDC_ADMIN_EMAILS` | – | Comma-separated admin e-mails (they must sign up with that address) |
| `USDC_SESSION_DAYS` | 14 | Login session lifetime |
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

MVP: single process, SQLite, local disk, GeoJSON uploads. Next: GPKG/Shapefile/FGB uploads, DEM terrain (GeoTIFF) & vertical datum, S3 storage + queue workers, Postgres, organisations/teams, password reset & e-mail verification, tile fan-out for very large layers, 3D Tiles preview, on-prem connector agent.
