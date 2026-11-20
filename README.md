# Device Report v2.0 — Siscom

Utilidad gráfica de escritorio para Windows (.NET 8 WinForms) orientada a diagnóstico técnico de equipos en taller, con análisis de salud de discos S.M.A.R.T. (`smartmontools`) y envío centralizado por HTTPS a un backend FastAPI + SQLite en `siscom_vps`.

## Características
- **GUI nativa en C# (.NET 8 WinForms)** compilada como un único ejecutable autocontenido (`dist/DeviceReport.exe`) con elevación UAC.
- **Recolección completa**: Hardware (CPU, RAM, placa, BIOS, GPU, volúmenes), Usuario/SO, Software instalado, Red/Wi-Fi.
- **Salud de discos (S.M.A.R.T.)**: Integra `smartctl.exe` (`--scan --json` y `-a --json`) con descarga automática opcional y respaldo WMI.
- **Alertas locales al finalizar**: Semáforo visual (`OK` / `WARNING` / `CRITICAL`), notificación de Windows y sonido del sistema.
- **Backend centralizado**: API REST en FastAPI + SQLite (`server/`) detrás de Traefik con TLS (`reportes.sismanager.cloud`).

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

## Backend (`server/`)

Desarrollo local:

```bash
cd server
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
DATA_DIR=./data API_TOKEN=dev uvicorn app:app --reload
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
- `GET /health` — Estado del servicio
- `POST /api/v1/reports` — Subida de `.zip` + `metadata` JSON (Bearer Token)
- `GET /api/v1/reports` — Listado filtrable por `client`, `hostname`, `disk_status`
- `GET /api/v1/reports/{id}` — Detalle completo del reporte
- `GET /api/v1/reports/{id}/download` — Descarga del `.zip`
