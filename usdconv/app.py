import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import jobs, payments
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

    def get_job(job_id: str) -> dict:
        j = store.get(job_id)
        if not j:
            raise HTTPException(404, "job not found")
        return j

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
    async def create_job(spec: str = Form(...), files: list[UploadFile] = File(default=[])):
        try:
            js = JobSpec.model_validate_json(spec)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json())) from e
        uploads, total = {}, 0
        for f in files:
            data = await f.read(cfg.max_upload_mb * 1024 * 1024 + 1)
            total += len(data)
            if total > cfg.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, "upload too large")
            uploads[f.filename] = data
        jobs.purge_expired(cfg, store, time.time())
        job_id = secrets.token_urlsafe(16)
        store.create(job_id, js.name, js.model_dump())
        pool.submit(jobs.run_job, cfg, store, job_id, js.model_dump(), uploads)
        return {"id": job_id}

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str):
        return public(get_job(job_id))

    @app.get("/api/jobs/{job_id}/preview.glb")
    def preview(job_id: str):
        j = get_job(job_id)
        p = jobs.job_dir(cfg, job_id) / "preview.glb"
        if j["status"] != "ready" or not p.exists():
            raise HTTPException(409, "preview not ready")
        return FileResponse(p, media_type="model/gltf-binary")

    @app.post("/api/jobs/{job_id}/checkout")
    def checkout(job_id: str):
        j = get_job(job_id)
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
    def mock_pay(job_id: str):
        """Development only: disabled as soon as a Stripe key is configured."""
        if cfg.payment_mode != "mock":
            raise HTTPException(404)
        j = get_job(job_id)
        if j["status"] != "ready":
            raise HTTPException(409, "job not ready")
        store.update(job_id, paid=1)
        return {"paid": True}

    @app.post("/api/jobs/{job_id}/verify-payment")
    def verify(job_id: str):
        j = get_job(job_id)
        if cfg.payment_mode == "stripe" and j["stripe_session"] and not j["paid"]:
            ok, ref = payments.retrieve_session_paid(cfg, j["stripe_session"])
            if ok and ref == job_id:
                store.update(job_id, paid=1)
        return public(get_job(job_id))

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
    def download(job_id: str):
        j = get_job(job_id)
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
