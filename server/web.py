"""Server-rendered web panel (Jinja2 + HTMX). All pages require a session except /login."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from jinja2 import Undefined

import core

BASE_DIR = Path(__file__).resolve().parent
PAGE_SIZE = 25

PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "frame-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'; object-src 'none'"
)

STATUS_LABELS = {"OK": "OK", "WARNING": "Advertencia", "CRITICAL": "Crítico", "UNKNOWN": "Sin datos"}
STATUS_CLASSES = {"OK": "ok", "WARNING": "warning", "CRITICAL": "critical", "UNKNOWN": "unknown"}

TABS = [
    ("resumen", "Resumen"),
    ("discos", "Discos"),
    ("hardware", "Hardware"),
    ("sistema", "Sistema"),
    ("red", "Red"),
    ("software", "Software"),
    ("original", "Reporte original"),
]
FULL_REPORT_TABS = {"hardware", "sistema", "red", "software"}

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --------------------------------------------------------------------------- formatting helpers

def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(core.settings.display_tz)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _missing(value: Any) -> bool:
    return value is None or value == "" or isinstance(value, Undefined)


def _parse_dt(value: Any) -> Optional[datetime]:
    if _missing(value):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_tz())


def fmt_dt(value: Any, fmt: str = "%d/%m/%Y %H:%M") -> str:
    dt = _parse_dt(value)
    return dt.strftime(fmt) if dt else "—"


def fmt_ago(value: Any) -> str:
    dt = _parse_dt(value)
    if not dt:
        return ""
    seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    if seconds < 60:
        return "hace un momento"
    for size, singular, plural in ((86400, "día", "días"), (3600, "hora", "horas"), (60, "minuto", "minutos")):
        if seconds >= size:
            n = int(seconds // size)
            return f"hace {n} {singular if n == 1 else plural}"
    return ""


def fmt_num(value: Any, decimals: int = 0) -> str:
    if _missing(value):
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:,.{decimals}f}"
    return text.replace(",", " ")


def fmt_bytes(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def status_label(value: Any) -> str:
    key = "UNKNOWN" if _missing(value) else str(value).upper()
    return STATUS_LABELS.get(key, str(value))


def status_class(value: Any) -> str:
    key = "UNKNOWN" if _missing(value) else str(value).upper()
    return STATUS_CLASSES.get(key, "unknown")


templates.env.filters.update(
    dt=fmt_dt, ago=fmt_ago, num=fmt_num, bytes=fmt_bytes, status_label=status_label, status_class=status_class,
    urlpath=lambda v: quote(str(v or ""), safe=""),
)
templates.env.globals.update(app_version=core.APP_VERSION, STATUS_LABELS=STATUS_LABELS)


# --------------------------------------------------------------------------- charts (pure SVG data)

def month_bars(by_month: list[dict[str, Any]], *, height: int = 140) -> dict[str, Any]:
    """Stacked bars per month; returns rect geometry so templates only emit SVG attributes."""
    peak = max((m["total"] for m in by_month), default=0) or 1
    bar_w, gap = 28, 14
    bars = []
    for i, m in enumerate(by_month):
        x = i * (bar_w + gap)
        y = height
        segments = []
        for key, cls in (("ok", "ok"), ("warning", "warning"), ("critical", "critical"), ("unknown", "unknown")):
            value = m.get(key) or 0
            if not value:
                continue
            h = value / peak * height
            y -= h
            segments.append({"cls": cls, "y": round(y, 2), "h": round(h, 2), "value": value, "label": STATUS_LABELS[key.upper()]})
        try:
            label = datetime.strptime(m["month"], "%Y-%m").strftime("%m/%y")
        except (TypeError, ValueError):
            label = str(m.get("month"))
        bars.append({"x": x, "w": bar_w, "segments": segments, "label": label, "total": m["total"], "month": m["month"]})
    width = max(len(bars) * (bar_w + gap) - gap, bar_w)
    return {"bars": bars, "width": width, "height": height, "peak": peak}


def last_months(by_month: list[dict[str, Any]], count: int = 12) -> list[dict[str, Any]]:
    """Fill gaps so the chart always shows the last `count` months (in display timezone)."""
    known = {m["month"]: m for m in by_month}
    now = datetime.now(_tz())
    year, month = now.year, now.month
    keys = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    empty = {"total": 0, "ok": 0, "warning": 0, "critical": 0, "unknown": 0}
    return [known.get(k, {"month": k, **empty}) for k in reversed(keys)]


def status_strip(by_status: dict[str, int]) -> list[dict[str, Any]]:
    total = sum(by_status.values()) or 1
    x = 0.0
    parts = []
    for key in core.DISK_STATUSES:
        value = by_status.get(key, 0)
        if not value:
            continue
        w = value / total * 100
        parts.append({"cls": STATUS_CLASSES[key], "x": round(x, 3), "w": round(w, 3), "value": value, "label": STATUS_LABELS[key]})
        x += w
    return parts


def sparkline(values: list[Optional[float]], *, width: int = 220, height: int = 48, pad: int = 4) -> dict[str, Any]:
    """Polyline points for a series (None values are skipped)."""
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if not points:
        return {"points": "", "dots": [], "width": width, "height": height}
    lo = min(v for _, v in points)
    hi = max(v for _, v in points)
    span = (hi - lo) or 1
    n = max(len(values) - 1, 1)
    coords = []
    for i, v in points:
        x = pad + (i / n) * (width - 2 * pad) if len(values) > 1 else width / 2
        y = height - pad - ((v - lo) / span) * (height - 2 * pad) if hi != lo else height / 2
        coords.append((round(x, 2), round(y, 2), v))
    return {
        "points": " ".join(f"{x},{y}" for x, y, _ in coords),
        "dots": [{"x": x, "y": y, "v": v} for x, y, v in coords],
        "width": width,
        "height": height,
    }


DISK_METRICS = [
    ("temperature_c", "Temperatura", "°C"),
    ("wear_percent", "Desgaste", "%"),
    ("reallocated_sectors", "Sectores reasignados", ""),
    ("pending_sectors", "Sectores pendientes", ""),
    ("power_on_hours", "Horas encendido", "h"),
]


def disk_trends(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group disk metrics across reports by disk serial (or model) and build sparklines."""
    keys: list[str] = []
    info: dict[str, dict[str, Any]] = {}
    for item in history:
        for disk in item["disks"]:
            key = str(disk.get("serial") or disk.get("model") or disk.get("device") or "disco")
            if key not in info:
                keys.append(key)
                info[key] = {"model": disk.get("model") or key, "serial": disk.get("serial") or "", "capacity_gb": disk.get("capacity_gb")}
    trends = []
    for key in keys:
        per_report = []
        for item in history:
            match = next(
                (d for d in item["disks"] if str(d.get("serial") or d.get("model") or d.get("device") or "disco") == key),
                None,
            )
            per_report.append(match)
        metrics = []
        for field, label, unit in DISK_METRICS:
            values = [_to_float(d.get(field)) if d else None for d in per_report]
            present = [v for v in values if v is not None]
            if not present:
                continue
            metrics.append({
                "label": label,
                "unit": unit,
                "first": present[0],
                "last": present[-1],
                "delta": present[-1] - present[0],
                "spark": sparkline(values),
            })
        statuses = [(d or {}).get("status") for d in per_report]
        trends.append({**info[key], "metrics": metrics, "statuses": statuses, "last_status": next((s for s in reversed(statuses) if s), "UNKNOWN")})
    return trends


