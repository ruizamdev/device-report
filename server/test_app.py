"""Unit and integration tests for Device Report API."""

from __future__ import annotations

import importlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

UPLOAD_TOKEN = "test-upload-token"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "contraseña-segura-123"
UPLOAD_HEADERS = {"Authorization": f"Bearer {UPLOAD_TOKEN}"}


def load_app() -> ModuleType:
    """Re-import core → web → app so Settings picks up the patched environment."""
    import app
    import core
    import web

    importlib.reload(core)
    importlib.reload(web)
    return importlib.reload(app)


@pytest.fixture()
def app_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    import core

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("API_TOKEN", UPLOAD_TOKEN)
    monkeypatch.setenv("ADMIN_USER", ADMIN_USER)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", core.hash_password(ADMIN_PASSWORD, n=2**10))
    monkeypatch.setenv("SESSION_SECRET", "s" * 64)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TZ", "America/Mexico_City")
    return load_app()


@pytest.fixture()
def client(app_module: ModuleType) -> TestClient:
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture()
def viewer(client: TestClient) -> TestClient:
    resp = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return client


def _zip_bytes(*, full_report: dict | None = None, html: str | None = "<h1>Reporte</h1>") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("reporte.txt", "Device Report Test")
        if html is not None:
            zf.writestr("reporte.html", html)
        if full_report is not None:
            zf.writestr("report.json", json.dumps(full_report))
    return buf.getvalue()


def _metadata(**overrides) -> dict:
    meta = {
        "client_name": "Empresa Demo",
        "technician": "Armando",
        "hostname": "PC-TALLER-01",
        "username": "soporte",
        "serial_number": "SN123456",
        "manufacturer": "Dell",
        "model": "OptiPlex 7090",
        "os_name": "Windows 11 Pro",
        "cpu": "Intel Core i7-11700",
        "ram_gb": 16.0,
        "disk_overall_status": "WARNING",
        "disks": [{"model": "Samsung SSD 980", "status": "WARNING", "temperature_c": 58}],
        "collected_at": "2026-11-18T16:00:00Z",
    }
    meta.update(overrides)
    return meta


