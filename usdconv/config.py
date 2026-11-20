"""Deployment-level configuration (env vars, prefix USDC_)."""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("USDC_DATA_DIR", "data")))
    base_url: str = field(default_factory=lambda: os.environ.get("USDC_BASE_URL", "http://localhost:8000"))
    stripe_secret_key: str = field(default_factory=lambda: os.environ.get("STRIPE_SECRET_KEY", ""))
    stripe_webhook_secret: str = field(default_factory=lambda: os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    min_price_cents: int = field(default_factory=lambda: _i("USDC_MIN_PRICE_CENTS", 900))
    price_per_1k_features_cents: int = field(default_factory=lambda: _i("USDC_PRICE_PER_1K_CENTS", 100))
    max_upload_mb: int = field(default_factory=lambda: _i("USDC_MAX_UPLOAD_MB", 50))
    max_features: int = field(default_factory=lambda: _i("USDC_MAX_FEATURES", 200_000))
    preview_max_features: int = field(default_factory=lambda: _i("USDC_PREVIEW_MAX_FEATURES", 1500))
    retention_hours: int = field(default_factory=lambda: _i("USDC_RETENTION_HOURS", 72))
    fetch_timeout_s: int = field(default_factory=lambda: _i("USDC_FETCH_TIMEOUT_S", 30))
    workers: int = field(default_factory=lambda: _i("USDC_WORKERS", 2))
    # Tests only: allow fetching from loopback/private hosts. NEVER enable in production.
    allow_private_hosts: bool = field(default_factory=lambda: os.environ.get("USDC_ALLOW_PRIVATE_HOSTS") == "1")

    @property
    def payment_mode(self) -> str:
        return "stripe" if self.stripe_secret_key else "mock"