def _to_float(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# --------------------------------------------------------------------------- auth helpers

def current_user(request: Request) -> Optional[str]:
    return core.read_session_token(request.cookies.get(core.SESSION_COOKIE))


def _safe_next(value: Optional[str]) -> str:
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def login_redirect(request: Request) -> Response:
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    url = "/login" + (f"?{urlencode({'next': target})}" if target != "/" else "")
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


def is_partial(request: Request, target: str) -> bool:
    return request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == target


def render(request: Request, name: str, context: dict[str, Any], status_code: int = 200) -> HTMLResponse:
    response = templates.TemplateResponse(request, name, context, status_code=status_code)
    response.headers["Cache-Control"] = "private, no-store"
    return response


# --------------------------------------------------------------------------- routes

@router.get("/login")
def login_page(request: Request, next: Optional[str] = None):
    if current_user(request):
        return RedirectResponse(_safe_next(next), status_code=303)
    return render(request, "login.html", {"next": _safe_next(next), "error": None, "panel_enabled": core.settings.panel_enabled})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    ip = request.client.host if request.client else "unknown"
    try:
        token = core.authenticate(username, password, ip)
    except core.AuthError as exc:
        return render(
            request,
            "login.html",
            {"next": _safe_next(next), "error": exc.detail, "username": username, "panel_enabled": core.settings.panel_enabled},
            status_code=exc.status_code,
        )
    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(core.SESSION_COOKIE, token, max_age=core.settings.session_ttl, **core.session_cookie_kwargs())
    return response


@router.post("/logout")
def logout_submit():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(core.SESSION_COOKIE, **core.session_cookie_kwargs())
    return response


@router.get("/")
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return login_redirect(request)
    stats = core.compute_stats(months=12, top=8)
    recent = core.query_reports(limit=8)["items"]
    alerts = core.query_reports(disk_status="CRITICAL", limit=5)["items"] + core.query_reports(disk_status="WARNING", limit=5)["items"]
    alerts.sort(key=lambda r: r["created_at"], reverse=True)
    return render(request, "dashboard.html", {
        "user": user,
        "nav": "inicio",
        "stats": stats,
        "chart": month_bars(last_months(stats["by_month"])),
        "strip": status_strip(stats["by_disk_status"]),
        "recent": recent,
        "alerts": alerts[:6],
    })


@router.get("/reportes")
def reports_page(
    request: Request,
    q: str = "",
    disk_status: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = Query(default=1, ge=1),
):
    user = current_user(request)
    if not user:
        return login_redirect(request)
    filters = {"q": q.strip(), "disk_status": disk_status.strip().upper(), "date_from": date_from.strip(), "date_to": date_to.strip()}
    if filters["disk_status"] not in core.DISK_STATUSES:
        filters["disk_status"] = ""
    error = None
    try:
        result = core.query_reports(**filters, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
    except core.QueryError as exc:
        error = str(exc)
        result = {"total": 0, "items": []}
    pages = max(math.ceil(result["total"] / PAGE_SIZE), 1)
    active = {k: v for k, v in filters.items() if v}
    context = {
        "user": user,
        "nav": "reportes",
        "filters": filters,
        "result": result,
        "page": page,
        "pages": pages,
        "error": error,
        "qs": lambda **extra: urlencode({**active, **{k: v for k, v in extra.items() if v}}),
    }
    template = "partials/report_table.html" if is_partial(request, "results") else "reports.html"
    return render(request, template, context)


@router.get("/reportes/{report_id}")
def report_detail(request: Request, report_id: str, tab: str = "resumen"):
    user = current_user(request)
    if not user:
        return login_redirect(request)
    data = core.fetch_report(report_id)
    if not data:
        return render(request, "not_found.html", {"user": user, "nav": "reportes", "message": "El reporte no existe."}, status_code=404)
    valid_tabs = {key for key, _ in TABS}
    tab = tab if tab in valid_tabs else "resumen"
    report = data.get("report") or {}
    disks = report.get("disks_health") or data.get("disks") or []
    software = ((report.get("software") or {}).get("installed_programs")) or []
    context = {
        "user": user,
        "nav": "reportes",
        "r": data,
        "full": report,
        "disks": disks,
        "tabs": TABS,
        "tab": tab,
        "needs_full": tab in FULL_REPORT_TABS and not data["has_full_report"],
        "software": software,
        "sw_q": "",
        "history_count": len(core.fetch_device_history(data["serial_number"])) if data.get("serial_number") else 0,
    }
    template = "partials/report_tab.html" if is_partial(request, "tab-content") else "report_detail.html"
    return render(request, template, context)


@router.get("/reportes/{report_id}/software")
def report_software(request: Request, report_id: str, q: str = ""):
    user = current_user(request)
    if not user:
        return login_redirect(request)
    data = core.fetch_report(report_id)
    if not data:
        return Response(status_code=404)
    programs = (((data.get("report") or {}).get("software") or {}).get("installed_programs")) or []
    needle = q.strip().lower()
    if needle:
        programs = [
            p for p in programs
            if needle in f"{p.get('name', '')} {p.get('publisher', '')} {p.get('version', '')}".lower()
        ]
    return render(request, "partials/software_rows.html", {"software": programs, "sw_q": q})


@router.get("/equipos/{serial}")
def device_page(request: Request, serial: str):
    user = current_user(request)
    if not user:
        return login_redirect(request)
    history = core.fetch_device_history(serial)
    if not history:
        return render(request, "not_found.html", {"user": user, "nav": "reportes", "message": "No hay reportes para ese número de serie."}, status_code=404)
    latest = core.fetch_report(history[-1]["id"]) or {}
    return render(request, "device.html", {
        "user": user,
        "nav": "reportes",
        "serial": serial,
        "history": list(reversed(history)),
        "latest": latest,
        "trends": disk_trends(history),
        "dates": [fmt_dt(h["created_at"], "%d/%m/%y") for h in history],
    })
