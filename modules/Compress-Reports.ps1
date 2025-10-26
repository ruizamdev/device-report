function Compress-Reports {
    <#
    .SYNOPSIS
    Comprime los reportes generados en un archivo ZIP.

    .DESCRIPTION
    Toma todos los archivos de reporte y los comprime en un único archivo ZIP
    con el nombre del cliente y timestamp.

    .PARAMETER ReportFiles
    Array de rutas de archivos a comprimir.

    .PARAMETER OutputPath
    Directorio donde se guardará el archivo ZIP.

    .PARAMETER ClientName
    Nombre del cliente (usado para nombrar el archivo ZIP).

    .EXAMPLE
    Compress-Reports -ReportFiles $files -OutputPath "C:\Temp" -ClientName "Juan Perez"
    #>

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [array]$ReportFiles,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [Parameter(Mandatory = $true)]
        [string]$ClientName
    )

    Write-Host "[INFO] Comprimiendo reportes..." -ForegroundColor Cyan

    try {
        if ($ReportFiles.Count -eq 0) {
            Write-Host "[WARN] No hay archivos para comprimir" -ForegroundColor Yellow
            return $null
        }

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $computerName = $env:COMPUTERNAME
        $userName = $env:USERNAME
        $zipFileName = "${ClientName}_${userName}-${computerName}_${timestamp}.zip"
        $zipPath = Join-Path $OutputPath $zipFileName

        # Eliminar archivo ZIP si ya existe
        if (Test-Path $zipPath) {
            Remove-Item $zipPath -Force
        }

        # Crear archivo ZIP usando .NET (compatible con PowerShell 5.0+)
        Add-Type -Assembly System.IO.Compression.FileSystem

        $compression = [System.IO.Compression.CompressionLevel]::Optimal
        $zipArchive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

        try {
            foreach ($file in $ReportFiles) {
                if (Test-Path $file) {
                    $fileName = Split-Path $file -Leaf
                    Write-Host "  - Agregando: $fileName" -ForegroundColor Gray
                    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file, $fileName, $compression) | Out-Null
                }
            }
        }
        finally {
            $zipArchive.Dispose()
        }

        # Verificar que el archivo se creó correctamente
        if (Test-Path $zipPath) {
            $zipSize = (Get-Item $zipPath).Length
            $zipSizeKB = [math]::Round($zipSize / 1KB, 2)
            Write-Host "[OK] Reportes comprimidos exitosamente: $zipFileName ($zipSizeKB KB)" -ForegroundColor Green

            # Eliminar archivos temporales
            Write-Host "[INFO] Eliminando archivos temporales..." -ForegroundColor Gray
            foreach ($file in $ReportFiles) {
                if (Test-Path $file) {
                    Remove-Item $file -Force
                }
            }

            return $zipPath
        }
        else {
            Write-Host "[ERROR] No se pudo crear el archivo ZIP" -ForegroundColor Red
            return $null
        }
    }
    catch {
        Write-Host "[ERROR] Error al comprimir reportes: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Export-ModuleMember -Function Compress-Reports
