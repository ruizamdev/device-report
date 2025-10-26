<#
.SYNOPSIS
Device Report - Sistema de recolección y envío de información de dispositivos

.DESCRIPTION
Recopila información detallada del hardware, software, usuario y red del equipo,
genera reportes en múltiples formatos (HTML, XML, TXT), los comprime y los envía
automáticamente al recurso compartido del taller (si está en la red) o a OneDrive
(si está fuera de la red).

.PARAMETER ClientName
Nombre del cliente (opcional, se pedirá interactivamente si no se proporciona)

.EXAMPLE W/O PARAMETER
.\DeviceReport.ps1

.EXAMPLE W/ PARAMETER
.\DeviceReport.ps1 -ClientName "Juan Perez"

.NOTES
Versión: 1.0
Autor: Armando Ruiz
Basado en: DataGath 3.0
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ClientName
)

# Configuración de errores
$ErrorActionPreference = "Stop"

# Banner
function Show-Banner {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                               ║" -ForegroundColor Cyan
    Write-Host "║                    DEVICE REPORT v1.0                         ║" -ForegroundColor Cyan
    Write-Host "║         Sistema de Recolección de Información                 ║" -ForegroundColor Cyan
    Write-Host "║                       del Sistema                             ║" -ForegroundColor Cyan
    Write-Host "║                                                               ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# Función principal
function Start-DeviceReport {
    try {
        Show-Banner

        # Obtener directorio del script
        $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
        if (-not $scriptPath) {
            Write-Host "[INFO] Se utilizó la variable PSScriptRoot para establecer la ruta del script" -ForegroundColor Yellow
            $scriptPath = $PSScriptRoot
        }

        # Cargar configuración
        Write-Host "[INFO] Cargando configuración..." -ForegroundColor Cyan
        $configPath = Join-Path $scriptPath "config.json"

        if (-not (Test-Path $configPath)) {
            Write-Host "[ERROR] No se encontró el archivo config.json" -ForegroundColor Red
            Write-Host "        Ubicación esperada: $configPath" -ForegroundColor Yellow
            exit 1
        }

        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        Write-Host "[OK] Configuración cargada" -ForegroundColor Green

        # Solicitar nombre del cliente si no se proporcionó
        if (-not $ClientName) {
            Write-Host ""
            $ClientName = Read-Host "Ingrese el nombre del cliente"

            if ([string]::IsNullOrWhiteSpace($ClientName)) {
                Write-Host "[ERROR] El nombre del cliente es obligatorio" -ForegroundColor Red
                exit 1
            }
        }

        Write-Host ""
        Write-Host "[INFO] Cliente: $ClientName" -ForegroundColor Cyan
        Write-Host "[INFO] Equipo: $env:COMPUTERNAME" -ForegroundColor Cyan
        Write-Host "[INFO] Usuario: $env:USERNAME" -ForegroundColor Cyan
        Write-Host ""

        # Cargar módulos
        Write-Host "[INFO] Cargando módulos..." -ForegroundColor Cyan
        $modulesPath = Join-Path $scriptPath "modules"

        $modules = @(
            "Test-WorkshopNetwork.ps1",
            "Get-HardwareInfo.ps1",
            "Get-UserInfo.ps1",
            "Get-SoftwareInfo.ps1",
            "Get-NetworkInfo.ps1",
            "New-Reports.ps1",
            "Compress-Reports.ps1",
            "Send-ToNetworkShare.ps1",
            "Send-ToOneDrive.ps1"
        )

        foreach ($module in $modules) {
            $modulePath = Join-Path $modulesPath $module
            if (Test-Path $modulePath) {
                Import-Module $modulePath -Force
                Write-Host "  - $module cargado" -ForegroundColor Gray
            }
            else {
                Write-Host "[ERROR] No se encontró el módulo: $module" -ForegroundColor Red
                exit 1
            }
        }
        Write-Host "[OK] Módulos cargados" -ForegroundColor Green
        Write-Host ""

        # Detectar red del taller
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        $isInWorkshop = Test-WorkshopNetwork -Config $config
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""

        # Recopilar información
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host "  RECOPILANDO INFORMACIÓN DEL DISPOSITIVO" -ForegroundColor Cyan
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""

        $allData = @{}

        # Hardware
        if ($config.DataCollection.Hardware) {
            $allData.Hardware = Get-HardwareInfo
        }

        # Usuario
        if ($config.DataCollection.User) {
            $allData.User = Get-UserInfo
        }

        # Software
        if ($config.DataCollection.Software) {
            $allData.Software = Get-SoftwareInfo -Config $config
        }

        # Red
        if ($config.DataCollection.Network) {
            $allData.Network = Get-NetworkInfo
        }

        Write-Host ""
        Write-Host "[OK] Recopilación completada" -ForegroundColor Green
        Write-Host ""

        # Generar reportes
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host "  GENERANDO REPORTES" -ForegroundColor Cyan
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""

        # Crear directorio temporal
        $tempFolder = $ExecutionContext.InvokeCommand.ExpandString($config.Reports.TempFolder)
        if (-not (Test-Path $tempFolder)) {
            New-Item -ItemType Directory -Path $tempFolder -Force | Out-Null
        }

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $reportFolder = Join-Path $tempFolder "${ClientName}_${timestamp}"
        New-Item -ItemType Directory -Path $reportFolder -Force | Out-Null

        $reportFiles = New-Reports -Data $allData -OutputPath $reportFolder -ClientName $ClientName -Config $config

        if (-not $reportFiles -or $reportFiles.Count -eq 0) {
            Write-Host "[ERROR] No se pudieron generar los reportes" -ForegroundColor Red
            exit 1
        }

        Write-Host ""

        # Comprimir reportes
        if ($config.Reports.CompressReports) {
            Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
            Write-Host "  COMPRIMIENDO REPORTES" -ForegroundColor Cyan
            Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
            Write-Host ""

            $zipFile = Compress-Reports -ReportFiles $reportFiles -OutputPath $tempFolder -ClientName $ClientName

            if (-not $zipFile) {
                Write-Host "[ERROR] No se pudo comprimir los reportes" -ForegroundColor Red
                exit 1
            }

            # Limpiar carpeta temporal de reportes
            Remove-Item $reportFolder -Recurse -Force -ErrorAction SilentlyContinue

            Write-Host ""
        }
        else {
            $zipFile = $reportFiles[0]  # Si no se comprime, usar el primer archivo
        }

        # Enviar reportes
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host "  ENVIANDO REPORTES" -ForegroundColor Cyan
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""

        $sendSuccess = $false

        if ($isInWorkshop) {
            # Enviar a recurso compartido de red
            Write-Host "[INFO] Modo: Recurso compartido de red (taller)" -ForegroundColor Cyan
            $sendSuccess = Send-ToNetworkShare -ZipFile $zipFile -ClientName $ClientName -Config $config
        }
        else {
            # Enviar a OneDrive
            Write-Host "[INFO] Modo: OneDrive (fuera del taller)" -ForegroundColor Cyan
            $sendSuccess = Send-ToOneDrive -ZipFile $zipFile -ClientName $ClientName -Config $config
        }

        Write-Host ""

        # Resultado final
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        if ($sendSuccess) {
            Write-Host "  ✓ PROCESO COMPLETADO EXITOSAMENTE" -ForegroundColor Green
        }
        else {
            Write-Host "  ✗ ERROR AL ENVIAR REPORTES" -ForegroundColor Red
            Write-Host ""
            Write-Host "[INFO] El archivo comprimido se encuentra en:" -ForegroundColor Yellow
            Write-Host "       $zipFile" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "       Puede enviarlo manualmente." -ForegroundColor Yellow
        }
        Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""

        # Pausar antes de salir
        Write-Host "Presione cualquier tecla para salir..." -ForegroundColor Gray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

        if ($sendSuccess) {
            exit 0
        }
        else {
            exit 1
        }
    }
    catch {
        Write-Host ""
        Write-Host "[ERROR FATAL] $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Stack Trace:" -ForegroundColor Yellow
        Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Presione cualquier tecla para salir..." -ForegroundColor Gray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

# Ejecutar
Start-DeviceReport
