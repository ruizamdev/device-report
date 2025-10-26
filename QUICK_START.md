# 🚀 Guía de Inicio Rápido

Esta guía te ayudará a configurar y ejecutar **Device Report** en menos de 5 minutos.

## 📋 Antes de Comenzar

Asegúrate de tener:
- ✅ Windows 10/11 o Windows Server 2016+
- ✅ PowerShell 5.1 o superior
- ✅ Permisos de administrador (recomendado)

## ⚡ Configuración Rápida

### Paso 1: Configurar el archivo de configuración

1. **Copia el archivo de ejemplo**:
   ```powershell
   Copy-Item config.example.json config.json
   ```

2. **Edita `config.json`** con un editor de texto:

   **Configuración MÍNIMA requerida**:
   ```json
   {
     "WorkshopNetwork": {
       "DetectionIP": "192.168.1.85"  // ← IP de tu servidor del taller
     },
     "NetworkShare": {
       "Path": "\\\\192.168.1.85\\reportes",  // ← Ruta del recurso compartido
       "Username": "TU_USUARIO",              // ← Usuario del recurso compartido
       "Password": "TU_CONTRASEÑA"            // ← Contraseña
     }
   }
   ```

   **Para OneDrive** (opcional, solo si no estás en el taller):
   - Sigue la guía completa en [AZURE_SETUP.md](AZURE_SETUP.md)
   - Obtén tu Client ID y Client Secret
   - Actualiza la sección `OneDrive` en `config.json`

### Paso 2: Permitir la ejecución de scripts

Abre PowerShell **como Administrador** y ejecuta:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass
```

### Paso 3: Ejecutar el script

```powershell
.\DeviceReport.ps1
```

O con el nombre del cliente directamente:

```powershell
.\DeviceReport.ps1 -ClientName "Juan Perez"
```

## 🎯 ¿Qué hace el script?

1. ✅ Te pide el nombre del cliente (si no lo proporcionaste)
2. ✅ Detecta si estás en la red del taller (ping a 192.168.1.85)
3. ✅ Recopila información del equipo:
   - Hardware (CPU, RAM, discos, BIOS)
   - Usuario y sistema operativo
   - Software instalado
   - Servicios y procesos
   - Configuración de red completa
4. ✅ Genera reportes en HTML, XML y TXT
5. ✅ Comprime los reportes en un ZIP
6. ✅ Envía automáticamente:
   - **En el taller**: Al recurso compartido `\\192.168.1.85\reportes\[Cliente]\`
   - **Fuera del taller**: A OneDrive (si está configurado)

## 📁 ¿Dónde se guardan los reportes?

### En el taller (red local)
```
\\192.168.1.85\reportes\
└── [Nombre del Cliente]/
    └── [Cliente]_[Usuario]-[Equipo]_[Timestamp].zip
```

### Fuera del taller (OneDrive)
```
OneDrive/
└── DeviceReports/
    └── [Nombre del Cliente]/
        └── [Cliente]_[Usuario]-[Equipo]_[Timestamp].zip
```

## 🔧 Compilar a Ejecutable (Opcional)

Si quieres distribuir el programa como un .exe:

1. **Instalar ps2exe**:
   ```powershell
   Install-Module -Name ps2exe -Scope CurrentUser
   ```

2. **Compilar**:
   ```powershell
   .\Build-Executable.ps1
   ```

3. **Distribuir**: Comparte la carpeta `dist/` que contiene:
   - `DeviceReport.exe`
   - `config.json`
   - `modules/`

## ❓ Problemas Comunes

### "No se puede ejecutar scripts en este sistema"

**Solución**:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass
```

### "No se pudo conectar al recurso compartido"

**Causas comunes**:
- ❌ IP incorrecta en `config.json`
- ❌ Credenciales incorrectas
- ❌ El servidor no está encendido
- ❌ Firewall bloqueando la conexión

**Solución**: Verifica manualmente:
```powershell
Test-Connection 192.168.1.85
```

### "Error al enviar a OneDrive"

**Causas comunes**:
- ❌ Client ID o Client Secret no configurados
- ❌ Permisos no otorgados en Azure AD

**Solución**: Sigue [AZURE_SETUP.md](AZURE_SETUP.md) paso a paso

### Falta información en los reportes

**Solución**: Ejecuta PowerShell **como Administrador**

## 📞 Necesitas Ayuda?

1. 📖 Lee la documentación completa: [README.md](README.md)
2. 🔧 Configuración de OneDrive: [AZURE_SETUP.md](AZURE_SETUP.md)
3. 📝 Historial de cambios: [CHANGELOG.md](CHANGELOG.md)

## 🎉 ¡Listo!

Ahora tienes **Device Report** funcionando. Cada vez que lo ejecutes:
- Recopilará información completa del equipo
- Generará reportes profesionales
- Los enviará automáticamente al lugar correcto

---

**Device Report v1.0** - Simplificando la recolección de información para soporte técnico IT
