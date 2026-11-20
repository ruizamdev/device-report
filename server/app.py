"""Device Report API: SQLite metadata index, ZIP storage and authenticated viewer endpoints.

Auth model
- Upload (POST /api/v1/reports): Bearer API_TOKEN, embedded in every DeviceReport.exe.
  That token can ONLY upload; it cannot read reports.
- Read endpoints (list/detail/download/html/stats): session cookie obtained via
  POST /api/v1/auth/login with ADMIN_USER / ADMIN_PASSWORD_HASH.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import uuid
import zipfile
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_VERSION = "2.1.0"
SESSION_COOKIE = "dr_session"
FULL_REPORT_NAME = "report.json"
HTML_REPORT_NAME = "reporte.html"
MAX_FULL_REPORT_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 20 * 1024 * 1024
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
VALID_DISK_STATUSES = {"OK", "WARNING", "CRITICAL", "UNKNOWN"}


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

    @property
    def panel_enabled(self) -> bool:
        return bool(self.admin_user and self.admin_password_hash and len(self.session_secret) >= 32)


settings = Settings()


# --------------------------------------------------------------------------- passwords

def hash_password(password: str, *, n: int = 2**14, r: int = 8, p: int = 1) -> str:
    """Return a scrypt hash as `scrypt:n:r:p:salt:hash` (base64url, no `$` so it is .env-safe)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
    return f"scrypt:{n}:{r}:{p}:{b64(salt)}:{b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = encoded.split(":")
        if algo != "scrypt":
            return False
        unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
        expected = unb64(hash_b64)
        digest = hashlib.scrypt(
            password.encode(), salt=unb64(salt_b64), n=int(n), r=int(r), p=int(p), dklen=len(expected)
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
    payload = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload.encode())}"


def read_session_token(token: str) -> Optional[str]:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload.encode())):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < time.time() or data.get("u") != settings.admin_user:
        return None
    return str(data["u"])


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


def _zip_path_for(row: sqlite3.Row) -> Path:
    base = settings.uploads_dir.resolve()
    file_path = (settings.uploads_dir / row["zip_path"]).resolve()
    if not file_path.is_relative_to(base) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored archive not found.")
    return file_path


def _read_zip_member(zip_source: Any, name: str, max_bytes: int) -> Optional[bytes]:
    """Read a top-level member from a ZIP, bounded by its declared and actual size. None if absent/invalid."""
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


def _extract_full_report(zip_bytes: bytes) -> Optional[str]:
    import io

    raw = _read_zip_member(io.BytesIO(zip_bytes), FULL_REPORT_NAME, MAX_FULL_REPORT_BYTES)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return json.dumps(parsed, ensure_ascii=False)


# --------------------------------------------------------------------------- auth deps

