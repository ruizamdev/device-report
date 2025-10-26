function Send-ToOneDrive {
    <#
    .SYNOPSIS
    Envía el archivo comprimido a OneDrive usando Microsoft Graph API.

    .DESCRIPTION
    Sube el archivo ZIP de reportes a OneDrive utilizando Microsoft Graph API.
    Requiere configuración previa de una aplicación en Azure AD.

    .PARAMETER ZipFile
    Ruta del archivo ZIP a enviar.

    .PARAMETER ClientName
    Nombre del cliente (usado para organizar en carpetas en OneDrive).

    .PARAMETER Config
    Objeto de configuración con credenciales de Azure AD.

    .EXAMPLE
    Send-ToOneDrive -ZipFile "C:\Temp\reporte.zip" -ClientName "Juan Perez" -Config $config
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

    Write-Host "[INFO] Enviando reporte a OneDrive..." -ForegroundColor Cyan

    try {
        if (-not (Test-Path $ZipFile)) {
            Write-Host "[ERROR] El archivo ZIP no existe: $ZipFile" -ForegroundColor Red
            return $false
        }

        # Validar configuración
        if (-not $Config.OneDrive.ClientId -or $Config.OneDrive.ClientId -eq "YOUR_CLIENT_ID_HERE") {
            Write-Host "[ERROR] ClientId no configurado en config.json" -ForegroundColor Red
            Write-Host "        Por favor, configura tu aplicación de Azure AD siguiendo AZURE_SETUP.md" -ForegroundColor Yellow
            return $false
        }

        if (-not $Config.OneDrive.ClientSecret -or $Config.OneDrive.ClientSecret -eq "YOUR_CLIENT_SECRET_HERE") {
            Write-Host "[ERROR] ClientSecret no configurado en config.json" -ForegroundColor Red
            Write-Host "        Por favor, configura tu aplicación de Azure AD siguiendo AZURE_SETUP.md" -ForegroundColor Yellow
            return $false
        }

        # Obtener token de acceso
        Write-Host "[INFO] Autenticando con Microsoft Graph API..." -ForegroundColor Gray
        $token = Get-GraphAccessToken -Config $Config

        if (-not $token) {
            Write-Host "[ERROR] No se pudo obtener el token de acceso" -ForegroundColor Red
            return $false
        }

        # Crear carpeta en OneDrive si no existe
        $uploadFolder = $Config.OneDrive.UploadFolder
        $folderPath = "$uploadFolder/$ClientName"

        Write-Host "[INFO] Verificando carpeta en OneDrive: $folderPath" -ForegroundColor Gray
        $folderId = Ensure-OneDriveFolder -FolderPath $folderPath -Token $token

        if (-not $folderId) {
            Write-Host "[ERROR] No se pudo crear/verificar la carpeta en OneDrive" -ForegroundColor Red
            return $false
        }

        # Subir archivo
        Write-Host "[INFO] Subiendo archivo a OneDrive..." -ForegroundColor Gray
        $fileName = Split-Path $ZipFile -Leaf
        $uploadSuccess = Upload-FileToOneDrive -FilePath $ZipFile -FileName $fileName -FolderId $folderId -Token $token

        if ($uploadSuccess) {
            Write-Host "[OK] Reporte enviado exitosamente a OneDrive" -ForegroundColor Green
            Write-Host "     Carpeta: $folderPath" -ForegroundColor Gray

            # Eliminar archivo local
            Remove-Item $ZipFile -Force
            Write-Host "[INFO] Archivo local eliminado" -ForegroundColor Gray

            return $true
        }
        else {
            Write-Host "[ERROR] No se pudo subir el archivo a OneDrive" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] Error al enviar a OneDrive: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Get-GraphAccessToken {
    param([PSCustomObject]$Config)

    try {
        $tenantId = $Config.OneDrive.TenantId
        $clientId = $Config.OneDrive.ClientId
        $clientSecret = $Config.OneDrive.ClientSecret

        $tokenUrl = "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token"

        $body = @{
            client_id     = $clientId
            client_secret = $clientSecret
            scope         = "https://graph.microsoft.com/.default"
            grant_type    = "client_credentials"
        }

        $response = Invoke-RestMethod -Uri $tokenUrl -Method Post -Body $body -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop

        return $response.access_token
    }
    catch {
        Write-Host "[ERROR] Error al obtener token: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "[ERROR] Respuesta del servidor: $responseBody" -ForegroundColor Red
        }
        return $null
    }
}

function Ensure-OneDriveFolder {
    param(
        [string]$FolderPath,
        [string]$Token
    )

    try {
        $headers = @{
            Authorization = "Bearer $Token"
            "Content-Type" = "application/json"
        }

        # Dividir la ruta en partes
        $folders = $FolderPath -split '/' | Where-Object { $_ -ne "" }
        $currentPath = "root"

        foreach ($folder in $folders) {
            # Verificar si la carpeta existe
            $checkUrl = "https://graph.microsoft.com/v1.0/me/drive/$currentPath/children"
            $children = Invoke-RestMethod -Uri $checkUrl -Headers $headers -Method Get -ErrorAction SilentlyContinue

            $existingFolder = $children.value | Where-Object { $_.name -eq $folder -and $_.folder }

            if ($existingFolder) {
                $currentPath = "items/$($existingFolder.id)"
            }
            else {
                # Crear la carpeta
                $createUrl = "https://graph.microsoft.com/v1.0/me/drive/$currentPath/children"
                $body = @{
                    name = $folder
                    folder = @{}
                    "@microsoft.graph.conflictBehavior" = "rename"
                } | ConvertTo-Json

                $newFolder = Invoke-RestMethod -Uri $createUrl -Headers $headers -Method Post -Body $body -ErrorAction Stop
                $currentPath = "items/$($newFolder.id)"
            }
        }

        # Obtener el ID de la carpeta final
        $finalUrl = "https://graph.microsoft.com/v1.0/me/drive/$currentPath"
        $finalFolder = Invoke-RestMethod -Uri $finalUrl -Headers $headers -Method Get

        return $finalFolder.id
    }
    catch {
        Write-Host "[ERROR] Error al crear carpeta: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

function Upload-FileToOneDrive {
    param(
        [string]$FilePath,
        [string]$FileName,
        [string]$FolderId,
        [string]$Token
    )

    try {
        $headers = @{
            Authorization = "Bearer $Token"
            "Content-Type" = "application/octet-stream"
        }

        $fileSize = (Get-Item $FilePath).Length
        $fileSizeMB = [math]::Round($fileSize / 1MB, 2)

        # Para archivos pequeños (< 4MB), usar carga simple
        if ($fileSize -lt 4MB) {
            Write-Host "  - Tamaño del archivo: $fileSizeMB MB (carga simple)" -ForegroundColor Gray

            $uploadUrl = "https://graph.microsoft.com/v1.0/me/drive/items/${FolderId}:/${FileName}:/content"
            $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)

            $response = Invoke-RestMethod -Uri $uploadUrl -Headers $headers -Method Put -Body $fileBytes -ErrorAction Stop

            return $true
        }
        else {
            # Para archivos grandes (>= 4MB), usar sesión de carga
            Write-Host "  - Tamaño del archivo: $fileSizeMB MB (carga por sesión)" -ForegroundColor Gray

            # Crear sesión de carga
            $sessionUrl = "https://graph.microsoft.com/v1.0/me/drive/items/${FolderId}:/${FileName}:/createUploadSession"

            $sessionHeaders = @{
                Authorization = "Bearer $Token"
                "Content-Type" = "application/json"
            }

            $sessionBody = @{
                item = @{
                    "@microsoft.graph.conflictBehavior" = "rename"
                }
            } | ConvertTo-Json

            $session = Invoke-RestMethod -Uri $sessionUrl -Headers $sessionHeaders -Method Post -Body $sessionBody

            # Subir archivo en fragmentos
            $uploadUrl = $session.uploadUrl
            $chunkSize = 320KB * 10  # 3.2 MB por fragmento
            $fileStream = [System.IO.File]::OpenRead($FilePath)
            $buffer = New-Object byte[] $chunkSize
            $position = 0

            try {
                while ($position -lt $fileSize) {
                    $bytesRead = $fileStream.Read($buffer, 0, $chunkSize)
                    $chunk = $buffer[0..($bytesRead - 1)]

                    $rangeStart = $position
                    $rangeEnd = $position + $bytesRead - 1

                    $uploadHeaders = @{
                        "Content-Length" = $bytesRead
                        "Content-Range" = "bytes $rangeStart-$rangeEnd/$fileSize"
                    }

                    $progress = [math]::Round(($position / $fileSize) * 100, 1)
                    Write-Host "  - Progreso: $progress%" -ForegroundColor Gray

                    Invoke-RestMethod -Uri $uploadUrl -Headers $uploadHeaders -Method Put -Body $chunk -ErrorAction Stop | Out-Null

                    $position += $bytesRead
                }

                return $true
            }
            finally {
                $fileStream.Close()
            }
        }
    }
    catch {
        Write-Host "[ERROR] Error al subir archivo: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Export-ModuleMember -Function Send-ToOneDrive
