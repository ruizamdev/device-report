"""Unit and integration tests for Device Report API."""

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("API_TOKEN", "test-secret-token")

    import importlib
    import app as app_module

    importlib.reload(app_module)
    return TestClient(app_module.app)


def _sample_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("reporte.txt", "Device Report Test")
    return buf.getvalue()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/reports",
        files={"file": ("test.zip", _sample_zip_bytes(), "application/zip")},
        data={"metadata": json.dumps({"client_name": "Juan"})},
    )
    assert resp.status_code == 401

    resp_bad = client.post(
        "/api/v1/reports",
        headers={"Authorization": "Bearer wrong"},
        files={"file": ("test.zip", _sample_zip_bytes(), "application/zip")},
        data={"metadata": json.dumps({"client_name": "Juan"})},
    )
    assert resp_bad.status_code == 401


def test_upload_list_get_and_download(client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-secret-token"}
    metadata = {
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

    zip_bytes = _sample_zip_bytes()
    resp = client.post(
        "/api/v1/reports",
        headers=headers,
        files={"file": ("Empresa_Demo.zip", zip_bytes, "application/zip")},
        data={"metadata": json.dumps(metadata)},
    )
    assert resp.status_code == 201
    created = resp.json()
    report_id = created["id"]
    assert created["disk_overall_status"] == "WARNING"

    # List with filter
    list_resp = client.get("/api/v1/reports?disk_status=WARNING", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["id"] == report_id

    # Get details
    detail_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["disks"][0]["model"] == "Samsung SSD 980"

    # Download ZIP
    dl_resp = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content == zip_bytes
