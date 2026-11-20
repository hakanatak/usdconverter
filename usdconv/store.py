import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, status TEXT, name TEXT, spec TEXT, report TEXT, error TEXT,
 price_cents INTEGER DEFAULT 0, paid INTEGER DEFAULT 0, stripe_session TEXT,
 created REAL, updated REAL)"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        with self._c() as c:
            c.execute(SCHEMA)

    def _c(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def create(self, job_id: str, name: str, spec: dict):
        now = time.time()
        with self._lock, self._c() as c:
            c.execute("INSERT INTO jobs(id,status,name,spec,created,updated) VALUES(?,?,?,?,?,?)",
                      (job_id, "queued", name, json.dumps(spec), now, now))

    def update(self, job_id: str, **kw):
        kw["updated"] = time.time()
        for k in ("report",):
            if k in kw and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k])
        cols = ", ".join(f"{k}=?" for k in kw)
        with self._lock, self._c() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*kw.values(), job_id))

    def get(self, job_id: str):
        with self._c() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(r) if r else None

    def by_session(self, session_id: str):
        with self._c() as c:
            r = c.execute("SELECT * FROM jobs WHERE stripe_session=?", (session_id,)).fetchone()
        return dict(r) if r else None

    def expired(self, older_than: float):
        with self._c() as c:
            return [r["id"] for r in c.execute("SELECT id FROM jobs WHERE created<?", (older_than,))]

    def delete(self, job_id: str):
        with self._lock, self._c() as c:
            c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