def require_upload_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Validate the Bearer upload token configured via API_TOKEN."""
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="API_TOKEN is not configured on the server.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    provided = authorization[len("Bearer ") :].strip()
    if not secrets.compare_digest(provided, settings.api_token):
        raise HTTPException(status_code=401, detail="Invalid API token.")


def require_session(request: Request) -> str:
    """Validate the viewer session cookie and return the username."""
    if not settings.panel_enabled:
        raise HTTPException(status_code=503, detail="El panel no está configurado en el servidor.")
    token = request.cookies.get(SESSION_COOKIE)
    user = read_session_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada.")
    return user


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- app

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Device Report API",
    version=APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "report.zip"


@app.get("/health")
def health() -> dict[str, Any]:
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {"status": "ok", "version": APP_VERSION, "reports_count": count}


# ---- auth

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    if not settings.panel_enabled:
        raise HTTPException(status_code=503, detail="El panel no está configurado en el servidor.")
    ip = _client_ip(request)
    if login_throttle.blocked(ip):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta de nuevo más tarde.")
    user_ok = hmac.compare_digest(body.username.strip().encode(), settings.admin_user.encode())
    pass_ok = verify_password(body.password, settings.admin_password_hash)
    if not (user_ok and pass_ok):
        login_throttle.fail(ip)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    login_throttle.reset(ip)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(settings.admin_user),
        max_age=settings.session_ttl,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"username": settings.admin_user}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")
    response.status_code = 204
    return response


@app.get("/api/v1/auth/me")
def me(user: str = Depends(require_session)) -> dict[str, Any]:
    return {"username": user}


# ---- upload

@app.post("/api/v1/reports", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_upload_token)])
async def create_report(file: UploadFile = File(...), metadata: str = Form(...)) -> dict[str, Any]:
    """Receive a zipped device report and JSON summary metadata, store on disk and index in SQLite."""
    try:
        meta: dict[str, Any] = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object.")

    client_name = str(meta.get("client_name") or "").strip()
    if not client_name:
        raise HTTPException(status_code=400, detail="metadata.client_name is required.")

    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds size limit.")

    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    rel_dir = Path(now.strftime("%Y/%m"))
    dest_dir = settings.uploads_dir / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or f"{client_name}.zip")
    stored_name = f"{report_id}_{safe_name}"
    (dest_dir / stored_name).write_bytes(content)

    disks = meta.get("disks") or []
    disk_status = str(meta.get("disk_overall_status") or "UNKNOWN").upper()
    if disk_status not in VALID_DISK_STATUSES:
        disk_status = "UNKNOWN"
    created_at = now.isoformat()
    full_json = _extract_full_report(content)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO reports (
                id, client_name, technician, notes, hostname, username,
                serial_number, manufacturer, model, os_name, cpu, ram_gb,
                disk_overall_status, disks_json, metadata_json, full_json,
                zip_filename, zip_path, zip_size_bytes, collected_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                client_name,
                meta.get("technician"),
                meta.get("notes"),
                meta.get("hostname"),
                meta.get("username"),
                meta.get("serial_number"),
                meta.get("manufacturer"),
                meta.get("model"),
                meta.get("os_name"),
                meta.get("cpu"),
                meta.get("ram_gb"),
                disk_status,
                json.dumps(disks, ensure_ascii=False),
                json.dumps(meta, ensure_ascii=False),
                full_json,
                safe_name,
                str(rel_dir / stored_name),
                len(content),
                meta.get("collected_at"),
                created_at,
            ),
        )
        conn.commit()

    return {
        "id": report_id,
        "client_name": client_name,
        "hostname": meta.get("hostname"),
        "disk_overall_status": disk_status,
        "zip_size_bytes": len(content),
        "has_full_report": full_json is not None,
        "created_at": created_at,
    }


# ---- read (session required)

def _like(value: str) -> str:
    escaped = value.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@app.get("/api/v1/reports", dependencies=[Depends(require_session)])
def list_reports(
    q: Optional[str] = Query(default=None, description="Busca en cliente, equipo, serie, usuario y modelo"),
    client: Optional[str] = Query(default=None),
    hostname: Optional[str] = Query(default=None),
    serial: Optional[str] = Query(default=None, description="Número de serie exacto"),
    disk_status: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="ISO date/datetime (created_at >=)"),
    date_to: Optional[str] = Query(default=None, description="ISO date/datetime (created_at <=, inclusive day)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    if q:
        fields = ["client_name", "hostname", "serial_number", "username", "model", "technician"]
        clauses.append("(" + " OR ".join(f"LOWER(COALESCE({f}, '')) LIKE ? ESCAPE '\\'" for f in fields) + ")")
        params.extend([_like(q)] * len(fields))
    if client:
        clauses.append("LOWER(client_name) LIKE ? ESCAPE '\\'")
        params.append(_like(client))
    if hostname:
        clauses.append("LOWER(hostname) LIKE ? ESCAPE '\\'")
        params.append(_like(hostname))
    if serial:
        clauses.append("serial_number = ?")
        params.append(serial.strip())
    if disk_status:
        clauses.append("UPPER(disk_overall_status) = ?")
        params.append(disk_status.strip().upper())
    if date_from:
        clauses.append("created_at >= ?")
        params.append(_parse_date_bound(date_from, end=False))
    if date_to:
        clauses.append("created_at <= ?")
        params.append(_parse_date_bound(date_to, end=True))

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


def _parse_date_bound(value: str, *, end: bool) -> str:
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
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {value}") from exc


@app.get("/api/v1/stats", dependencies=[Depends(require_session)])
def stats(months: int = Query(default=12, ge=1, le=36), top: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        by_status = {s: 0 for s in ("OK", "WARNING", "CRITICAL", "UNKNOWN")}
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


def _get_row(conn: sqlite3.Connection, report_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    return row


@app.get("/api/v1/reports/{report_id}", dependencies=[Depends(require_session)])
def get_report(report_id: str) -> dict[str, Any]:
    """Full report: indexed metadata, disks, and the complete `report` (null for legacy uploads)."""
    with get_db() as conn:
        data = dict(_get_row(conn, report_id))
    data.pop("zip_path", None)
    data["disks"] = json.loads(data.pop("disks_json") or "[]")
    data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    full = data.pop("full_json")
    data["report"] = json.loads(full) if full else None
    data["has_full_report"] = full is not None
    return data


@app.get("/api/v1/devices/{serial}/reports", dependencies=[Depends(require_session)])
def device_history(serial: str) -> dict[str, Any]:
    """All reports for one serial number, oldest first, with disk metrics for trend charts."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, client_name, hostname, disk_overall_status, disks_json, collected_at, created_at
            FROM reports WHERE serial_number = ? ORDER BY created_at ASC
            """,
            (serial.strip(),),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No hay reportes para ese número de serie.")
    items = []
    for r in rows:
        item = dict(r)
        item["disks"] = json.loads(item.pop("disks_json") or "[]")
        items.append(item)
    return {"serial_number": serial.strip(), "total": len(items), "items": items}


@app.get("/api/v1/reports/{report_id}/download", dependencies=[Depends(require_session)])
def download_report(report_id: str):
    with get_db() as conn:
        row = _get_row(conn, report_id)
    return FileResponse(path=_zip_path_for(row), media_type="application/zip", filename=row["zip_filename"])


# The HTML comes from the client machine: render it fully sandboxed (no scripts, no network).
HTML_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, no-store",
}


@app.get("/api/v1/reports/{report_id}/html", dependencies=[Depends(require_session)])
def report_html(report_id: str) -> Response:
    with get_db() as conn:
        row = _get_row(conn, report_id)
    html = _read_zip_member(_zip_path_for(row), HTML_REPORT_NAME, MAX_HTML_BYTES)
    if html is None:
        raise HTTPException(status_code=404, detail="El ZIP no contiene reporte.html.")
    return Response(content=html, media_type="text/html; charset=utf-8", headers=HTML_SECURITY_HEADERS)


# --------------------------------------------------------------------------- CLI

def _cli() -> None:
    """`python app.py hash-password` reads a password from stdin and prints its hash."""
    if len(sys.argv) >= 2 and sys.argv[1] == "hash-password":
        password = sys.stdin.readline().rstrip("\r\n")
        if len(password) < 10:
            print("La contraseña debe tener al menos 10 caracteres.", file=sys.stderr)
            sys.exit(2)
        print(hash_password(password))
        return
    print("Uso: echo <password> | python app.py hash-password", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    _cli()
