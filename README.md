# Device Report — Siscom

Utilidad gráfica de escritorio para Windows (.NET 8 WinForms) orientada a diagnóstico técnico de equipos en taller, con análisis de salud de discos S.M.A.R.T. (`smartmontools`) y envío centralizado por HTTPS a un backend FastAPI + SQLite en `siscom_vps`.

Guía para técnicos: [QUICK_START.md](QUICK_START.md) · Historial de cambios: [CHANGELOG.md](CHANGELOG.md)

## Características
- **GUI nativa en C# (.NET 8 WinForms)** compilada como un único ejecutable autocontenido (`dist/DeviceReport.exe`) con elevación UAC.
- **Recolección completa**: Hardware (CPU, RAM, placa, BIOS, GPU, volúmenes), Usuario/SO, Software instalado, Red/Wi-Fi.
- **Salud de discos (S.M.A.R.T.)**: Integra `smartctl.exe` (`--scan --json` y `-a --json`) con descarga automática opcional y respaldo WMI.
- **Alertas locales al finalizar**: Semáforo visual (`OK` / `WARNING` / `CRITICAL`), notificación de Windows y sonido del sistema.
- **Backend centralizado**: API REST en FastAPI + SQLite (`server/`) detrás de Traefik con TLS (`reportes.sismanager.cloud`).
- **Panel web** para consultar reportes, alertas e historial por equipo (ver abajo).

## Compilación del cliente Windows

Requiere **.NET 8 SDK** (puede compilarse desde Windows o de forma cruzada desde Linux):

```bash
# En Linux / macOS
./build.sh
```

```cmd
:: En Windows
build.cmd
```

El ejecutable se genera en `dist/DeviceReport.exe`. Coloca junto a él un archivo `config.json` basado en `config.example.json` con tu `ApiToken`.

## Panel web

`https://reportes.sismanager.cloud` (producción) y `https://test-reportes.sismanager.cloud` (staging).
Páginas renderizadas en el servidor (FastAPI + Jinja2 + HTMX, sin build de frontend):

- **Inicio**: totales, semáforo de discos, reportes por mes, alertas recientes y clientes principales.
- **Reportes**: búsqueda (cliente, equipo, serie, usuario, modelo, técnico), filtro por estado y fechas, paginación.
- **Detalle**: pestañas Resumen, Discos, Hardware, Sistema, Red, Software (con filtro) y Reporte original
  (el `reporte.html` del ZIP en un iframe aislado), más descarga del ZIP.
- **Equipo** (`/equipos/<serie>`): historial por número de serie y evolución de las métricas S.M.A.R.T.

Código en `server/web.py`, `server/templates/` y `server/static/` (HTMX 2.0.4 incluido en el repo; CSP estricta,
sin scripts ni estilos en línea).

## Backend (`server/`)

Desarrollo local:

```bash
cd server
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
DATA_DIR=./data API_TOKEN=dev COOKIE_SECURE=false SESSION_SECRET=$(openssl rand -hex 32) \
  ADMIN_USER=admin ADMIN_PASSWORD_HASH=$(echo 'clave-local-123' | python app.py hash-password) \
  uvicorn app:app --reload
```

## Flujo de ramas y despliegue

El despliegue sigue las reglas del VPS siscom (`/srv/agents/AGENTS.md`). **Nunca se despliega a mano.**
Las imágenes las construye GitHub Actions (`.github/workflows/deploy.yml`) y se publican en
`ghcr.io/ruizamdev/device-report-api:<sha12>`.

| Rama / evento | Resultado |
| --- | --- |
| PR a `dev` o `main` | Tests del backend, build del cliente y de la imagen (sin publicar) |
| push a `dev` | Despliegue a **staging** → `https://test-reportes.sismanager.cloud` (`/srv/apps/device-reports-dev`) |
| tag `vX.Y.Z` sobre `main` | Despliegue a **producción** → `https://reportes.sismanager.cloud` (`/srv/apps/device-reports`) + GitHub Release con `DeviceReport.exe` |

| Paso | Comandos |
| --- | --- |
| Crear rama | `git switch dev && git pull && git switch -c feat-<nombre>` |
| Subir a staging | `git switch dev && git merge --squash feat-<nombre> && git commit && git push origin dev` |
| Publicar en producción | `git switch main && git pull && git merge --squash dev && git commit && git push origin main && git tag vX.Y.Z && git push origin vX.Y.Z` |
| Sincronizar `dev` | `git switch dev && git merge origin/main && git push origin dev` |

- `deploy/` contiene el `docker-compose.yml`, `deploy.sh` y `.env.example` que CI copia al VPS.
  Los secretos viven solo en `/srv/apps/<app>/.env` del VPS.
- Rollback: `cd /srv/apps/<app> && IMAGE_TAG=<tag anterior> ./deploy.sh` (historial en `.deploy-history`),
  o re-ejecutar el workflow de un commit anterior.

### Endpoints principales

**Subida** (Bearer `API_TOKEN`, el que lleva `DeviceReport.exe`; este token **no** permite leer):
- `POST /api/v1/reports` — `.zip` + `metadata` JSON. Si el ZIP trae `report.json` (cliente ≥ 2.1.0) se indexa el reporte completo.

**Panel / lectura** (cookie de sesión vía `POST /api/v1/auth/login`):
- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`
- `GET /api/v1/reports` — filtros `q`, `client`, `hostname`, `serial`, `disk_status`, `date_from`, `date_to`, paginación `limit`/`offset`
- `GET /api/v1/reports/{id}` — detalle con `report` completo (`null` en reportes de clientes < 2.1.0)
- `GET /api/v1/reports/{id}/html` — `reporte.html` del ZIP servido con CSP `sandbox`
- `GET /api/v1/reports/{id}/download` — ZIP original
- `GET /api/v1/devices/{serial}/reports` — historial de un equipo
- `GET /api/v1/stats` — totales, estado de discos, por mes y clientes principales
- `GET /health` — público

**Usuario del panel:** en el VPS, `ssh -t deploy@<vps> /srv/apps/<app>/set-admin-password.sh [usuario]`.
Cambiar la contraseña invalida las sesiones abiertas.
