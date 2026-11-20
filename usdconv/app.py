import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import auth, connectors, crs as crsmod, jobs, payments, ssrf, suggest as suggestmod
from .sources import SourceError
from .config import Settings
from .spec import JobSpec
from .store import Store

STATIC = Path(__file__).parent / "static"


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or Settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(cfg.data_dir / "db.sqlite")
    pool = ThreadPoolExecutor(max_workers=cfg.workers)
    app = FastAPI(title="USD Converter", version="0.1.0")
    app.state.cfg, app.state.store, app.state.pool = cfg, store, pool

    def current_user(request: Request) -> dict:
        tok = request.cookies.get(auth.COOKIE)
        u = store.session_user(auth.hash_token(tok)) if tok else None
        if not u:
            raise HTTPException(401, "login required")
        if time.time() - u["_seen"] > 60:
            store.touch_session(auth.hash_token(tok))
        return u

    def admin_user(request: Request) -> dict:
        u = current_user(request)
        if not u["is_admin"]:
            raise HTTPException(403, "admin only")
        return u

    def get_job(job_id: str, request: Request) -> dict:
        """Owner or admin only; anything else is a 404 so job ids cannot be probed."""
        u = current_user(request)
        j = store.get(job_id)
        if not j or (j["user_id"] != u["id"] and not u["is_admin"]):
            raise HTTPException(404, "job not found")
        return j

    @app.middleware("http")
    async def csrf(request: Request, call_next):
        # State-changing calls need a custom header: browsers cannot add it cross-site without a CORS preflight.
        if (request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/")
                and request.url.path != "/api/stripe/webhook" and request.headers.get("x-csrf") != "1"):
            return JSONResponse({"error": "missing X-CSRF header"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def no_cache_static(request: Request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache"   # always revalidate, so UI updates show up after a git pull
        return resp

    def start_session(request: Request, response: Response, user: dict):
        tok, th = auth.new_token()
        exp = time.time() + cfg.session_days * 86400
        store.add_session(th, user["id"], exp, request.client.host if request.client else "", request.headers.get("user-agent", ""))
        store.update_user(user["id"], last_login=time.time(), failed=0, locked_until=0)
        response.set_cookie(auth.COOKIE, tok, max_age=cfg.session_days * 86400, httponly=True,
                            samesite="lax", secure=cfg.secure_cookies, path="/")

    def me(u: dict) -> dict:
        return {"email": u["email"], "is_admin": bool(u["is_admin"])}

    @app.post("/api/auth/signup")
    async def signup(request: Request, response: Response):
        b = await request.json()
        email, pw = str(b.get("email", "")).strip().lower(), str(b.get("password", ""))
        if not auth.EMAIL_RE.match(email):
            raise HTTPException(422, "invalid e-mail")
        try:
            auth.check_new_password(pw)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        if store.user_by_email(email):
            raise HTTPException(409, "account already exists")
        uid = store.add_user(email, auth.hash_password(pw), email in cfg.admins)
        u = store.user_by_email(email)
        start_session(request, response, u)
        return me(u)

    @app.post("/api/auth/login")
    async def login(request: Request, response: Response):
        b = await request.json()
        email, pw = str(b.get("email", "")).strip().lower(), str(b.get("password", ""))
        u = store.user_by_email(email)
        if u and auth.locked(u):
            raise HTTPException(429, "too many failed attempts; try again in 15 minutes")
        ok = auth.verify_password(pw, u["pw_hash"] if u else auth.DUMMY)
        if not u or not ok:
            if u:
                n = u["failed"] + 1
                store.update_user(u["id"], failed=n, locked_until=time.time() + auth.LOCK_S if n >= auth.MAX_FAILS else 0)
            raise HTTPException(401, "wrong e-mail or password")
        if email in cfg.admins and not u["is_admin"]:
            store.update_user(u["id"], is_admin=1)
            u = store.user_by_email(email)
        start_session(request, response, u)
        return me(u)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        tok = request.cookies.get(auth.COOKIE)
        if tok:
            store.delete_session(auth.hash_token(tok))
        response.delete_cookie(auth.COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/auth/me")
    def whoami(request: Request):
        return me(current_user(request))

    @app.get("/api/my/jobs")
    def my_jobs(request: Request):
        return store.list_jobs(current_user(request)["id"])

    @app.post("/api/inspect")
    async def inspect(request: Request, file: UploadFile = File(...), source_crs: str = Form("")):
        """Read an uploaded file and report what was detected + smart defaults (nothing is stored)."""
        current_user(request)
        data = await file.read(cfg.max_upload_mb * 1024 * 1024 + 1)
        if len(data) > cfg.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "upload too large")
        import numpy as np
        import shapely
        from pyproj import Transformer
        from shapely.geometry import shape
        from . import sources
        try:
            fc = sources._parse(data)
        except SourceError as e:
            raise HTTPException(400, str(e)) from e
        feats = fc.get("features", [])
        if not feats:
            raise HTTPException(400, "no features in file")
        if source_crs and not __import__("re").fullmatch(r"EPSG:\d{4,6}", source_crs):
            raise HTTPException(422, "source_crs must look like EPSG:3857")
        try:
            src = crsmod.detect_source_crs(fc, source_crs or None)
        except crsmod.CRSError as e:
            return {"needs_crs": True, "message": str(e), "count": len(feats)}
        kinds, geoms = {}, []
        for f in feats[:5000]:
            try:
                g = shape(f["geometry"]) if f.get("geometry") else None
            except Exception:
                continue
            if g is None or g.is_empty:
                continue
            geoms.append(g)
            k = "point" if "Point" in g.geom_type else "line" if "Line" in g.geom_type else "polygon" if "Polygon" in g.geom_type else None
            if k:
                kinds[k] = kinds.get(k, 0) + 1
        if not geoms:
            raise HTTPException(400, "no usable geometries")
        geometry = max(kinds, key=kinds.get) if kinds else None
        minx, miny, maxx, maxy = shapely.total_bounds(np.array(geoms, dtype=object))
        bb = Transformer.from_crs(src, 4326, always_xy=True).transform_bounds(minx, miny, maxx, maxy)
        stats: dict = {}
        for f in feats[:300]:
            for k, v in (f.get("properties") or {}).items():
                st = stats.setdefault(k, {"n": 0, "num": 0, "ex": None})
                if v is not None:
                    st["n"] += 1
                    st["num"] += isinstance(v, (int, float)) and not isinstance(v, bool)
                    st["ex"] = st["ex"] if st["ex"] is not None else v
        fields = [{"name": k, "numeric": st["n"] > 0 and st["num"] / st["n"] > 0.9, "example": str(st["ex"])[:40]}
                  for k, st in list(stats.items())[:80]]
        stem = file.filename.rsplit(".", 1)[0] if file.filename else ""
        return {"needs_crs": False, "count": len(feats), "geometry": geometry, "mixed": len(kinds) > 1, "fields": fields,
                "crs": src.to_string(), "bbox4326": list(bb), "suggested_tile_m": suggestmod.nice_tile(suggestmod.extent_m(bb)),
                "suggest": suggestmod.suggest(stem, geometry, fields)}

    # ---- saved services (URL only; credentials are asked per use and never stored)
    @app.get("/api/connections")
    def list_connections(request: Request):
        return store.list_conns(current_user(request)["id"])

    @app.post("/api/connections")
    async def add_connection(request: Request):
        u = current_user(request)
        b = await request.json()
        kind, url, name = str(b.get("kind", "")), str(b.get("url", "")).strip(), str(b.get("name", "")).strip()[:80]
        if kind not in ("arcgis", "wfs", "geojson_url") or not name:
            raise HTTPException(422, "name and a valid type are required")
        try:
            ssrf.resolve_safe(url, cfg.allow_private_hosts)
        except ssrf.UnsafeURL as e:
            raise HTTPException(422, str(e)) from e
        cid = secrets.token_urlsafe(9)
        store.add_conn(cid, u["id"], name, kind, url)
        return {"id": cid, "name": name, "kind": kind, "url": url}

    @app.delete("/api/connections/{cid}")
    def del_connection(cid: str, request: Request):
        store.delete_conn(cid, current_user(request)["id"])
        return {"ok": True}

    def conn_and_creds(cid: str, request: Request, body: dict):
        c = store.get_conn(cid, current_user(request)["id"])
        if not c:
            raise HTTPException(404, "connection not found")
        return c, (body.get("username") or None, body.get("password") or None, body.get("token") or None)

    @app.post("/api/connections/{cid}/catalog")
    async def conn_catalog(cid: str, request: Request):
        c, (us, pw, tk) = conn_and_creds(cid, request, await request.json())
        try:
            return {"layers": connectors.catalog(cfg, c["kind"], c["url"], us, pw, tk)}
        except (SourceError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:  # never leave the UI waiting on an unreadable 500
            raise HTTPException(502, f"service error: {type(e).__name__}") from e

    @app.post("/api/connections/{cid}/info")
    async def conn_info(cid: str, request: Request):
        body = await request.json()
        c, (us, pw, tk) = conn_and_creds(cid, request, body)
        try:
            return connectors.layer_info(cfg, c["kind"], c["url"], str(body.get("ref", "")), us, pw, tk)
        except (SourceError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:  # never leave the UI waiting on an unreadable 500
            raise HTTPException(502, f"service error: {type(e).__name__}") from e

    @app.get("/api/admin/overview")
    def admin_overview(request: Request):
        admin_user(request)
        store.purge_sessions()
        return {"users": store.list_users(), "sessions": store.list_sessions(), "jobs": store.list_jobs()}

    def public(j: dict) -> dict:
        return {"id": j["id"], "status": j["status"], "name": j["name"], "error": j["error"],
                "report": json.loads(j["report"]) if j["report"] else None,
                "price_cents": j["price_cents"], "currency": "usd", "paid": bool(j["paid"]),
                "payment_mode": cfg.payment_mode}

    @app.get("/api/config")
    def config():
        return {"payment_mode": cfg.payment_mode, "max_upload_mb": cfg.max_upload_mb,
                "preview_max_features": cfg.preview_max_features}

    @app.post("/api/jobs")
    async def create_job(request: Request, spec: str = Form(...), files: list[UploadFile] = File(default=[])):
        user = current_user(request)
        try:
            js = JobSpec.model_validate_json(spec)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json(include_input=False, include_url=False))) from e
        uploads, total = {}, 0
        for f in files:
            data = await f.read(cfg.max_upload_mb * 1024 * 1024 + 1)
            total += len(data)
            if total > cfg.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, "upload too large")
            uploads[f.filename] = data
        jobs.purge_expired(cfg, store, time.time())
        job_id = secrets.token_urlsafe(16)
        store.create(job_id, js.name, js.model_dump(), user["id"])
        pool.submit(jobs.run_job, cfg, store, job_id, js, uploads)
        return {"id": job_id}

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str, request: Request):
        return public(get_job(job_id, request))

    @app.get("/api/jobs/{job_id}/preview.glb")
    def preview(job_id: str, request: Request):
        j = get_job(job_id, request)
        p = jobs.job_dir(cfg, job_id) / "preview.glb"
        if j["status"] != "ready" or not p.exists():
            raise HTTPException(409, "preview not ready")
        return FileResponse(p, media_type="model/gltf-binary")

    @app.post("/api/jobs/{job_id}/checkout")
    def checkout(job_id: str, request: Request):
        j = get_job(job_id, request)
        if j["status"] != "ready":
            raise HTTPException(409, "job not ready")
        if j["paid"]:
            return {"paid": True}
        if cfg.payment_mode == "stripe":
            s = payments.create_checkout(cfg, job_id, j["name"], j["price_cents"])
            store.update(job_id, stripe_session=s["id"])
            return {"url": s["url"]}
        return {"mock": True}

    @app.post("/api/jobs/{job_id}/mock-pay")
    def mock_pay(job_id: str, request: Request):
        """Development only: disabled as soon as a Stripe key is configured."""
        if cfg.payment_mode != "mock":
            raise HTTPException(404)
        j = get_job(job_id, request)
        if j["status"] != "ready":
            raise HTTPException(409, "job not ready")
        store.update(job_id, paid=1)
        return {"paid": True}

    @app.post("/api/jobs/{job_id}/verify-payment")
    def verify(job_id: str, request: Request):
        j = get_job(job_id, request)
        if cfg.payment_mode == "stripe" and j["stripe_session"] and not j["paid"]:
            ok, ref = payments.retrieve_session_paid(cfg, j["stripe_session"])
            if ok and ref == job_id:
                store.update(job_id, paid=1)
        return public(get_job(job_id, request))

    @app.post("/api/stripe/webhook")
    async def webhook(request: Request):
        payload = await request.body()
        if not cfg.stripe_webhook_secret or not payments.verify_webhook(
                payload, request.headers.get("stripe-signature", ""), cfg.stripe_webhook_secret):
            raise HTTPException(400, "bad signature")
        ev = json.loads(payload)
        if ev.get("type") == "checkout.session.completed":
            obj = ev["data"]["object"]
            if obj.get("payment_status") == "paid" and obj.get("client_reference_id"):
                if store.get(obj["client_reference_id"]):
                    store.update(obj["client_reference_id"], paid=1)
        return {"received": True}

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str, request: Request):
        j = get_job(job_id, request)
        if not j["paid"]:
            raise HTTPException(402, "payment required")
        p = jobs.job_dir(cfg, job_id) / "full.zip"
        if not p.exists():
            raise HTTPException(404, "export not found")
        return FileResponse(p, media_type="application/zip", filename=f"usd-export-{job_id[:8]}.zip")

    @app.exception_handler(HTTPException)
    async def _h(_, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.get("/healthz")
    def health():
        return {"ok": True}

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app


def app_factory() -> FastAPI:
    return create_app()
