function Get-SoftwareInfo {
    <#
    .SYNOPSIS
    Recopila información sobre el software instalado y en ejecución.

    .DESCRIPTION
    Recopila información sobre:
    - Programas instalados
    - Actualizaciones de Windows (Hotfixes)
    - Servicios en ejecución
    - Procesos activos

    .PARAMETER Config
    Objeto de configuración que especifica qué información recopilar.

    .EXAMPLE
    $softInfo = Get-SoftwareInfo -Config $config
    #>

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [PSCustomObject]$Config
    )

    Write-Host "[INFO] Recopilando información de software..." -ForegroundColor Cyan

    $softwareInfo = @{
        InstalledPrograms = $null
        WindowsUpdates = $null
        Services = $null
        Processes = $null
        TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    try {
        # Programas instalados
        if ($Config.DataCollection.Software.InstalledPrograms) {
            Write-Host "  - Programas instalados..." -ForegroundColor Gray

            $installedPrograms = @()

            # Programas de 64 bits
            $installedPrograms += Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName } |
                Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, InstallLocation, UninstallString

            # Programas de 32 bits en sistemas de 64 bits
            if (Test-Path "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall") {
                $installedPrograms += Get-ItemProperty "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
                    Where-Object { $_.DisplayName } |
                    Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, InstallLocation, UninstallString
            }

            # Programas del usuario actual
            $installedPrograms += Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName } |
                Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, InstallLocation, UninstallString

            # Eliminar duplicados y ordenar
            $softwareInfo.InstalledPrograms = $installedPrograms |
                Sort-Object DisplayName -Unique |
                Where-Object { $_.DisplayName -and $_.DisplayName.Trim() -ne "" }
        }

        # Actualizaciones de Windows
        if ($Config.DataCollection.Software.WindowsUpdates) {
            Write-Host "  - Actualizaciones de Windows..." -ForegroundColor Gray
            $softwareInfo.WindowsUpdates = Get-HotFix |
                Select-Object Description, HotFixID, InstalledBy, InstalledOn |
                Sort-Object InstalledOn -Descending
        }

        # Servicios en ejecución
        if ($Config.DataCollection.Software.RunningServices) {
            Write-Host "  - Servicios..." -ForegroundColor Gray
            $softwareInfo.Services = Get-Service |
                Select-Object Name, DisplayName, Status, StartType, ServiceType |
                Sort-Object DisplayName
        }

        # Procesos activos
        if ($Config.DataCollection.Software.ActiveProcesses) {
            Write-Host "  - Procesos activos..." -ForegroundColor Gray
            $softwareInfo.Processes = Get-Process |
                Select-Object ProcessName, Id, CPU, WorkingSet, Path, Company, Product, ProductVersion, StartTime |
                Sort-Object CPU -Descending |
                Select-Object -First 50  # Limitar a los 50 procesos con mayor uso de CPU
        }

        Write-Host "[OK] Información de software recopilada" -ForegroundColor Green
        return $softwareInfo
    }
    catch {
        Write-Host "[ERROR] Error al recopilar información de software: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Export-ModuleMember -Function Get-SoftwareInfo
