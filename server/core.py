"""Shared logic for the API and the web panel: settings, auth, storage and queries."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

APP_VERSION = "2.2.0"
SESSION_COOKIE = "dr_session"
FULL_REPORT_NAME = "report.json"
HTML_REPORT_NAME = "reporte.html"
MAX_FULL_REPORT_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 20 * 1024 * 1024
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
DISK_STATUSES = ("OK", "WARNING", "CRITICAL", "UNKNOWN")


class Settings:
    """Runtime configuration read from environment variables."""

    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("DATA_DIR", "/data"))
        self.db_path = self.data_dir / "reports.db"
        self.uploads_dir = self.data_dir / "uploads"
        self.api_token = os.environ.get("API_TOKEN", "")
        self.max_upload_bytes = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
        self.admin_user = os.environ.get("ADMIN_USER", "").strip()
        self.admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
        self.session_secret = os.environ.get("SESSION_SECRET", "")
        self.session_ttl = int(os.environ.get("SESSION_TTL_HOURS", "12")) * 3600
        self.cookie_secure = os.environ.get("COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
        self.display_tz = os.environ.get("TZ", "America/Mexico_City") or "America/Mexico_City"

    @property
    def panel_enabled(self) -> bool:
        return bool(self.admin_user and self.admin_password_hash and len(self.session_secret) >= 32)


settings = Settings()


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# --------------------------------------------------------------------------- passwords

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, *, n: int = 2**14, r: int = 8, p: int = 1) -> str:
    """Return a scrypt hash as `scrypt:n:r:p:salt:hash` (base64url, no `$` so it is .env-safe)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt:{n}:{r}:{p}:{_b64(salt)}:{_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = encoded.split(":")
        if algo != "scrypt":
            return False
        expected = _unb64(hash_b64)
        digest = hashlib.scrypt(
            password.encode(), salt=_unb64(salt_b64), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- sessions

def _sign(payload: bytes) -> str:
    # Including the password hash in the key invalidates all sessions when the password changes.
    key = f"{settings.session_secret}\x00{settings.admin_password_hash}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def create_session_token(username: str) -> str:
    body = json.dumps({"u": username, "exp": int(time.time()) + settings.session_ttl}, separators=(",", ":"))
    payload = _b64(body.encode())
    return f"{payload}.{_sign(payload.encode())}"


def read_session_token(token: Optional[str]) -> Optional[str]:
    if not token or not settings.panel_enabled:
        return None
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload.encode())):
        return None
    try:
        data = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < time.time() or data.get("u") != settings.admin_user:
        return None
    return str(data["u"])


def session_cookie_kwargs() -> dict[str, Any]:
    return {"httponly": True, "secure": settings.cookie_secure, "samesite": "strict", "path": "/"}


