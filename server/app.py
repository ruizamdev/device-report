"""Device Report API + web panel.

Auth model
- Upload (POST /api/v1/reports): Bearer API_TOKEN, embedded in every DeviceReport.exe.
  That token can ONLY upload; it cannot read reports.
- Read endpoints and the web panel: session cookie obtained via login with
  ADMIN_USER / ADMIN_PASSWORD_HASH.
"""

from __future__ import annotations

import json
import re
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import core
import web

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- auth deps

def require_upload_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Validate the Bearer upload token configured via API_TOKEN."""
    if not core.settings.api_token:
        raise HTTPException(status_code=503, detail="API_TOKEN is not configured on the server.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    provided = authorization[len("Bearer ") :].strip()
    if not secrets.compare_digest(provided, core.settings.api_token):
        raise HTTPException(status_code=401, detail="Invalid API token.")


def require_session(request: Request) -> str:
    """Validate the viewer session cookie and return the username."""
    if not core.settings.panel_enabled:
        raise HTTPException(status_code=503, detail="El panel no está configurado en el servidor.")
    user = core.read_session_token(request.cookies.get(core.SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada.")
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- app

@asynccontextmanager
async def lifespan(_: FastAPI):
    core.init_db()
    yield


app = FastAPI(
    title="Device Report API",
    version=core.APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(web.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Content-Security-Policy", web.PAGE_CSP)
        response.headers.setdefault("X-Frame-Options", "DENY")
    return response


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "report.zip"


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": core.APP_VERSION, "reports_count": core.count_reports()}


# ---- auth

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        token = core.authenticate(body.username, body.password, client_ip(request))
    except core.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    response.set_cookie(core.SESSION_COOKIE, token, max_age=core.settings.session_ttl, **core.session_cookie_kwargs())
    return {"username": core.settings.admin_user}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(core.SESSION_COOKIE, **core.session_cookie_kwargs())
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

    max_bytes = core.settings.max_upload_bytes
    content = await file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds size limit.")

    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    rel_dir = Path(now.strftime("%Y/%m"))
    dest_dir = core.settings.uploads_dir / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or f"{client_name}.zip")
    stored_name = f"{report_id}_{safe_name}"
    (dest_dir / stored_name).write_bytes(content)

    disks = meta.get("disks") or []
    disk_status = str(meta.get("disk_overall_status") or "UNKNOWN").upper()
    if disk_status not in core.DISK_STATUSES:
        disk_status = "UNKNOWN"
    created_at = now.isoformat()
    full_json = core.extract_full_report(content)

    with core.get_db() as conn:
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
    try:
        return core.query_reports(
            q=q, client=client, hostname=hostname, serial=serial, disk_status=disk_status,
            date_from=date_from, date_to=date_to, limit=limit, offset=offset,
        )
    except core.QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/stats", dependencies=[Depends(require_session)])
def stats(months: int = Query(default=12, ge=1, le=36), top: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    return core.compute_stats(months=months, top=top)


@app.get("/api/v1/reports/{report_id}", dependencies=[Depends(require_session)])
def get_report(report_id: str) -> dict[str, Any]:
    data = core.fetch_report(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found.")
    return data


@app.get("/api/v1/devices/{serial}/reports", dependencies=[Depends(require_session)])
def device_history(serial: str) -> dict[str, Any]:
    items = core.fetch_device_history(serial)
    if not items:
        raise HTTPException(status_code=404, detail="No hay reportes para ese número de serie.")
    return {"serial_number": serial.strip(), "total": len(items), "items": items}


def _zip_for(report_id: str) -> tuple[Path, str]:
    row = core.fetch_report_row(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    path = core.stored_zip_path(row["zip_path"])
    if not path:
        raise HTTPException(status_code=404, detail="Stored archive not found.")
    return path, row["zip_filename"]


@app.get("/api/v1/reports/{report_id}/download", dependencies=[Depends(require_session)])
def download_report(report_id: str):
    path, filename = _zip_for(report_id)
    return FileResponse(path=path, media_type="application/zip", filename=filename)


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
    path, _ = _zip_for(report_id)
    html = core.read_zip_member(path, core.HTML_REPORT_NAME, core.MAX_HTML_BYTES)
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
        print(core.hash_password(password))
        return
    print("Uso: echo <password> | python app.py hash-password", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    _cli()
