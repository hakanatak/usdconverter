"""Payments. Stripe Checkout (REST, no SDK) when STRIPE_SECRET_KEY is set; otherwise a dev-only mock."""
import hashlib
import hmac
import time

import httpx

from .config import Settings


def quote_cents(features: int, cfg: Settings) -> int:
    return cfg.min_price_cents + (features // 1000) * cfg.price_per_1k_features_cents


def create_checkout(cfg: Settings, job_id: str, name: str, cents: int) -> dict:
    r = httpx.post(
        "https://api.stripe.com/v1/checkout/sessions",
        auth=(cfg.stripe_secret_key, ""),
        data={
            "mode": "payment",
            "client_reference_id": job_id,
            "metadata[job_id]": job_id,
            "payment_intent_data[metadata][job_id]": job_id,
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": cents,
            "line_items[0][price_data][product_data][name]": f"USD export: {name}"[:200],
            "success_url": f"{cfg.base_url}/?job={job_id}&paid=1",
            "cancel_url": f"{cfg.base_url}/?job={job_id}",
        }, timeout=30)
    r.raise_for_status()
    j = r.json()
    return {"id": j["id"], "url": j["url"]}


def retrieve_session_paid(cfg: Settings, session_id: str) -> tuple[bool, str | None]:
    r = httpx.get(f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
                  auth=(cfg.stripe_secret_key, ""), timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get("payment_status") == "paid", j.get("client_reference_id")


def verify_webhook(payload: bytes, header: str, secret: str, tolerance: int = 300) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts, sig = parts["t"], parts["v1"]
    except Exception:
        return False
    if abs(time.time() - int(ts)) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