class LoginThrottle:
    """In-memory per-IP failure counter (single container, single worker)."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._failures.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]

    def blocked(self, key: str) -> bool:
        with self._lock:
            recent = self._recent(key, time.time())
            self._failures[key] = recent
            return len(recent) >= LOGIN_MAX_FAILURES

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.time()
            self._failures[key] = [*self._recent(key, now), now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_throttle = LoginThrottle()


def authenticate(username: str, password: str, client_ip: str) -> str:
    """Check credentials with throttling. Returns a session token or raises AuthError."""
    if not settings.panel_enabled:
        raise AuthError(503, "El panel no está configurado en el servidor.")
    if login_throttle.blocked(client_ip):
        raise AuthError(429, "Demasiados intentos. Intenta de nuevo más tarde.")
    user_ok = hmac.compare_digest(username.strip().encode(), settings.admin_user.encode())
    pass_ok = verify_password(password, settings.admin_password_hash)
    if not (user_ok and pass_ok):
        login_throttle.fail(client_ip)
        raise AuthError(401, "Usuario o contraseña incorrectos.")
    login_throttle.reset(client_ip)
    return create_session_token(settings.admin_user)


# --------------------------------------------------------------------------- database

def init_db() -> None:
    """Ensure data directories and SQLite schema exist (idempotent, with additive migrations)."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                client_name TEXT NOT NULL,
                technician TEXT,
                notes TEXT,
                hostname TEXT,
                username TEXT,
                serial_number TEXT,
                manufacturer TEXT,
                model TEXT,
                os_name TEXT,
                cpu TEXT,
                ram_gb REAL,
                disk_overall_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                disks_json TEXT,
                metadata_json TEXT,
                zip_filename TEXT NOT NULL,
                zip_path TEXT NOT NULL,
                zip_size_bytes INTEGER NOT NULL,
                collected_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
        if "full_json" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN full_json TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_client ON reports(client_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_hostname ON reports(hostname)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_serial ON reports(serial_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_disk_status ON reports(disk_overall_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC)")
        conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def count_reports() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]


# --------------------------------------------------------------------------- zip helpers

def read_zip_member(zip_source: Any, name: str, max_bytes: int) -> Optional[bytes]:
    """Read a top-level member from a ZIP, bounded by declared and actual size. None if absent/invalid."""
    try:
        with zipfile.ZipFile(zip_source) as zf:
            try:
                info = zf.getinfo(name)
            except KeyError:
                return None
            if info.file_size > max_bytes:
                return None
            with zf.open(info) as fh:
                data = fh.read(max_bytes + 1)
            return data if len(data) <= max_bytes else None
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None


def extract_full_report(zip_bytes: bytes) -> Optional[str]:
    raw = read_zip_member(io.BytesIO(zip_bytes), FULL_REPORT_NAME, MAX_FULL_REPORT_BYTES)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return json.dumps(parsed, ensure_ascii=False)


def stored_zip_path(zip_path: str) -> Optional[Path]:
    base = settings.uploads_dir.resolve()
    file_path = (settings.uploads_dir / zip_path).resolve()
    if not file_path.is_relative_to(base) or not file_path.is_file():
        return None
    return file_path


# --------------------------------------------------------------------------- queries

class QueryError(ValueError):
    pass


def _like(value: str) -> str:
    escaped = value.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def parse_date_bound(value: str, *, end: bool) -> str:
    raw = value.strip()
    try:
        if len(raw) == 10:
            d = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if end:
                d = d.replace(hour=23, minute=59, second=59, microsecond=999999)
            return d.isoformat()
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat()
    except ValueError as exc:
        raise QueryError(f"Fecha inválida: {value}") from exc


def query_reports(
    *,
    q: Optional[str] = None,
    client: Optional[str] = None,
    hostname: Optional[str] = None,
    serial: Optional[str] = None,
    disk_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    if q and q.strip():
        fields = ["client_name", "hostname", "serial_number", "username", "model", "technician"]
        clauses.append("(" + " OR ".join(f"LOWER(COALESCE({f}, '')) LIKE ? ESCAPE '\\'" for f in fields) + ")")
        params.extend([_like(q)] * len(fields))
    if client and client.strip():
        clauses.append("LOWER(client_name) LIKE ? ESCAPE '\\'")
        params.append(_like(client))
    if hostname and hostname.strip():
        clauses.append("LOWER(hostname) LIKE ? ESCAPE '\\'")
        params.append(_like(hostname))
    if serial and serial.strip():
        clauses.append("serial_number = ?")
        params.append(serial.strip())
    if disk_status and disk_status.strip():
        clauses.append("UPPER(disk_overall_status) = ?")
        params.append(disk_status.strip().upper())
    if date_from and date_from.strip():
        clauses.append("created_at >= ?")
        params.append(parse_date_bound(date_from, end=False))
    if date_to and date_to.strip():
        clauses.append("created_at <= ?")
        params.append(parse_date_bound(date_to, end=True))

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM reports {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, client_name, technician, hostname, username, serial_number,
                   manufacturer, model, os_name, cpu, ram_gb, disk_overall_status,
                   zip_filename, zip_size_bytes, collected_at, created_at,
                   (full_json IS NOT NULL) AS has_full_report
            FROM reports
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [{**dict(r), "has_full_report": bool(r["has_full_report"])} for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def compute_stats(*, months: int = 12, top: int = 10) -> dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        by_status = {s: 0 for s in DISK_STATUSES}
        for r in conn.execute("SELECT disk_overall_status s, COUNT(*) c FROM reports GROUP BY s"):
            by_status[r["s"]] = r["c"]
        by_month = [
            dict(r)
            for r in conn.execute(
                """
                SELECT substr(created_at, 1, 7) AS month,
                       COUNT(*) AS total,
                       SUM(disk_overall_status = 'OK') AS ok,
                       SUM(disk_overall_status = 'WARNING') AS warning,
                       SUM(disk_overall_status = 'CRITICAL') AS critical,
                       SUM(disk_overall_status = 'UNKNOWN') AS unknown
                FROM reports GROUP BY month ORDER BY month DESC LIMIT ?
                """,
                (months,),
            )
        ][::-1]
        top_clients = [
            dict(r)
            for r in conn.execute(
                """
                SELECT client_name, COUNT(*) AS total,
                       SUM(disk_overall_status IN ('WARNING', 'CRITICAL')) AS with_alerts,
                       MAX(created_at) AS last_report_at
                FROM reports GROUP BY client_name ORDER BY total DESC, last_report_at DESC LIMIT ?
                """,
                (top,),
            )
        ]
        unique_devices = conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(serial_number, ''), hostname)) FROM reports"
        ).fetchone()[0]
    return {
        "total_reports": total,
        "unique_devices": unique_devices,
        "by_disk_status": by_status,
        "by_month": by_month,
        "top_clients": top_clients,
    }


def fetch_report_row(report_id: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()


def fetch_report(report_id: str) -> Optional[dict[str, Any]]:
    """Full report: indexed metadata, disks, and the complete `report` (None for legacy uploads)."""
    row = fetch_report_row(report_id)
    if not row:
        return None
    data = dict(row)
    data.pop("zip_path", None)
    data["disks"] = json.loads(data.pop("disks_json") or "[]")
    data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    full = data.pop("full_json")
    data["report"] = json.loads(full) if full else None
    data["has_full_report"] = full is not None
    return data


def fetch_device_history(serial: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, client_name, hostname, disk_overall_status, disks_json, collected_at, created_at
            FROM reports WHERE serial_number = ? ORDER BY created_at ASC
            """,
            (serial.strip(),),
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item["disks"] = json.loads(item.pop("disks_json") or "[]")
        items.append(item)
    return items