def _upload(client: TestClient, *, zip_bytes: bytes | None = None, **meta) -> dict:
    resp = client.post(
        "/api/v1/reports",
        headers=UPLOAD_HEADERS,
        files={"file": ("Empresa_Demo.zip", zip_bytes or _zip_bytes(), "application/zip")},
        data={"metadata": json.dumps(_metadata(**meta))},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- health / upload auth

def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_requires_valid_token(client: TestClient) -> None:
    files = {"file": ("test.zip", _zip_bytes(), "application/zip")}
    data = {"metadata": json.dumps({"client_name": "Juan"})}
    assert client.post("/api/v1/reports", files=files, data=data).status_code == 401
    bad = client.post("/api/v1/reports", headers={"Authorization": "Bearer wrong"}, files=files, data=data)
    assert bad.status_code == 401


def test_upload_validates_metadata(client: TestClient) -> None:
    files = {"file": ("test.zip", _zip_bytes(), "application/zip")}
    resp = client.post("/api/v1/reports", headers=UPLOAD_HEADERS, files=files, data={"metadata": "{}"})
    assert resp.status_code == 400
    resp = client.post("/api/v1/reports", headers=UPLOAD_HEADERS, files=files, data={"metadata": "[1]"})
    assert resp.status_code == 400


def test_unknown_disk_status_is_normalized(client: TestClient, viewer: TestClient) -> None:
    created = _upload(client, disk_overall_status="weird")
    assert created["disk_overall_status"] == "UNKNOWN"


# --------------------------------------------------------------------------- read auth separation

@pytest.mark.parametrize(
    "path",
    ["/api/v1/reports", "/api/v1/stats", "/api/v1/reports/x", "/api/v1/reports/x/download",
     "/api/v1/reports/x/html", "/api/v1/devices/SN/reports", "/api/v1/auth/me"],
)
def test_read_endpoints_require_session(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401
    # The upload token embedded in DeviceReport.exe must NOT grant read access.
    assert client.get(path, headers=UPLOAD_HEADERS).status_code == 401


def test_login_logout_flow(client: TestClient) -> None:
    bad = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": "nope"})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert ok.status_code == 200
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/v1/auth/me").json() == {"username": ADMIN_USER}
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tampered_session_is_rejected(viewer: TestClient) -> None:
    token = viewer.cookies.get("dr_session")
    payload, sig = token.rsplit(".", 1)
    viewer.cookies.set("dr_session", f"{payload}.{'0' * len(sig)}")
    assert viewer.get("/api/v1/auth/me").status_code == 401


def test_login_is_throttled(client: TestClient) -> None:
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": "bad"})
    resp = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert resp.status_code == 429


def test_panel_disabled_without_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("API_TOKEN", UPLOAD_TOKEN)
    for var in ("ADMIN_USER", "ADMIN_PASSWORD_HASH", "SESSION_SECRET"):
        monkeypatch.delenv(var, raising=False)
    module = load_app()
    with TestClient(module.app) as c:
        assert c.get("/health").status_code == 200
        assert c.post("/api/v1/auth/login", json={"username": "a", "password": "b"}).status_code == 503
        assert c.get("/api/v1/reports").status_code == 503


# --------------------------------------------------------------------------- data endpoints

def test_upload_list_get_and_download(client: TestClient, viewer: TestClient) -> None:
    zip_bytes = _zip_bytes()
    created = _upload(client, zip_bytes=zip_bytes)
    report_id = created["id"]
    assert created["disk_overall_status"] == "WARNING"
    assert created["has_full_report"] is False

    listing = viewer.get("/api/v1/reports?disk_status=WARNING").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == report_id

    detail = viewer.get(f"/api/v1/reports/{report_id}").json()
    assert detail["disks"][0]["model"] == "Samsung SSD 980"
    assert detail["report"] is None
    assert "zip_path" not in detail

    dl = viewer.get(f"/api/v1/reports/{report_id}/download")
    assert dl.status_code == 200
    assert dl.content == zip_bytes


def test_full_report_is_extracted_from_zip(client: TestClient, viewer: TestClient) -> None:
    full = {"schema_version": 1, "hardware": {"cpu_name": "Ryzen"}, "software": {"installed_programs": []}}
    created = _upload(client, zip_bytes=_zip_bytes(full_report=full))
    assert created["has_full_report"] is True
    detail = viewer.get(f"/api/v1/reports/{created['id']}").json()
    assert detail["report"]["hardware"]["cpu_name"] == "Ryzen"


def test_invalid_zip_or_json_is_tolerated(client: TestClient, viewer: TestClient) -> None:
    created = _upload(client, zip_bytes=b"not a zip")
    assert created["has_full_report"] is False
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.json", "{broken")
    assert _upload(client, zip_bytes=buf.getvalue())["has_full_report"] is False


def test_html_is_served_sandboxed(client: TestClient, viewer: TestClient) -> None:
    created = _upload(client, zip_bytes=_zip_bytes(html="<script>alert(1)</script><p>hola</p>"))
    resp = viewer.get(f"/api/v1/reports/{created['id']}/html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    csp = resp.headers["content-security-policy"]
    assert "sandbox" in csp and "default-src 'none'" in csp
    assert b"<p>hola</p>" in resp.content

    no_html = _upload(client, zip_bytes=_zip_bytes(html=None))
    assert viewer.get(f"/api/v1/reports/{no_html['id']}/html").status_code == 404


def test_search_and_filters(client: TestClient, viewer: TestClient) -> None:
    _upload(client, client_name="Acme", hostname="ACME-PC", serial_number="AAA111", disk_overall_status="OK")
    _upload(client, client_name="Beta 100%", hostname="BETA-LAP", serial_number="BBB222", disk_overall_status="CRITICAL")

    assert viewer.get("/api/v1/reports?q=acme").json()["total"] == 1
    assert viewer.get("/api/v1/reports?q=bbb222").json()["total"] == 1
    assert viewer.get("/api/v1/reports?q=100%25").json()["total"] == 1  # literal %, not wildcard
    assert viewer.get("/api/v1/reports?q=%25").json()["total"] == 1
    assert viewer.get("/api/v1/reports?serial=AAA111").json()["total"] == 1
    assert viewer.get("/api/v1/reports?disk_status=critical").json()["total"] == 1
    assert viewer.get("/api/v1/reports?date_from=2000-01-01&date_to=2999-12-31").json()["total"] == 2
    assert viewer.get("/api/v1/reports?date_to=2000-01-01").json()["total"] == 0
    assert viewer.get("/api/v1/reports?date_from=no-es-fecha").status_code == 422


def test_stats(client: TestClient, viewer: TestClient) -> None:
    _upload(client, client_name="Acme", serial_number="S1", disk_overall_status="OK")
    _upload(client, client_name="Acme", serial_number="S1", disk_overall_status="CRITICAL")
    _upload(client, client_name="Beta", serial_number="S2", disk_overall_status="WARNING")
    data = viewer.get("/api/v1/stats").json()
    assert data["total_reports"] == 3
    assert data["unique_devices"] == 2
    assert data["by_disk_status"] == {"OK": 1, "WARNING": 1, "CRITICAL": 1, "UNKNOWN": 0}
    assert data["by_month"][-1]["total"] == 3
    assert data["top_clients"][0] == {**data["top_clients"][0], "client_name": "Acme", "total": 2, "with_alerts": 1}


def test_device_history(client: TestClient, viewer: TestClient) -> None:
    _upload(client, serial_number="HIST1", disk_overall_status="OK")
    _upload(client, serial_number="HIST1", disk_overall_status="WARNING")
    data = viewer.get("/api/v1/devices/HIST1/reports").json()
    assert data["total"] == 2
    assert [i["disk_overall_status"] for i in data["items"]] == ["OK", "WARNING"]
    assert viewer.get("/api/v1/devices/NOPE/reports").status_code == 404


def test_legacy_db_is_migrated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A reports.db created by v2.0.0 (no full_json column) keeps working."""
    import sqlite3

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with sqlite3.connect(data_dir / "reports.db") as conn:
        conn.execute(
            "CREATE TABLE reports (id TEXT PRIMARY KEY, client_name TEXT NOT NULL, technician TEXT, notes TEXT,"
            " hostname TEXT, username TEXT, serial_number TEXT, manufacturer TEXT, model TEXT, os_name TEXT,"
            " cpu TEXT, ram_gb REAL, disk_overall_status TEXT NOT NULL DEFAULT 'UNKNOWN', disks_json TEXT,"
            " metadata_json TEXT, zip_filename TEXT NOT NULL, zip_path TEXT NOT NULL,"
            " zip_size_bytes INTEGER NOT NULL, collected_at TEXT, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO reports (id, client_name, disk_overall_status, zip_filename, zip_path, zip_size_bytes,"
            " created_at) VALUES ('old', 'Legacy', 'OK', 'a.zip', 'x/a.zip', 1, '2026-11-18T00:00:00+00:00')"
        )
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    load_app()
    import core

    core.init_db()
    with sqlite3.connect(data_dir / "reports.db") as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
    assert "full_json" in cols


# --------------------------------------------------------------------------- passwords / CLI

def test_password_hash_roundtrip(app_module: ModuleType) -> None:
    import core

    encoded = core.hash_password("una-clave-larga", n=2**10)
    assert "$" not in encoded  # safe to paste in a docker compose .env
    assert core.verify_password("una-clave-larga", encoded)
    assert not core.verify_password("otra", encoded)
    assert not core.verify_password("x", "basura")


def test_hash_password_cli() -> None:
    server_dir = Path(__file__).parent
    out = subprocess.run(
        [sys.executable, "app.py", "hash-password"], input="clave-de-prueba-1\n",
        capture_output=True, text=True, cwd=server_dir, check=True,
    )
    assert out.stdout.startswith("scrypt:")
    short = subprocess.run(
        [sys.executable, "app.py", "hash-password"], input="corta\n", capture_output=True, text=True, cwd=server_dir
    )
    assert short.returncode == 2


def test_password_change_invalidates_sessions(viewer: TestClient, app_module: ModuleType) -> None:
    assert viewer.get("/api/v1/auth/me").status_code == 200
    import core

    core.settings.admin_password_hash = core.hash_password("nueva-clave-segura", n=2**10)
    assert viewer.get("/api/v1/auth/me").status_code == 401
