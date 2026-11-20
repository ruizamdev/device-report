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

## Backend en VPS (`server/`)

```bash
cd server
API_TOKEN="tu-token-seguro" docker compose up -d --build
```

### Endpoints principales
- `GET /health` — Estado del servicio
- `POST /api/v1/reports` — Subida de `.zip` + `metadata` JSON (Bearer Token)
- `GET /api/v1/reports` — Listado filtrable por `client`, `hostname`, `disk_status`
- `GET /api/v1/reports/{id}` — Detalle completo del reporte
- `GET /api/v1/reports/{id}/download` — Descarga del `.zip`
