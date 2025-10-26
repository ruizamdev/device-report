<#
.SYNOPSIS
Script para compilar DeviceReport.ps1 a un ejecutable .exe

.DESCRIPTION
Este script utiliza ps2exe para convertir el script de PowerShell en un ejecutable
de Windows que puede ser distribuido y ejecutado sin necesidad de PowerShell visible.

.NOTES
Requisitos:
- Módulo ps2exe instalado: Install-Module -Name ps2exe -Scope CurrentUser
- PowerShell 5.1 o superior
#>

[CmdletBinding()]
param()

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Device Report - Build Executable" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Verificar si ps2exe está instalado
Write-Host "[INFO] Verificando módulo ps2exe..." -ForegroundColor Cyan

if (-not (Get-Module -ListAvailable -Name ps2exe)) {
    Write-Host "[WARN] El módulo ps2exe no está instalado" -ForegroundColor Yellow
    Write-Host ""
    $install = Read-Host "¿Desea instalarlo ahora? (S/N)"

    if ($install -eq "S" -or $install -eq "s") {
        Write-Host "[INFO] Instalando ps2exe..." -ForegroundColor Cyan
        try {
            Install-Module -Name ps2exe -Scope CurrentUser -Force
            Write-Host "[OK] ps2exe instalado exitosamente" -ForegroundColor Green
        }
        catch {
            Write-Host "[ERROR] No se pudo instalar ps2exe: $($_.Exception.Message)" -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "[ERROR] ps2exe es requerido para compilar el ejecutable" -ForegroundColor Red
        Write-Host "        Instálalo con: Install-Module -Name ps2exe -Scope CurrentUser" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[OK] Módulo ps2exe disponible" -ForegroundColor Green
Write-Host ""

# Importar ps2exe
Import-Module ps2exe

# Obtener ruta del script
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptPath) {
    $scriptPath = $PSScriptRoot
}

# Rutas
$inputFile = Join-Path $scriptPath "DeviceReport.ps1"
$outputFile = Join-Path $scriptPath "DeviceReport.exe"
$iconFile = Join-Path $scriptPath "icon.ico"

# Verificar que existe el archivo de entrada
if (-not (Test-Path $inputFile)) {
    Write-Host "[ERROR] No se encontró DeviceReport.ps1" -ForegroundColor Red
    exit 1
}

# Parámetros de compilación
Write-Host "[INFO] Compilando ejecutable..." -ForegroundColor Cyan
Write-Host "  - Archivo de entrada: DeviceReport.ps1" -ForegroundColor Gray
Write-Host "  - Archivo de salida: DeviceReport.exe" -ForegroundColor Gray
Write-Host ""

try {
    $ps2exeParams = @{
        inputFile = $inputFile
        outputFile = $outputFile
        title = "Device Report"
        version = "1.0.0.0"
        company = "Armando Ruiz"
        product = "Device Report"
        copyright = "© 2025 ruizamdev"
        description = "Sistema de recolección de información de dispositivos"
        requireAdmin = $false  # Cambiar a $true si se requiere admin
        noConsole = $false     # Cambiar a $true para ocultar la consola
        noError = $false
        noOutput = $false
    }

    # Agregar icono si existe
    if (Test-Path $iconFile) {
        $ps2exeParams.iconFile = $iconFile
        Write-Host "  - Icono: icon.ico" -ForegroundColor Gray
    }

    Invoke-ps2exe @ps2exeParams

    if (Test-Path $outputFile) {
        $exeSize = (Get-Item $outputFile).Length
        $exeSizeMB = [math]::Round($exeSize / 1MB, 2)

        Write-Host ""
        Write-Host "[OK] Ejecutable compilado exitosamente" -ForegroundColor Green
        Write-Host "     Ubicación: $outputFile" -ForegroundColor Gray
        Write-Host "     Tamaño: $exeSizeMB MB" -ForegroundColor Gray
        Write-Host ""

        # Crear carpeta de distribución
        Write-Host "[INFO] Creando paquete de distribución..." -ForegroundColor Cyan

        $distFolder = Join-Path $scriptPath "dist"
        if (Test-Path $distFolder) {
            Remove-Item $distFolder -Recurse -Force
        }
        New-Item -ItemType Directory -Path $distFolder -Force | Out-Null

        # Copiar archivos necesarios
        Copy-Item $outputFile -Destination $distFolder
        Copy-Item (Join-Path $scriptPath "config.example.json") -Destination (Join-Path $distFolder "config.json")
        Copy-Item (Join-Path $scriptPath "README.md") -Destination $distFolder
        Copy-Item (Join-Path $scriptPath "AZURE_SETUP.md") -Destination $distFolder

        # Copiar carpeta modules
        $modulesSource = Join-Path $scriptPath "modules"
        $modulesDest = Join-Path $distFolder "modules"
        Copy-Item $modulesSource -Destination $modulesDest -Recurse

        Write-Host "[OK] Paquete de distribución creado en: $distFolder" -ForegroundColor Green
        Write-Host ""
        Write-Host "Contenido del paquete:" -ForegroundColor Gray
        Write-Host "  - DeviceReport.exe" -ForegroundColor Gray
        Write-Host "  - config.json (editar antes de usar)" -ForegroundColor Gray
        Write-Host "  - modules/ (todos los módulos)" -ForegroundColor Gray
        Write-Host "  - README.md" -ForegroundColor Gray
        Write-Host "  - AZURE_SETUP.md" -ForegroundColor Gray
        Write-Host ""

        # Opcionalmente, crear un ZIP del paquete
        Write-Host "[INFO] ¿Desea crear un archivo ZIP del paquete? (S/N)" -ForegroundColor Cyan
        $createZip = Read-Host

        if ($createZip -eq "S" -or $createZip -eq "s") {
            $zipFile = Join-Path $scriptPath "DeviceReport_v1.0.zip"
            if (Test-Path $zipFile) {
                Remove-Item $zipFile -Force
            }

            Add-Type -Assembly System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::CreateFromDirectory($distFolder, $zipFile, [System.IO.Compression.CompressionLevel]::Optimal, $false)

            if (Test-Path $zipFile) {
                $zipSize = (Get-Item $zipFile).Length
                $zipSizeMB = [math]::Round($zipSize / 1MB, 2)
                Write-Host "[OK] Archivo ZIP creado: DeviceReport_v1.0.zip ($zipSizeMB MB)" -ForegroundColor Green
            }
        }

        Write-Host ""
        Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host "  ✓ BUILD COMPLETADO EXITOSAMENTE" -ForegroundColor Green
        Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""
    }
    else {
        Write-Host "[ERROR] No se pudo crear el ejecutable" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "[ERROR] Error durante la compilación: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
