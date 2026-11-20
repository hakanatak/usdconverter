"""Job runner: load -> build -> preview GLB (free) + full package (after payment)."""
import io
import json
import shutil
import traceback
import zipfile
from pathlib import Path

from . import engine, payments, sources, writers
from .config import Settings
from .spec import JobSpec
from .store import Store

README_TXT = """usd-converter export
====================
scene.usda  - OpenUSD root layer (Z-up, metres). Tiles are payloads in tiles/.
scene.glb   - same geometry as binary glTF (Y-up).
report.json - build report (CRS, anchor, counts).
All coordinates are local to the anchor in report.json (target CRS, metres).
Add the anchor to X/Y to recover projected coordinates.
"""


def job_dir(cfg: Settings, job_id: str) -> Path:
    return cfg.data_dir / "jobs" / job_id


def run_job(cfg: Settings, store: Store, job_id: str, spec_dict: dict, uploads: dict[str, bytes]):
    try:
        store.update(job_id, status="processing")
        spec = JobSpec.model_validate(spec_dict)
        loaded = [(l, sources.load_layer(l, uploads, cfg)) for l in spec.layers]
        res = engine.build(spec, loaded, cfg.max_features)
        report = res.report()
        out = job_dir(cfg, job_id)
        out.mkdir(parents=True, exist_ok=True)

        # Free preview: subsampled geometry, GLB only. Never contains the full dataset.
        preview = engine.subsample(res, cfg.preview_max_features)
        (out / "preview.glb").write_bytes(writers.write_glb(preview))
        total_features = report["totals"]["features"]
        report["preview_truncated"] = any(l.stats["features"] > cfg.preview_max_features for l in res.layers)

        # Full package, kept server-side until paid.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            if spec.outputs_usd:
                for path, data in writers.write_usd(res, spec.name).items():
                    z.writestr(path, data)
            if spec.outputs_glb:
                z.writestr("scene.glb", writers.write_glb(engine.full_layers(res)))
            z.writestr("report.json", json.dumps(report, indent=2))
            z.writestr("README.txt", README_TXT)
        (out / "full.zip").write_bytes(buf.getvalue())

        cents = payments.quote_cents(total_features, cfg)
        store.update(job_id, status="ready", report=report, price_cents=cents)
    except Exception as e:  # surfaced to the user as a readable message
        traceback.print_exc()
        store.update(job_id, status="failed", error=str(e)[:500])
    finally:
        pass


def purge_expired(cfg: Settings, store: Store, now: float):
    for jid in store.expired(now - cfg.retention_hours * 3600):
        shutil.rmtree(job_dir(cfg, jid), ignore_errors=True)
        store.delete(jid)
