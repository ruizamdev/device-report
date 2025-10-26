# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [1.0.0] - 2025-01-24

### Añadido

- ✨ Primera versión del proyecto Device Report
- 📊 Recolección de información de hardware (CPU, RAM, discos, BIOS, placa base, tarjeta de video)
- 👤 Recolección de información de usuario y sistema operativo
- 💾 Recolección de software instalado, actualizaciones, servicios y procesos
- 🌐 Recolección de información de red completa (adaptadores, IP, rutas, WiFi)
- 📄 Generación de reportes en múltiples formatos (HTML, XML, TXT)
- 🗜️ Compresión automática de reportes en ZIP
- 🔍 Detección automática de red del taller mediante ping
- 📤 Envío automático a recurso compartido de red (en taller)
- ☁️ Envío automático a OneDrive vía Microsoft Graph API (fuera del taller)
- 🧩 Arquitectura modular con funciones separadas
- 📝 Documentación completa (README, AZURE_SETUP)
- ⚙️ Archivo de configuración JSON editable
- 🔨 Script de compilación a ejecutable (.exe)
- 🎨 Interfaz de consola con colores y diseño profesional
- 📋 Reportes HTML con diseño responsive y profesional

### Características Técnicas

- PowerShell 5.1+ compatible
- Sin dependencias externas (solo comandos nativos de Windows)
- Soporte para autenticación en recursos compartidos de red
- Integración con Microsoft Graph API v1.0
- Manejo de errores robusto
- Logs informativos en tiempo real

### Documentación

- README.md con instrucciones completas
- AZURE_SETUP.md con guía paso a paso para configurar Azure AD
- Comentarios de ayuda en todos los módulos
- Ejemplos de uso
- Archivo de configuración de ejemplo (config.example.json)

### Módulos Incluidos

1. `Test-WorkshopNetwork.ps1` - Detección de red del taller
2. `Get-HardwareInfo.ps1` - Recolección de hardware
3. `Get-UserInfo.ps1` - Recolección de usuario
4. `Get-SoftwareInfo.ps1` - Recolección de software
5. `Get-NetworkInfo.ps1` - Recolección de red
6. `New-Reports.ps1` - Generación de reportes
7. `Compress-Reports.ps1` - Compresión de reportes
8. `Send-ToNetworkShare.ps1` - Envío a recurso compartido
9. `Send-ToOneDrive.ps1` - Envío a OneDrive

---

## [Unreleased]

### Planeado

- [ ] Soporte para múltiples idiomas (ES/EN)
- [ ] Interfaz gráfica (GUI) opcional
- [ ] Reportes en formato PDF
- [ ] Integración con otras plataformas cloud (Google Drive, Dropbox)
- [ ] Programación de ejecuciones automáticas
- [ ] Panel web para visualización de reportes
- [ ] Comparación de reportes históricos
- [ ] Alertas automáticas por cambios significativos
- [ ] Soporte para Device Code Flow (cuentas personales OneDrive)
- [ ] Firma digital del ejecutable
- [ ] Auto-actualización del ejecutable

### En Consideración

- Soporte para Linux y macOS
- Base de datos local para histórico de reportes
- Exportación a sistemas de ticketing (ServiceNow, Jira)
- Notificaciones por email al completar el reporte
- Modo offline (guardar localmente cuando no hay conexión)

---

[1.0.0]: https://github.com/artmannmx/device-report/releases/tag/v1.0.0
