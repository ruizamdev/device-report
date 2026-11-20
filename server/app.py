"""Device Report API server with SQLite metadata index and ZIP storage."""

import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "reports.db"
UPLOADS_DIR = DATA_DIR / "uploads"
API_TOKEN = os.environ.get("API_TOKEN", "")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024

app = FastAPI(
    title="Device Report API",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


def init_db() -> None:
    """Ensure data directories and SQLite schema exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_client ON reports(client_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_hostname ON reports(hostname)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_disk_status ON reports(disk_overall_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC)")
        conn.commit()


@contextmanager
def get_db():
    """Yield a SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Validate Bearer API token configured via API_TOKEN environment variable."""
    if not API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_TOKEN is not configured on the server.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    provided = authorization[len("Bearer ") :].strip()
    if not secrets.compare_digest(provided, API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "report.zip"


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check endpoint."""
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {"status": "ok", "reports_count": count}


@app.post("/api/v1/reports", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_token)])
async def create_report(
    file: UploadFile = File(...),
    metadata: str = Form(...),
) -> dict[str, Any]:
    """Receive a zipped device report and JSON summary metadata, store on disk and index in SQLite."""
    init_db()
    try:
        meta: dict[str, Any] = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {exc}") from exc

    client_name = str(meta.get("client_name") or "").strip()
    if not client_name:
        raise HTTPException(status_code=400, detail="metadata.client_name is required.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds size limit.")

    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    rel_dir = Path(now.strftime("%Y/%m"))
    dest_dir = UPLOADS_DIR / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or f"{client_name}.zip")
    stored_name = f"{report_id}_{safe_name}"
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(content)

    rel_zip_path = str(rel_dir / stored_name)
    disks = meta.get("disks") or []
    disk_status = str(meta.get("disk_overall_status") or "UNKNOWN").upper()
    created_at = now.isoformat()

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO reports (
                id, client_name, technician, notes, hostname, username,
                serial_number, manufacturer, model, os_name, cpu, ram_gb,
                disk_overall_status, disks_json, metadata_json,
                zip_filename, zip_path, zip_size_bytes, collected_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                safe_name,
                rel_zip_path,
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
        "created_at": created_at,
    }


@app.get("/api/v1/reports", dependencies=[Depends(require_token)])
def list_reports(
    client: Optional[str] = Query(default=None),
    hostname: Optional[str] = Query(default=None),
    disk_status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List stored reports with optional filters for workshop integration."""
    init_db()
    clauses: list[str] = []
    params: list[Any] = []

    if client:
        clauses.append("LOWER(client_name) LIKE ?")
        params.append(f"%{client.strip().lower()}%")
    if hostname:
        clauses.append("LOWER(hostname) LIKE ?")
        params.append(f"%{hostname.strip().lower()}%")
    if disk_status:
        clauses.append("UPPER(disk_overall_status) = ?")
        params.append(disk_status.strip().upper())

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM reports {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, client_name, technician, hostname, username, serial_number,
                   manufacturer, model, os_name, cpu, ram_gb, disk_overall_status,
                   zip_filename, zip_size_bytes, collected_at, created_at
            FROM reports
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows],
    }


@app.get("/api/v1/reports/{report_id}", dependencies=[Depends(require_token)])
def get_report(report_id: str) -> dict[str, Any]:
    """Return full report metadata including parsed disks_json."""
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    data = dict(row)
    data["disks"] = json.loads(data.pop("disks_json") or "[]")
    data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    return data


@app.get("/api/v1/reports/{report_id}/download", dependencies=[Depends(require_token)])
def download_report(report_id: str):
    """Download the stored ZIP archive for a report."""
    init_db()
    with get_db() as conn:
        row = conn.execute(
            "SELECT zip_path, zip_filename FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")
    file_path = (UPLOADS_DIR / row["zip_path"]).resolve()
    if not str(file_path).startswith(str(UPLOADS_DIR.resolve())) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored archive not found.")
    return FileResponse(path=file_path, media_type="application/zip", filename=row["zip_filename"])
