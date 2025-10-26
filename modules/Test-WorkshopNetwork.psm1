function Test-WorkshopNetwork {
    <#
    .SYNOPSIS
    Detecta si el equipo está en la red del taller.

    .DESCRIPTION
    Realiza un ping al servidor del taller para determinar si el equipo
    está conectado a la red local del taller.

    .PARAMETER Config
    Objeto de configuración que contiene los parámetros de detección.

    .EXAMPLE
    Test-WorkshopNetwork -Config $config
    #>

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [PSCustomObject]$Config
    )

    try {
        Write-Host "[INFO] Detectando red del taller..." -ForegroundColor Cyan

        $detectionIP = $Config.WorkshopNetwork.DetectionIP
        $timeout = $Config.WorkshopNetwork.PingTimeout
        $count = $Config.WorkshopNetwork.PingCount

        Write-Host "[INFO] Haciendo ping a: $detectionIP" -ForegroundColor Gray

        $pingResult = Test-Connection -ComputerName $detectionIP -Count $count -Quiet -ErrorAction SilentlyContinue

        if ($pingResult) {
            Write-Host "[OK] Conectado a la red del taller" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[INFO] No se detectó la red del taller" -ForegroundColor Yellow
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] Error al detectar red: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Export-ModuleMember -Function Test-WorkshopNetwork
