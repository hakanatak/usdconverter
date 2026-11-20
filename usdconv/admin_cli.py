"""Operator tool: reset a user's password locally (no e-mail flow yet).

    python -m usdconv.admin_cli reset-password you@example.com

Run it on the machine that holds the database, from the same folder the server runs in
(or set USDC_DATA_DIR). The new password is typed hidden; it never leaves your machine.
"""
import argparse
import getpass
import sys

from . import auth
from .config import Settings
from .store import Store


def reset_password(store: Store, email: str, password: str) -> bool:
    u = store.user_by_email(email.strip().lower())
    if not u:
        return False
    auth.check_new_password(password)
    store.update_user(u["id"], pw_hash=auth.hash_password(password), failed=0, locked_until=0)
    store.kill_sessions(u["id"])  # sign out everywhere
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="usdconv.admin_cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset-password", help="set a new password and clear any lockout")
    r.add_argument("email")
    r.add_argument("--data-dir", help="defaults to USDC_DATA_DIR or ./data")
    a = ap.parse_args(argv)
    cfg = Settings()
    if a.data_dir:
        from pathlib import Path
        cfg.data_dir = Path(a.data_dir)
    db = cfg.data_dir / "db.sqlite"
    if not db.exists():
        print(f"Database not found: {db.resolve()}\nRun this from the server's folder or pass --data-dir.", file=sys.stderr)
        return 2
    store = Store(db)
    if not store.user_by_email(a.email.strip().lower()):
        print("No such user.", file=sys.stderr)
        return 1
    pw = getpass.getpass("New password (min. 10 chars): ")
    if pw != getpass.getpass("Repeat: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        reset_password(store, a.email, pw)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    print("Password changed. All existing sessions were signed out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
