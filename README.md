# 🖥️ Device Report

Sistema automatizado de recolección y envío de información de dispositivos para soporte técnico IT.

## 📋 Descripción

**Device Report** es una herramienta desarrollada en PowerShell que recopila información detallada del hardware, software, usuario y red de un equipo Windows, genera reportes en múltiples formatos (HTML, XML, TXT), los comprime y los envía automáticamente:

- **En la red del taller**: Al recurso compartido de red
- **Fuera del taller**: A OneDrive usando Microsoft Graph API

## ✨ Características

- ✅ **Recolección completa de información**:
  - Hardware (CPU, RAM, discos, placa base, BIOS, tarjeta de video)
  - Usuario y sistema operativo
  - Software instalado
  - Actualizaciones de Windows
  - Servicios en ejecución
  - Procesos activos
  - Configuración de red completa
  - Perfiles WiFi

- ✅ **Reportes en múltiples formatos**:
  - HTML (con diseño profesional y responsive)
  - XML (para procesamiento automatizado)
  - TXT (para lectura rápida)

- ✅ **Envío automático inteligente**:
  - Detecta si está en la red del taller
  - Envía a recurso compartido de red (en taller)
  - Envía a OneDrive (fuera del taller)

- ✅ **Arquitectura modular**:
  - Cada funcionalidad en su propio módulo
  - Fácil de mantener y extender
  - Código limpio y documentado

- ✅ **Compresión automática**:
  - Todos los reportes comprimidos en un ZIP
  - Nomenclatura: `Cliente_Usuario-Equipo_Timestamp.zip`

## 📁 Estructura del Proyecto

```
device-report/
├── DeviceReport.ps1              # Script principal
├── config.json                   # Archivo de configuración
├── README.md                     # Este archivo
├── AZURE_SETUP.md               # Guía de configuración de Azure AD
└── modules/                     # Módulos del sistema
    ├── Get-HardwareInfo.ps1     # Recolección de hardware
    ├── Get-UserInfo.ps1         # Recolección de usuario y SO
    ├── Get-SoftwareInfo.ps1     # Recolección de software
    ├── Get-NetworkInfo.ps1      # Recolección de red
    ├── New-Reports.ps1          # Generación de reportes
    ├── Compress-Reports.ps1     # Compresión de reportes
    ├── Test-WorkshopNetwork.ps1 # Detección de red del taller
    ├── Send-ToNetworkShare.ps1  # Envío a recurso compartido
    └── Send-ToOneDrive.ps1      # Envío a OneDrive vía Graph API
```

## 🚀 Instalación

### Requisitos

- Windows 10/11 o Windows Server 2016+
- PowerShell 5.1 o superior
- Conexión a Internet (para envío a OneDrive)
- Permisos de administrador (recomendado para recolección completa)

### Pasos

1. **Descargar o clonar el proyecto**:
   ```powershell
   git clone https://github.com/tuusuario/device-report.git
   cd device-report
   ```

2. **Configurar config.json**:
   - Edita `config.json` con tus parámetros
   - Configura credenciales del recurso compartido de red
   - Configura Azure AD para OneDrive (ver AZURE_SETUP.md)

3. **Configurar Azure AD** (para OneDrive):
   - Sigue la guía en [AZURE_SETUP.md](AZURE_SETUP.md)
   - Obtén tu Client ID y Client Secret
   - Actualiza `config.json` con estos valores

## 🎯 Uso

### Ejecución Interactiva

```powershell
.\DeviceReport.ps1
```

El script te pedirá el nombre del cliente.

### Ejecución con Parámetro

```powershell
.\DeviceReport.ps1 -ClientName "Juan Perez"
```

### Ejecución como Ejecutable

Después de empaquetar como .exe:

```cmd
DeviceReport.exe
```

## ⚙️ Configuración

### config.json

```json
{
  "WorkshopNetwork": {
    "DetectionIP": "192.168.1.85",      // IP del servidor del taller
    "PingTimeout": 1000,
    "PingCount": 2
  },
  "NetworkShare": {
    "Path": "\\\\192.168.1.85\\reportes",  // Ruta del recurso compartido
    "Username": "usuario",                  // Usuario del recurso compartido
    "Password": "contraseña",               // Contraseña del recurso compartido
    "RequiresAuth": true
  },
  "OneDrive": {
    "TenantId": "common",                   // "common" para cuentas personales
    "ClientId": "tu-client-id",             // Tu Client ID de Azure AD
    "ClientSecret": "tu-client-secret",     // Tu Client Secret de Azure AD
    "UploadFolder": "DeviceReports",        // Carpeta en OneDrive
    "RedirectUri": "http://localhost"
  },
  "Reports": {
    "TempFolder": "$env:TEMP\\DeviceReports",  // Carpeta temporal
    "Formats": ["HTML", "XML", "TXT"],         // Formatos de reporte
    "CompressReports": true,
    "CompressionFormat": "ZIP"
  },
  "DataCollection": {
    "Hardware": true,
    "User": true,
    "Software": {
      "InstalledPrograms": true,
      "WindowsUpdates": true,
      "RunningServices": true,
      "ActiveProcesses": true
    },
    "Network": true
  }
}
```

## 📦 Empaquetado como .exe

Para convertir el script en un ejecutable de Windows, puedes usar **PS2EXE**:

### Instalar PS2EXE

```powershell
Install-Module -Name ps2exe -Scope CurrentUser
```

### Generar el ejecutable

```powershell
Invoke-ps2exe -inputFile "DeviceReport.ps1" -outputFile "DeviceReport.exe" -iconFile "icon.ico" -title "Device Report" -version "1.0.0.0" -company "ArtmannMX" -product "Device Report" -copyright "© 2025 ArtmannMX" -requireAdmin
```

### Incluir módulos y configuración

El ejecutable buscará los módulos en la carpeta `modules` relativa al ejecutable. Asegúrate de distribuir:

```
DeviceReport/
├── DeviceReport.exe
├── config.json
└── modules/
    └── (todos los módulos .ps1)
```

## 🔧 Desarrollo

### Agregar nuevos módulos

1. Crea un nuevo archivo `.ps1` en `modules/`
2. Define tu función con comentarios de ayuda
3. Exporta la función: `Export-ModuleMember -Function NombreFuncion`
4. Importa el módulo en `DeviceReport.ps1`

### Ejemplo de nuevo módulo

```powershell
# modules/Get-CustomInfo.ps1
function Get-CustomInfo {
    <#
    .SYNOPSIS
    Descripción breve
    #>
    [CmdletBinding()]
    param()

    # Tu código aquí

    return $data
}

Export-ModuleMember -Function Get-CustomInfo
```

## 🐛 Solución de Problemas

### El script no se ejecuta

- Verifica la política de ejecución:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass
  ```

### No se puede conectar al recurso compartido

- Verifica la IP del servidor
- Verifica las credenciales en `config.json`
- Prueba acceder manualmente: `\\192.168.1.85\reportes`

### Error al enviar a OneDrive

- Verifica que el Client ID y Secret estén configurados
- Consulta [AZURE_SETUP.md](AZURE_SETUP.md)
- Verifica los permisos en Azure AD

### Falta información en los reportes

- Ejecuta el script como administrador
- Algunos datos requieren privilegios elevados

## 📝 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

**ArtmannMX**

Basado en el proyecto original **DataGath 3.0**

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📞 Soporte

Si tienes problemas o preguntas:

1. Revisa la documentación
2. Consulta [AZURE_SETUP.md](AZURE_SETUP.md) para configuración de OneDrive
3. Abre un issue en GitHub

---

**Device Report** - Simplificando la recolección de información para soporte técnico IT
