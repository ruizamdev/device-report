# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y el proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).
Las versiones del servidor (API + panel) y del cliente Windows se publican juntas con una etiqueta `vX.Y.Z`.

## [2.2.0] - 2026-11-20

### Añadido

- **Panel web** para consultar los reportes (`server/web.py`, Jinja2 + HTMX):
  - Inicio con totales, semáforo de salud de discos, reportes por mes, alertas recientes y clientes principales.
  - Listado con búsqueda (cliente, equipo, serie, usuario, modelo, técnico), filtro por estado de discos y por fechas, y paginación.
  - Detalle del reporte en pestañas: Resumen, Discos, Hardware, Sistema, Red, Software (con filtro) y Reporte original
    (el `reporte.html` del ZIP en un iframe aislado), con descarga del ZIP.
  - Historial por equipo (`/equipos/<serie>`) con la evolución de temperatura, desgaste, sectores y horas de cada disco.
  - Modo claro/oscuro y diseño adaptable a móvil.
- Cabeceras de seguridad en el panel: CSP estricta (sin scripts ni estilos en línea), `X-Frame-Options: DENY`, `no-store`.

### Cambiado

- Backend reorganizado en `core.py` (configuración, autenticación, base de datos y consultas), `app.py` (API) y `web.py` (panel).
- El título de la ventana del cliente muestra la versión real del ejecutable.

## [2.1.0] - 2026-11-20

### Añadido

- **Inicio de sesión** del panel con usuario y contraseña (hash scrypt, cookie `HttpOnly` + `SameSite=Strict`
  firmada, bloqueo tras 5 intentos fallidos por IP). Cambiar la contraseña invalida las sesiones abiertas.
- `deploy/set-admin-password.sh` para fijar el usuario del panel en el VPS sin escribir la contraseña en disco.
- El cliente incluye `report.json` (todos los datos recolectados, `schema_version` 1) dentro del ZIP;
  el servidor lo indexa al recibirlo.
- Endpoints: `/api/v1/auth/*`, `/api/v1/reports/{id}/html`, `/api/v1/devices/{serial}/reports`, `/api/v1/stats`;
  filtros `q`, `serial`, `date_from` y `date_to` en el listado.

### Cambiado

- **Incompatible:** el token Bearer que lleva `DeviceReport.exe` ahora **solo permite subir** reportes.
  La lectura requiere sesión.
- Migración automática de la base de datos (columna `full_json`); los reportes anteriores siguen disponibles
  con su resumen, discos y HTML original.

## [2.0.0] - 2026-11-20

### Añadido

- Cliente de escritorio en **C# (.NET 8 WinForms)**, ejecutable único autocontenido con elevación UAC.
- Diagnóstico de salud de discos **S.M.A.R.T.** con `smartctl` (descarga automática opcional) y respaldo por WMI;
  semáforo OK / Advertencia / Crítico, notificación y sonido al terminar.
- **API propia** (FastAPI + SQLite) que recibe los reportes por HTTPS con token Bearer.
- **CI/CD** con GitHub Actions según las reglas del VPS siscom: tests, imagen en
  `ghcr.io/ruizamdev/device-report-api`, despliegue a staging (`dev`) y producción (etiqueta `vX.Y.Z`),
  y release con `DeviceReport.exe`.

### Eliminado

- Script PowerShell y sus módulos, envío a recurso compartido de red y a OneDrive (`AZURE_SETUP.md`).

## [1.0.0] - 2025-01-24

Primera versión en PowerShell: recolección de hardware, usuario, software y red; reportes HTML/XML/TXT
comprimidos en ZIP y enviados a un recurso compartido del taller o a OneDrive.
