function Send-ToNetworkShare {
    <#
    .SYNOPSIS
    Envía el archivo comprimido al recurso compartido de red.

    .DESCRIPTION
    Copia el archivo ZIP de reportes al recurso compartido de red del taller,
    creando la carpeta del cliente si no existe.

    .PARAMETER ZipFile
    Ruta del archivo ZIP a enviar.

    .PARAMETER ClientName
    Nombre del cliente (usado para crear la carpeta en el recurso compartido).

    .PARAMETER Config
    Objeto de configuración con las credenciales y ruta del recurso compartido.

    .EXAMPLE
    Send-ToNetworkShare -ZipFile "C:\Temp\reporte.zip" -ClientName "Juan Perez" -Config $config
    #>

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ZipFile,

        [Parameter(Mandatory = $true)]
        [string]$ClientName,

        [Parameter(Mandatory = $true)]
        [PSCustomObject]$Config
    )

    Write-Host "[INFO] Enviando reporte al recurso compartido de red..." -ForegroundColor Cyan

    try {
        if (-not (Test-Path $ZipFile)) {
            Write-Host "[ERROR] El archivo ZIP no existe: $ZipFile" -ForegroundColor Red
            return $false
        }

        $networkPath = $Config.NetworkShare.Path
        $requiresAuth = $Config.NetworkShare.RequiresAuth

        # Mapear unidad de red si requiere autenticación
        $driveMapped = $false
        $driveLetter = $null

        if ($requiresAuth) {
            Write-Host "[INFO] Autenticando en el recurso compartido..." -ForegroundColor Gray

            # Buscar una letra de unidad disponible
            $availableDrives = 90..65 | ForEach-Object { [char]$_ } | Where-Object {
                -not (Test-Path "${_}:\")
            }
            $driveLetter = $availableDrives[0]

            $username = $Config.NetworkShare.Username
            $password = $Config.NetworkShare.Password
            $securePassword = ConvertTo-SecureString $password -AsPlainText -Force
            $credential = New-Object System.Management.Automation.PSCredential($username, $securePassword)

            try {
                New-PSDrive -Name $driveLetter -PSProvider FileSystem -Root $networkPath -Credential $credential -ErrorAction Stop | Out-Null
                $driveMapped = $true
                $targetPath = "${driveLetter}:\"
                Write-Host "[OK] Autenticación exitosa" -ForegroundColor Green
            }
            catch {
                Write-Host "[ERROR] No se pudo mapear el recurso compartido: $($_.Exception.Message)" -ForegroundColor Red
                return $false
            }
        }
        else {
            $targetPath = $networkPath
        }

        # Crear carpeta del cliente si no existe
        $clientFolder = Join-Path $targetPath $ClientName
        if (-not (Test-Path $clientFolder)) {
            Write-Host "[INFO] Creando carpeta del cliente: $ClientName" -ForegroundColor Gray
            New-Item -ItemType Directory -Path $clientFolder -Force | Out-Null
        }

        # Copiar archivo
        $destination = Join-Path $clientFolder (Split-Path $ZipFile -Leaf)
        Write-Host "[INFO] Copiando archivo al servidor..." -ForegroundColor Gray
        Copy-Item -Path $ZipFile -Destination $destination -Force

        if (Test-Path $destination) {
            Write-Host "[OK] Reporte enviado exitosamente al recurso compartido" -ForegroundColor Green
            Write-Host "     Ubicación: $destination" -ForegroundColor Gray

            # Eliminar archivo local
            Remove-Item $ZipFile -Force
            Write-Host "[INFO] Archivo local eliminado" -ForegroundColor Gray

            return $true
        }
        else {
            Write-Host "[ERROR] No se pudo verificar la copia del archivo" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] Error al enviar al recurso compartido: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
    finally {
        # Desmontar unidad de red si fue mapeada
        if ($driveMapped -and $driveLetter) {
            try {
                Remove-PSDrive -Name $driveLetter -Force -ErrorAction SilentlyContinue
                Write-Host "[INFO] Unidad de red desmontada" -ForegroundColor Gray
            }
            catch {
                # Ignorar errores al desmontar
            }
        }
    }
}

Export-ModuleMember -Function Send-ToNetworkShare
