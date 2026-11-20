# Guía de inicio rápido

Device Report tiene dos partes:

1. **`DeviceReport.exe`**: se ejecuta en el equipo del cliente, recoge el diagnóstico y lo sube al servidor.
2. **Panel web**: consulta los reportes recibidos en <https://reportes.sismanager.cloud>.

## 1. Preparar el ejecutable

**Requisitos del equipo:** Windows 10/11 de 64 bits. No hace falta instalar .NET, porque el ejecutable lo incluye.

1. Descarga `DeviceReport.exe` y `config.example.json` del
   [último release](https://github.com/ruizamdev/device-report/releases/latest).
2. Junto al `.exe`, crea un `config.json` a partir de `config.example.json` y pon el token de subida en `ApiToken`:

   ```json
   {
     "VpsApi": {
       "EndpointUrl": "https://reportes.sismanager.cloud/api/v1/reports",
       "ApiToken": "TOKEN_DE_SUBIDA",
       "TimeoutSeconds": 60
     },
     "SmartCtl": { "AutoDownload": true, "ExecutablePath": "tools\\smartctl.exe" },
     "DataCollection": { "Hardware": true, "DiskHealth": true, "User": true, "Software": true, "Network": true }
   }
   ```

   Pide el token al administrador. Está en el `.env` del servidor y **no** se guarda en git.
   Si compilas tú mismo con un `config.json` en la raíz del repo, queda incrustado en el `.exe`.
   Un `config.json` junto al ejecutable siempre tiene prioridad.
3. Copia la carpeta (`DeviceReport.exe` + `config.json`) a la memoria USB del taller.

## 2. Generar un reporte

1. Ejecuta `DeviceReport.exe` en el equipo del cliente y acepta el aviso de UAC: necesita privilegios para leer S.M.A.R.T.
2. Escribe el **Cliente** (obligatorio) y, si quieres, el técnico y las notas de la falla.
3. Elige qué recolectar y pulsa **Generar y Enviar Reporte**.
4. Al terminar verás el estado global de los discos (OK / Advertencia / Crítico). El ZIP queda en
   `%TEMP%\DeviceReports` y se sube al servidor. Si no hay internet, usa **Reintentar Envío** cuando vuelva la conexión.

La primera vez, si no encuentra `smartctl.exe`, lo descarga de smartmontools (`SmartCtl.AutoDownload`).
Sin él, usa un diagnóstico de respaldo por WMI con menos detalle.

## 3. Consultar los reportes

Entra a <https://reportes.sismanager.cloud> con el usuario del panel:

- **Inicio**: estado general y alertas recientes.
- **Reportes**: busca por cliente, equipo, número de serie, usuario, modelo o técnico, y filtra por estado y fechas.
- **Detalle**: hardware, discos, sistema, red y software del equipo, además del reporte original y el ZIP.
- **Historial del equipo**: cómo evolucionaron sus discos entre visitas.

Para crear o cambiar el usuario del panel (en el VPS):

```bash
ssh -t deploy@<vps> /srv/apps/device-reports/set-admin-password.sh admin
```

## Problemas comunes

| Síntoma | Qué revisar |
| --- | --- |
| "ApiToken no configurado en config.json" | Falta `config.json` junto al `.exe` o el token sigue con el valor de ejemplo. |
| `HTTP 401` al enviar | El token no coincide con el `API_TOKEN` del servidor (staging y producción usan tokens distintos). |
| `HTTP 413` al enviar | El ZIP supera `MAX_UPLOAD_MB` (50 MB por defecto). |
| Discos en "Sin datos" | El `.exe` no se ejecutó como administrador o el disco no expone S.M.A.R.T. (p. ej. algunas controladoras RAID/USB). |
| El panel dice "no está configurado" | Falta el usuario del panel: ejecuta `set-admin-password.sh` en el VPS. |
| En el detalle solo aparecen Resumen y Discos | El reporte se generó con un cliente anterior a 2.1. Usa la pestaña "Reporte original". |

Para desarrollo, compilación y despliegue, consulta el [README](README.md).
