"""Tests for the server-rendered web panel."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from test_app import ADMIN_PASSWORD, ADMIN_USER, _upload, _zip_bytes, app_module, client, viewer  # noqa: F401

FULL_REPORT = {
    "schema_version": 1,
    "app_version": "2.1.0.0",
    "client_name": "Empresa Demo",
    "hardware": {
        "manufacturer": "Dell",
        "model": "OptiPlex 7090",
        "serial_number": "SN123456",
        "bios_version": "1.2.3",
        "motherboard": "Dell 0ABC",
        "cpu_name": "Intel Core i7-11700",
        "cpu_cores": 8,
        "cpu_logical_processors": 16,
        "total_ram_gb": 16,
        "ram_modules": [{"slot": "DIMM1", "capacity_gb": 8, "speed_mhz": 3200, "manufacturer": "Kingston", "part_number": "KF-123"}],
        "gpus": ["Intel UHD 750"],
        "volumes": [{"drive_letter": "C:", "label": "Sistema", "file_system": "NTFS", "total_gb": 476.0, "free_gb": 40.5}],
    },
    "disks_health": [
        {"model": "Samsung SSD 980", "serial": "S1DISK", "status": "WARNING", "temperature_c": 58, "power_on_hours": 12000,
         "wear_percent": 12, "reallocated_sectors": 0, "capacity_gb": 500, "protocol": "NVMe", "summary": "Temperatura alta"},
    ],
    "user_os": {"os_name": "Windows 11 Pro", "os_version": "10.0.22631", "os_build": "22631", "architecture": "64 bits",
                "domain_or_workgroup": "WORKGROUP", "uptime": "2d 3h", "last_boot_time": "2026-11-17T10:00:00Z"},
    "software": {
        "installed_programs": [
            {"name": "Google Chrome", "version": "131.0", "publisher": "Google LLC"},
            {"name": "7-Zip", "version": "24.08", "publisher": "Igor Pavlov"},
        ],
        "recent_updates": ["KB5046617"],
        "running_services_count": 120,
        "active_processes_count": 210,
    },
    "network": {
        "adapters": [{"name": "Ethernet", "mac_address": "AA:BB:CC:DD:EE:FF", "ip_addresses": "192.168.1.50", "gateways": "192.168.1.1", "dns_servers": "1.1.1.1"}],
        "wifi_profiles": ["Taller-5G"],
    },
}

HX = {"HX-Request": "true"}


def _full_upload(c: TestClient, **meta) -> str:
    return _upload(c, zip_bytes=_zip_bytes(full_report=FULL_REPORT), **meta)["id"]


# --------------------------------------------------------------------------- auth

def test_pages_redirect_to_login(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    resp = client.get("/reportes/abc?tab=red", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Freportes%2Fabc%3Ftab%3Dred"


def test_htmx_request_without_session_uses_hx_redirect(client: TestClient) -> None:
    resp = client.get("/reportes", headers=HX, follow_redirects=False)
    assert resp.status_code == 204
    assert resp.headers["HX-Redirect"].startswith("/login")


def test_login_form(client: TestClient) -> None:
    page = client.get("/login")
    assert page.status_code == 200 and 'name="password"' in page.text

    bad = client.post("/login", data={"username": ADMIN_USER, "password": "mala", "next": "/"})
    assert bad.status_code == 401 and "incorrectos" in bad.text

    ok = client.post("/login", data={"username": ADMIN_USER, "password": ADMIN_PASSWORD, "next": "/reportes"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/reportes"
    assert client.get("/reportes").status_code == 200

    # Already logged in: /login bounces to the app.
    assert client.get("/login", follow_redirects=False).status_code == 303


def test_login_rejects_open_redirect(client: TestClient) -> None:
    for target in ("//evil.example", "https://evil.example", "/\\evil.example"):
        resp = client.post("/login", data={"username": ADMIN_USER, "password": ADMIN_PASSWORD, "next": target}, follow_redirects=False)
        assert resp.headers["location"] == "/"


def test_logout(viewer: TestClient) -> None:
    resp = viewer.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert viewer.get("/", follow_redirects=False).status_code == 303


# --------------------------------------------------------------------------- pages

def test_security_headers_on_pages(viewer: TestClient) -> None:
    resp = viewer.get("/")
    csp = resp.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["cache-control"] == "private, no-store"
    # Pages must not contain inline scripts or style attributes (blocked by CSP).
    assert "<script>" not in resp.text and ' style="' not in resp.text


def test_dashboard_empty_and_with_data(client: TestClient, viewer: TestClient) -> None:
    assert "Todavía no hay reportes" in viewer.get("/").text
    _upload(client, client_name="Acme", disk_overall_status="CRITICAL")
    _upload(client, client_name="Beta", disk_overall_status="OK")
    html = viewer.get("/").text
    assert "Acme" in html and "Beta" in html
    assert "Discos críticos" in html
    assert "<rect" in html  # chart rendered


def test_reports_list_filters_and_partial(client: TestClient, viewer: TestClient) -> None:
    _upload(client, client_name="Acme", hostname="ACME-PC", disk_overall_status="CRITICAL")
    _upload(client, client_name="Beta", hostname="BETA-PC", disk_overall_status="OK")

    full = viewer.get("/reportes?q=acme")
    assert full.status_code == 200 and "<html" in full.text
    assert "ACME-PC" in full.text and "BETA-PC" not in full.text

    partial = viewer.get("/reportes?disk_status=OK", headers={**HX, "HX-Target": "results"})
    assert "<html" not in partial.text
    assert "BETA-PC" in partial.text and "ACME-PC" not in partial.text

    bad = viewer.get("/reportes?date_from=nope")
    assert bad.status_code == 200 and "Fecha inválida" in bad.text


def test_reports_pagination(client: TestClient, viewer: TestClient) -> None:
    for i in range(27):
        _upload(client, client_name=f"Cliente {i:02d}")
    page1 = viewer.get("/reportes").text
    assert "Página 1 de 2" in page1
    page2 = viewer.get("/reportes?page=2").text
    assert "Página 2 de 2" in page2
    assert page2.count('class="row-link"') == 2


def test_report_detail_tabs(client: TestClient, viewer: TestClient) -> None:
    rid = _full_upload(client)
    expectations = {
        "resumen": ["OptiPlex 7090", "SN123456"],
        "discos": ["Samsung SSD 980", "58 °C"],
        "hardware": ["Intel Core i7-11700", "KF-123", "C:"],
        "sistema": ["22631", "WORKGROUP", "KB5046617"],
        "red": ["AA:BB:CC:DD:EE:FF", "Taller-5G"],
        "software": ["Google Chrome", "7-Zip"],
        "original": [f"/api/v1/reports/{rid}/html", 'sandbox=""'],
    }
    for tab, needles in expectations.items():
        resp = viewer.get(f"/reportes/{rid}?tab={tab}")
        assert resp.status_code == 200, tab
        for needle in needles:
            assert needle in resp.text, (tab, needle)

    partial = viewer.get(f"/reportes/{rid}?tab=red", headers={**HX, "HX-Target": "tab-content"})
    assert "<html" not in partial.text and "AA:BB:CC:DD:EE:FF" in partial.text
    assert re.search(r'class="active"[^>]*>Red<|aria-selected="true" class="active">Red<', partial.text)


def test_legacy_report_detail(client: TestClient, viewer: TestClient) -> None:
    rid = _upload(client)["id"]  # no report.json
    html = viewer.get(f"/reportes/{rid}").text
    assert "anterior a la versión 2.1" in html
    assert "Samsung SSD 980" in html  # disks from metadata
    assert "Sección no disponible" in viewer.get(f"/reportes/{rid}?tab=hardware").text


def test_software_filter_partial(client: TestClient, viewer: TestClient) -> None:
    rid = _full_upload(client)
    resp = viewer.get(f"/reportes/{rid}/software?q=zip", headers=HX)
    assert "7-Zip" in resp.text and "Chrome" not in resp.text
    none = viewer.get(f"/reportes/{rid}/software?q=nada", headers=HX)
    assert "Ningún programa coincide" in none.text


def test_device_page_trends(client: TestClient, viewer: TestClient) -> None:
    _upload(client, serial_number="DEV1", disks=[{"model": "WD Blue", "serial": "W1", "status": "OK", "temperature_c": 35, "reallocated_sectors": 0}])
    _upload(client, serial_number="DEV1", disks=[{"model": "WD Blue", "serial": "W1", "status": "WARNING", "temperature_c": 41, "reallocated_sectors": 8}])
    html = viewer.get("/equipos/DEV1").text
    assert "WD Blue" in html and "<polyline" in html
    assert "Sectores reasignados" in html and "+8" in html


def test_not_found_pages(viewer: TestClient) -> None:
    assert viewer.get("/reportes/no-existe").status_code == 404
    assert viewer.get("/equipos/no-existe").status_code == 404
    assert viewer.get("/reportes/no-existe/software", headers=HX).status_code == 404


def test_user_content_is_escaped(client: TestClient, viewer: TestClient) -> None:
    rid = _upload(client, client_name="<script>alert(1)</script>", notes='"><img src=x onerror=alert(1)>')["id"]
    for path in ("/", "/reportes", f"/reportes/{rid}"):
        html = viewer.get(path).text
        assert "<script>alert(1)</script>" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html


def test_static_assets(client: TestClient) -> None:
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/htmx.min.js").status_code == 200


def test_month_chart_always_shows_twelve_months(viewer: TestClient, client: TestClient) -> None:
    import web

    _upload(client)
    filled = web.last_months([{"month": "1999-01", "total": 9, "ok": 9, "warning": 0, "critical": 0, "unknown": 0}])
    assert len(filled) == 12 and all(m["month"] != "1999-01" for m in filled)
    assert viewer.get("/").text.count('class="bar-label"') == 12
