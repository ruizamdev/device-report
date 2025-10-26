function New-Reports {
    <#
    .SYNOPSIS
    Genera reportes en múltiples formatos (HTML, XML, TXT).

    .DESCRIPTION
    Toma la información recopilada y genera reportes en los formatos especificados.

    .PARAMETER Data
    Hashtable con toda la información recopilada.

    .PARAMETER OutputPath
    Ruta donde se guardarán los reportes.

    .PARAMETER ClientName
    Nombre del cliente.

    .PARAMETER Config
    Objeto de configuración.

    .EXAMPLE
    New-Reports -Data $allData -OutputPath "C:\Temp\Reports" -ClientName "Juan Perez" -Config $config
    #>

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Data,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [Parameter(Mandatory = $true)]
        [string]$ClientName,

        [Parameter(Mandatory = $true)]
        [PSCustomObject]$Config
    )

    Write-Host "[INFO] Generando reportes..." -ForegroundColor Cyan

    $reportFiles = @()

    try {
        # Crear directorio de salida si no existe
        if (-not (Test-Path $OutputPath)) {
            New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
        }

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $computerName = $env:COMPUTERNAME
        $userName = $env:USERNAME
        $reportBaseName = "${userName}-${computerName}"

        # Generar reporte TXT
        if ($Config.Reports.Formats -contains "TXT") {
            Write-Host "  - Generando reporte TXT..." -ForegroundColor Gray
            $txtPath = Join-Path $OutputPath "${reportBaseName}_${timestamp}.txt"
            New-TextReport -Data $Data -OutputPath $txtPath -ClientName $ClientName
            $reportFiles += $txtPath
        }

        # Generar reporte XML
        if ($Config.Reports.Formats -contains "XML") {
            Write-Host "  - Generando reporte XML..." -ForegroundColor Gray
            $xmlPath = Join-Path $OutputPath "${reportBaseName}_${timestamp}.xml"
            New-XMLReport -Data $Data -OutputPath $xmlPath -ClientName $ClientName
            $reportFiles += $xmlPath
        }

        # Generar reporte HTML
        if ($Config.Reports.Formats -contains "HTML") {
            Write-Host "  - Generando reporte HTML..." -ForegroundColor Gray
            $htmlPath = Join-Path $OutputPath "${reportBaseName}_${timestamp}.html"
            New-HTMLReport -Data $Data -OutputPath $htmlPath -ClientName $ClientName
            $reportFiles += $htmlPath
        }

        Write-Host "[OK] Reportes generados exitosamente" -ForegroundColor Green
        return $reportFiles
    }
    catch {
        Write-Host "[ERROR] Error al generar reportes: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

function New-TextReport {
    param($Data, $OutputPath, $ClientName)

    $report = New-Object System.Text.StringBuilder

    [void]$report.AppendLine("=" * 80)
    [void]$report.AppendLine("REPORTE DE DISPOSITIVO - FORMATO TEXTO")
    [void]$report.AppendLine("=" * 80)
    [void]$report.AppendLine("Cliente: $ClientName")
    [void]$report.AppendLine("Generado: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    [void]$report.AppendLine("=" * 80)
    [void]$report.AppendLine("")

    # Hardware
    if ($Data.Hardware) {
        [void]$report.AppendLine("-" * 80)
        [void]$report.AppendLine("INFORMACIÓN DE HARDWARE")
        [void]$report.AppendLine("-" * 80)

        if ($Data.Hardware.System) {
            [void]$report.AppendLine("`n[SISTEMA]")
            [void]$report.AppendLine("  Fabricante: $($Data.Hardware.System.Manufacturer)")
            [void]$report.AppendLine("  Modelo: $($Data.Hardware.System.Model)")
            [void]$report.AppendLine("  Tipo de sistema: $($Data.Hardware.System.SystemType)")
        }

        if ($Data.Hardware.Processor) {
            [void]$report.AppendLine("`n[PROCESADOR]")
            foreach ($cpu in $Data.Hardware.Processor) {
                [void]$report.AppendLine("  Nombre: $($cpu.Name)")
                [void]$report.AppendLine("  Núcleos: $($cpu.NumberOfCores)")
                [void]$report.AppendLine("  Procesadores lógicos: $($cpu.NumberOfLogicalProcessors)")
                [void]$report.AppendLine("  Velocidad máxima: $($cpu.MaxClockSpeed) MHz")
            }
        }

        if ($Data.Hardware.Memory) {
            [void]$report.AppendLine("`n[MEMORIA RAM]")
            $totalRAM = 0
            foreach ($mem in $Data.Hardware.Memory) {
                $capacityGB = [math]::Round($mem.Capacity / 1GB, 2)
                [void]$report.AppendLine("  Módulo: $($mem.DeviceLocator)")
                [void]$report.AppendLine("    Capacidad: $capacityGB GB")
                [void]$report.AppendLine("    Velocidad: $($mem.Speed) MHz")
                [void]$report.AppendLine("    Fabricante: $($mem.Manufacturer)")
                $totalRAM += $capacityGB
            }
            [void]$report.AppendLine("  Total RAM: $totalRAM GB")
        }
    }

    # Usuario
    if ($Data.User) {
        [void]$report.AppendLine("`n" + "-" * 80)
        [void]$report.AppendLine("INFORMACIÓN DE USUARIO Y SISTEMA OPERATIVO")
        [void]$report.AppendLine("-" * 80)

        if ($Data.User.CurrentUser) {
            [void]$report.AppendLine("`n[USUARIO ACTUAL]")
            [void]$report.AppendLine("  Usuario: $($Data.User.CurrentUser.UserName)")
            [void]$report.AppendLine("  Dominio: $($Data.User.CurrentUser.UserDomain)")
            [void]$report.AppendLine("  Equipo: $($Data.User.CurrentUser.ComputerName)")
        }

        if ($Data.User.OperatingSystem) {
            [void]$report.AppendLine("`n[SISTEMA OPERATIVO]")
            [void]$report.AppendLine("  Sistema: $($Data.User.OperatingSystem.Caption)")
            [void]$report.AppendLine("  Versión: $($Data.User.OperatingSystem.Version)")
            [void]$report.AppendLine("  Build: $($Data.User.OperatingSystem.BuildNumber)")
            [void]$report.AppendLine("  Arquitectura: $($Data.User.OperatingSystem.Architecture)")
        }
    }

    # Software
    if ($Data.Software) {
        [void]$report.AppendLine("`n" + "-" * 80)
        [void]$report.AppendLine("INFORMACIÓN DE SOFTWARE")
        [void]$report.AppendLine("-" * 80)

        if ($Data.Software.InstalledPrograms) {
            [void]$report.AppendLine("`n[PROGRAMAS INSTALADOS] (Total: $($Data.Software.InstalledPrograms.Count))")
            foreach ($prog in ($Data.Software.InstalledPrograms | Select-Object -First 100)) {
                [void]$report.AppendLine("  - $($prog.DisplayName) ($($prog.DisplayVersion))")
            }
        }

        if ($Data.Software.WindowsUpdates) {
            [void]$report.AppendLine("`n[ACTUALIZACIONES DE WINDOWS] (Total: $($Data.Software.WindowsUpdates.Count))")
            foreach ($update in ($Data.Software.WindowsUpdates | Select-Object -First 20)) {
                [void]$report.AppendLine("  - $($update.HotFixID): $($update.Description)")
            }
        }
    }

    # Red
    if ($Data.Network) {
        [void]$report.AppendLine("`n" + "-" * 80)
        [void]$report.AppendLine("INFORMACIÓN DE RED")
        [void]$report.AppendLine("-" * 80)

        if ($Data.Network.NetworkAdapters) {
            [void]$report.AppendLine("`n[ADAPTADORES DE RED]")
            foreach ($adapter in $Data.Network.NetworkAdapters) {
                [void]$report.AppendLine("  Nombre: $($adapter.Name)")
                [void]$report.AppendLine("    Estado: $($adapter.Status)")
                [void]$report.AppendLine("    MAC: $($adapter.MacAddress)")
                [void]$report.AppendLine("    Velocidad: $($adapter.LinkSpeed)")
            }
        }

        if ($Data.Network.IPConfiguration) {
            [void]$report.AppendLine("`n[CONFIGURACIÓN IP]")
            foreach ($config in $Data.Network.IPConfiguration) {
                [void]$report.AppendLine("  Interfaz: $($config.InterfaceAlias)")
                [void]$report.AppendLine("    IPv4: $($config.IPv4Address.IPAddress)")
                [void]$report.AppendLine("    Gateway: $($config.IPv4DefaultGateway.NextHop)")
                [void]$report.AppendLine("    DNS: $($config.DNSServer.ServerAddresses -join ', ')")
            }
        }

        if ($Data.Network.WiFiProfiles -and $Data.Network.WiFiProfiles.Count -gt 0) {
            [void]$report.AppendLine("`n[REDES WIFI GUARDADAS] (Total: $($Data.Network.WiFiProfiles.Count))")
            foreach ($wifi in $Data.Network.WiFiProfiles) {
                [void]$report.AppendLine("  Red: $($wifi.SSID)")
                [void]$report.AppendLine("    Autenticación: $($wifi.Authentication)")
                [void]$report.AppendLine("    Cifrado: $($wifi.Encryption)")
                [void]$report.AppendLine("    Contraseña: $($wifi.Password)")
                [void]$report.AppendLine("")
            }
        }
    }

    [void]$report.AppendLine("`n" + "=" * 80)
    [void]$report.AppendLine("FIN DEL REPORTE")
    [void]$report.AppendLine("=" * 80)

    $report.ToString() | Out-File -FilePath $OutputPath -Encoding UTF8
}

function New-XMLReport {
    param($Data, $OutputPath, $ClientName)

    $xmlData = @{
        Report = @{
            Client = $ClientName
            GeneratedDate = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
            Hardware = $Data.Hardware
            User = $Data.User
            Software = $Data.Software
            Network = $Data.Network
        }
    }

    $xmlData | ConvertTo-Json -Depth 10 | ConvertFrom-Json | Export-Clixml -Path $OutputPath
}

function New-HTMLReport {
    param($Data, $OutputPath, $ClientName)

    $html = @"
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Dispositivo - $ClientName</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }
        h2 { color: #34495e; margin-top: 30px; margin-bottom: 15px; padding: 10px; background: #ecf0f1; border-left: 4px solid #3498db; }
        h3 { color: #555; margin-top: 20px; margin-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th { background: #3498db; color: white; padding: 12px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #ddd; }
        tr:hover { background: #f8f9fa; }
        .info-box { background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .label { font-weight: bold; color: #2980b9; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }
        ul { margin-left: 20px; }
        li { margin: 5px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Reporte de Dispositivo</h1>
        <div class="info-box">
            <p><span class="label">Cliente:</span> $ClientName</p>
            <p><span class="label">Equipo:</span> $($env:COMPUTERNAME)</p>
            <p><span class="label">Usuario:</span> $($env:USERNAME)</p>
            <p class="timestamp">Generado: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')</p>
        </div>
"@

    # Hardware
    if ($Data.Hardware) {
        $html += "<h2>Información de Hardware</h2>"

        if ($Data.Hardware.System) {
            $sys = $Data.Hardware.System
            $html += @"
            <h3>Sistema</h3>
            <table>
                <tr><td class="label">Fabricante</td><td>$($sys.Manufacturer)</td></tr>
                <tr><td class="label">Modelo</td><td>$($sys.Model)</td></tr>
                <tr><td class="label">Tipo</td><td>$($sys.SystemType)</td></tr>
                <tr><td class="label">Dominio/Grupo de trabajo</td><td>$($sys.Domain)$($sys.Workgroup)</td></tr>
            </table>
"@
        }

        if ($Data.Hardware.Processor) {
            $html += "<h3>Procesador</h3><table><tr><th>Nombre</th><th>Núcleos</th><th>Procesadores Lógicos</th><th>Velocidad</th></tr>"
            foreach ($cpu in $Data.Hardware.Processor) {
                $html += "<tr><td>$($cpu.Name)</td><td>$($cpu.NumberOfCores)</td><td>$($cpu.NumberOfLogicalProcessors)</td><td>$($cpu.MaxClockSpeed) MHz</td></tr>"
            }
            $html += "</table>"
        }

        if ($Data.Hardware.Memory) {
            $html += "<h3>Memoria RAM</h3><table><tr><th>Ubicación</th><th>Capacidad</th><th>Velocidad</th><th>Fabricante</th></tr>"
            foreach ($mem in $Data.Hardware.Memory) {
                $capacityGB = [math]::Round($mem.Capacity / 1GB, 2)
                $html += "<tr><td>$($mem.DeviceLocator)</td><td>$capacityGB GB</td><td>$($mem.Speed) MHz</td><td>$($mem.Manufacturer)</td></tr>"
            }
            $html += "</table>"
        }

        if ($Data.Hardware.Disks) {
            $html += "<h3>Discos</h3><table><tr><th>Modelo</th><th>Interfaz</th><th>Tamaño</th><th>Estado</th></tr>"
            foreach ($disk in $Data.Hardware.Disks) {
                $sizeGB = [math]::Round($disk.Size / 1GB, 2)
                $html += "<tr><td>$($disk.Model)</td><td>$($disk.InterfaceType)</td><td>$sizeGB GB</td><td>$($disk.Status)</td></tr>"
            }
            $html += "</table>"
        }
    }

    # Usuario y SO
    if ($Data.User) {
        $html += "<h2>Usuario y Sistema Operativo</h2>"

        if ($Data.User.OperatingSystem) {
            $os = $Data.User.OperatingSystem
            $html += @"
            <table>
                <tr><td class="label">Sistema Operativo</td><td>$($os.Caption)</td></tr>
                <tr><td class="label">Versión</td><td>$($os.Version)</td></tr>
                <tr><td class="label">Build</td><td>$($os.BuildNumber)</td></tr>
                <tr><td class="label">Arquitectura</td><td>$($os.Architecture)</td></tr>
                <tr><td class="label">Usuario Registrado</td><td>$($os.RegisteredUser)</td></tr>
                <tr><td class="label">Organización</td><td>$($os.Organization)</td></tr>
            </table>
"@
        }
    }

    # Software
    if ($Data.Software) {
        $html += "<h2>Software</h2>"

        if ($Data.Software.InstalledPrograms) {
            $html += "<h3>Programas Instalados (Mostrando primeros 50)</h3><table><tr><th>Nombre</th><th>Versión</th><th>Fabricante</th></tr>"
            foreach ($prog in ($Data.Software.InstalledPrograms | Select-Object -First 50)) {
                $html += "<tr><td>$($prog.DisplayName)</td><td>$($prog.DisplayVersion)</td><td>$($prog.Publisher)</td></tr>"
            }
            $html += "</table>"
        }

        if ($Data.Software.WindowsUpdates) {
            $html += "<h3>Actualizaciones de Windows (Últimas 20)</h3><table><tr><th>HotFix ID</th><th>Descripción</th><th>Instalado Por</th><th>Fecha</th></tr>"
            foreach ($update in ($Data.Software.WindowsUpdates | Select-Object -First 20)) {
                $html += "<tr><td>$($update.HotFixID)</td><td>$($update.Description)</td><td>$($update.InstalledBy)</td><td>$($update.InstalledOn)</td></tr>"
            }
            $html += "</table>"
        }
    }

    # Red
    if ($Data.Network) {
        $html += "<h2>Red</h2>"

        if ($Data.Network.NetworkAdapters) {
            $html += "<h3>Adaptadores de Red</h3><table><tr><th>Nombre</th><th>Estado</th><th>MAC</th><th>Velocidad</th></tr>"
            foreach ($adapter in $Data.Network.NetworkAdapters) {
                $html += "<tr><td>$($adapter.Name)</td><td>$($adapter.Status)</td><td>$($adapter.MacAddress)</td><td>$($adapter.LinkSpeed)</td></tr>"
            }
            $html += "</table>"
        }

        if ($Data.Network.IPConfiguration) {
            $html += "<h3>Configuración IP</h3><table><tr><th>Interfaz</th><th>IPv4</th><th>Gateway</th><th>DNS</th></tr>"
            foreach ($config in $Data.Network.IPConfiguration) {
                $html += "<tr><td>$($config.InterfaceAlias)</td><td>$($config.IPv4Address.IPAddress)</td><td>$($config.IPv4DefaultGateway.NextHop)</td><td>$($config.DNSServer.ServerAddresses -join '<br>')</td></tr>"
            }
            $html += "</table>"
        }

        if ($Data.Network.WiFiProfiles -and $Data.Network.WiFiProfiles.Count -gt 0) {
            $html += "<h3>Redes WiFi Guardadas</h3><table><tr><th>SSID</th><th>Autenticación</th><th>Cifrado</th><th>Contraseña</th></tr>"
            foreach ($wifi in $Data.Network.WiFiProfiles) {
                $html += "<tr><td>$($wifi.SSID)</td><td>$($wifi.Authentication)</td><td>$($wifi.Encryption)</td><td><strong>$($wifi.Password)</strong></td></tr>"
            }
            $html += "</table>"
        }
    }

    $html += @"
    </div>
</body>
</html>
"@

    $html | Out-File -FilePath $OutputPath -Encoding UTF8
}

Export-ModuleMember -Function New-Reports
