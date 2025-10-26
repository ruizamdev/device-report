function Get-NetworkInfo {
    <#
    .SYNOPSIS
    Recopila información detallada de red del equipo.

    .DESCRIPTION
    Obtiene información sobre:
    - Adaptadores de red
    - Configuración IP
    - Rutas de red
    - Conexiones activas
    - Perfiles WiFi guardados con contraseñas
    - DNS y configuración de red
    - Estado del firewall

    .EXAMPLE
    $netInfo = Get-NetworkInfo
    #>

    [CmdletBinding()]
    param()

    Write-Host "[INFO] Recopilando información de red..." -ForegroundColor Cyan

    $networkInfo = @{
        NetworkAdapters = $null
        IPConfiguration = $null
        Routes = $null
        ActiveConnections = $null
        WiFiProfiles = $null
        DNSConfiguration = $null
        TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    try {
        # Adaptadores de red
        Write-Host "  - Adaptadores de red..." -ForegroundColor Gray
        $networkInfo.NetworkAdapters = Get-NetAdapter -ErrorAction SilentlyContinue |
            Select-Object Name, InterfaceDescription, Status, MacAddress, LinkSpeed, MediaType, DriverVersion

        # Configuración IP
        Write-Host "  - Configuración IP..." -ForegroundColor Gray
        $networkInfo.IPConfiguration = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
            Select-Object InterfaceAlias, InterfaceIndex, IPv4Address, IPv6Address,
                          IPv4DefaultGateway, IPv6DefaultGateway, DNSServer

        # Direcciones IP detalladas
        $networkInfo.IPAddresses = Get-NetIPAddress -ErrorAction SilentlyContinue |
            Select-Object InterfaceAlias, IPAddress, PrefixLength, AddressFamily, Type, PrefixOrigin, SuffixOrigin

        # Rutas de red
        Write-Host "  - Tabla de rutas..." -ForegroundColor Gray
        $networkInfo.Routes = Get-NetRoute -ErrorAction SilentlyContinue |
            Where-Object { $_.DestinationPrefix -ne "::/0" } |
            Select-Object DestinationPrefix, NextHop, InterfaceAlias, RouteMetric |
            Sort-Object RouteMetric

        # Conexiones TCP activas
        Write-Host "  - Conexiones activas..." -ForegroundColor Gray
        $networkInfo.ActiveConnections = Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
            Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess |
            Sort-Object LocalPort

        # Configuración DNS
        Write-Host "  - Configuración DNS..." -ForegroundColor Gray
        $networkInfo.DNSConfiguration = Get-DnsClientServerAddress -ErrorAction SilentlyContinue |
            Where-Object { $_.ServerAddresses.Count -gt 0 } |
            Select-Object InterfaceAlias, AddressFamily, ServerAddresses

        # Caché DNS
        $networkInfo.DNSCache = Get-DnsClientCache -ErrorAction SilentlyContinue |
            Select-Object Entry, Name, Type, TimeToLive, Data |
            Sort-Object Entry

        # Perfiles WiFi guardados con contraseñas (si hay adaptadores WiFi)
        Write-Host "  - Perfiles WiFi y contraseñas guardadas..." -ForegroundColor Gray
        try {
            $wifiProfiles = @()
            $profileList = netsh wlan show profiles 2>$null

            if ($LASTEXITCODE -eq 0 -and $profileList) {
                $profiles = $profileList | Select-String ":\s+(.+)$" | ForEach-Object { $_.Matches.Groups[1].Value.Trim() }

                foreach ($profile in $profiles) {
                    $profileInfo = netsh wlan show profile name="$profile" key=clear 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        # Parsear información del perfil
                        $ssid = $profile
                        # Parseo de autenticación
                        $authSpanishMatch = $profileInfo | Select-String "Autenticaci.n\s+:\s+(.+)"
                        if ($authSpanishMatch) {
                            $authentication = $authSpanishMatch.Matches.Groups[1].Value.Trim() -replace '\s+', ' '
                        } else {
                            $authentication = ($profileInfo | Select-String "Authentication\s+:\s+(.+)").Matches.Groups[1].Value.Trim() -replace '\s+', ' '
                        }
                        # Parseo de cifrado
                        $cipherSpanishMatch = $profileInfo | Select-String "Cifrado\s+:\s+(.+)"
                        if ($cipherSpanishMatch) {
                            $cipher = $cipherSpanishMatch.Matches.Groups[1].Value.Trim() -replace '\s+', ' '
                        } else {
                            $cipher = ($profileInfo | Select-String "Cipher\s+:\s+(.+)").Matches.Groups[1].Value.Trim() -replace '\s+', ' '
                        }
                        $passSpanishMatch = $profileInfo | Select-String "Contenido de la clave\s+:\s+(.+)"
                        if ($passSpanishMatch) {
                            $passSpanishMatch.Matches.Groups[1].Value.Trim() -replace '\s+', ' '
                        } else {
                            $password = ($profileInfo | Select-String "Key Content\s+:\s+(.+)").Matches.Groups[1].Value.Trim()
                        }

                        # Si no hay contraseña, marcar como no disponible
                        if ([string]::IsNullOrWhiteSpace($password)) {
                            $password = "N/A (Red abierta o no disponible)"
                        }

                        $wifiProfiles += [PSCustomObject]@{
                            SSID = $ssid
                            Authentication = if ($authentication) { $authentication } else { "N/A" }
                            Encryption = if ($cipher) { $cipher } else { "N/A" }
                            Password = $password
                        }
                    }
                }

                if ($wifiProfiles.Count -gt 0) {
                    Write-Host "    ✓ Se encontraron $($wifiProfiles.Count) redes WiFi guardadas" -ForegroundColor Green
                } else {
                    Write-Host "    ℹ No se encontraron redes WiFi guardadas" -ForegroundColor Yellow
                }
            } else {
                Write-Host "    ℹ No hay adaptador WiFi disponible" -ForegroundColor Yellow
            }

            $networkInfo.WiFiProfiles = $wifiProfiles
        }
        catch {
            Write-Host "  [WARN] No se pudieron obtener perfiles WiFi: $($_.Exception.Message)" -ForegroundColor Yellow
            $networkInfo.WiFiProfiles = @()
        }

        # Estado de firewall
        Write-Host "  - Estado del firewall..." -ForegroundColor Gray
        $networkInfo.FirewallProfiles = Get-NetFirewallProfile -ErrorAction SilentlyContinue |
            Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction

        Write-Host "[OK] Información de red recopilada" -ForegroundColor Green
        return $networkInfo
    }
    catch {
        Write-Host "[ERROR] Error al recopilar información de red: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Export-ModuleMember -Function Get-NetworkInfo
