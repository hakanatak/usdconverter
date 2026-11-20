import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, status TEXT, name TEXT, spec TEXT, report TEXT, error TEXT,
 price_cents INTEGER DEFAULT 0, paid INTEGER DEFAULT 0, stripe_session TEXT,
 created REAL, updated REAL)"""


USERS = """CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, is_admin INTEGER DEFAULT 0,
 failed INTEGER DEFAULT 0, locked_until REAL DEFAULT 0, created REAL, last_login REAL)"""
SESSIONS = """CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created REAL, last_seen REAL, expires REAL, ip TEXT, ua TEXT)"""


CONNS = """CREATE TABLE IF NOT EXISTS connections(
 id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT, kind TEXT, url TEXT, created REAL)"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        with self._c() as c:
            c.execute(SCHEMA)
            c.execute(USERS)
            c.execute(SESSIONS)
            c.execute(CONNS)
            cols = [r["name"] for r in c.execute("PRAGMA table_info(jobs)")]
            if "user_id" not in cols:
                c.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER")

    def _c(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def create(self, job_id: str, name: str, spec: dict, user_id: int | None = None):
        now = time.time()
        with self._lock, self._c() as c:
            c.execute("INSERT INTO jobs(id,status,name,spec,created,updated,user_id) VALUES(?,?,?,?,?,?,?)",
                      (job_id, "queued", name, json.dumps(spec), now, now, user_id))

    def list_jobs(self, user_id: int | None = None, limit: int = 200):
        q = ("SELECT j.id,j.status,j.name,j.price_cents,j.paid,j.created,j.error,u.email FROM jobs j "
             "LEFT JOIN users u ON u.id=j.user_id ")
        args: tuple = ()
        if user_id is not None:
            q += "WHERE j.user_id=? "
            args = (user_id,)
        q += "ORDER BY j.created DESC LIMIT ?"
        with self._c() as c:
            return [dict(r) for r in c.execute(q, (*args, limit))]

    # ---- users / sessions
    def add_user(self, email: str, pw_hash: str, is_admin: bool) -> int:
        with self._lock, self._c() as c:
            cur = c.execute("INSERT INTO users(email,pw_hash,is_admin,created) VALUES(?,?,?,?)",
                            (email, pw_hash, int(is_admin), time.time()))
            return cur.lastrowid

    def user_by_email(self, email: str):
        with self._c() as c:
            r = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(r) if r else None

    def update_user(self, uid: int, **kw):
        cols = ", ".join(f"{k}=?" for k in kw)
        with self._lock, self._c() as c:
            c.execute(f"UPDATE users SET {cols} WHERE id=?", (*kw.values(), uid))

    def list_users(self):
        with self._c() as c:
            return [dict(r) for r in c.execute(
                "SELECT u.id,u.email,u.is_admin,u.created,u.last_login,"
                "(SELECT COUNT(*) FROM jobs j WHERE j.user_id=u.id) AS jobs FROM users u ORDER BY u.created DESC")]

    def add_session(self, token_hash: str, uid: int, expires: float, ip: str, ua: str):
        now = time.time()
        with self._lock, self._c() as c:
            c.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?)", (token_hash, uid, now, now, expires, ip, ua[:200]))

    def session_user(self, token_hash: str):
        with self._c() as c:
            r = c.execute("SELECT u.*, s.last_seen AS _seen FROM sessions s JOIN users u ON u.id=s.user_id "
                          "WHERE s.token_hash=? AND s.expires>?", (token_hash, time.time())).fetchone()
        return dict(r) if r else None

    def touch_session(self, token_hash: str):
        with self._lock, self._c() as c:
            c.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (time.time(), token_hash))

    def delete_session(self, token_hash: str):
        with self._lock, self._c() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def list_sessions(self):
        with self._c() as c:
            return [dict(r) for r in c.execute(
                "SELECT u.email,s.created,s.last_seen,s.expires,s.ip,s.ua FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.expires>? ORDER BY s.last_seen DESC", (time.time(),))]

    def kill_sessions(self, uid: int):
        with self._lock, self._c() as c:
            c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))

    def purge_sessions(self):
        with self._lock, self._c() as c:
            c.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))

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

    # ---- connections (URL only; secrets are never stored)
    def add_conn(self, cid: str, uid: int, name: str, kind: str, url: str):
        with self._lock, self._c() as c:
            c.execute("INSERT INTO connections VALUES(?,?,?,?,?,?)", (cid, uid, name, kind, url, time.time()))

    def list_conns(self, uid: int):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT id,name,kind,url,created FROM connections WHERE user_id=? ORDER BY created DESC", (uid,))]

    def get_conn(self, cid: str, uid: int):
        with self._c() as c:
            r = c.execute("SELECT * FROM connections WHERE id=? AND user_id=?", (cid, uid)).fetchone()
        return dict(r) if r else None

    def delete_conn(self, cid: str, uid: int):
        with self._lock, self._c() as c:
            c.execute("DELETE FROM connections WHERE id=? AND user_id=?", (cid, uid))
