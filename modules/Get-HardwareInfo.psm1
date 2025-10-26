function Get-HardwareInfo {
    <#
    .SYNOPSIS
    Recopila información detallada del hardware del equipo.

    .DESCRIPTION
    Utiliza comandos nativos de Windows para recopilar información sobre:
    - Sistema (Fabricante, Modelo, Número de serie)
    - BIOS/UEFI
    - Procesador
    - Memoria RAM
    - Discos duros y particiones
    - Placa base
    - Tarjeta de video

    .EXAMPLE
    $hwInfo = Get-HardwareInfo
    #>

    [CmdletBinding()]
    param()

    Write-Host "[INFO] Recopilando información de hardware..." -ForegroundColor Cyan

    $hardwareInfo = @{
        System = $null
        BIOS = $null
        Processor = $null
        Memory = $null
        Disks = $null
        Motherboard = $null
        VideoCard = $null
        TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    try {
        # Información del sistema
        Write-Host "  - Sistema..." -ForegroundColor Gray
        $hardwareInfo.System = Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object `
            Manufacturer, Model, TotalPhysicalMemory, NumberOfProcessors, NumberOfLogicalProcessors, `
            Domain, Workgroup, UserName, SystemType, PCSystemType

        # BIOS
        Write-Host "  - BIOS..." -ForegroundColor Gray
        $hardwareInfo.BIOS = Get-CimInstance -ClassName Win32_BIOS | Select-Object `
            Manufacturer, Name, SerialNumber, Version, ReleaseDate, SMBIOSBIOSVersion, SMBIOSMajorVersion, SMBIOSMinorVersion

        # Procesador
        Write-Host "  - Procesador..." -ForegroundColor Gray
        $hardwareInfo.Processor = Get-CimInstance -ClassName Win32_Processor | Select-Object `
            Name, Manufacturer, Description, MaxClockSpeed, NumberOfCores, NumberOfLogicalProcessors, `
            Architecture, ProcessorId, SocketDesignation, L2CacheSize, L3CacheSize

        # Memoria RAM
        Write-Host "  - Memoria RAM..." -ForegroundColor Gray
        $hardwareInfo.Memory = Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object `
            Manufacturer, PartNumber, SerialNumber, Capacity, Speed, ConfiguredClockSpeed, `
            DeviceLocator, FormFactor, MemoryType, SMBIOSMemoryType

        # Discos
        Write-Host "  - Discos..." -ForegroundColor Gray
        $hardwareInfo.Disks = Get-CimInstance -ClassName Win32_DiskDrive | Select-Object `
            Model, InterfaceType, MediaType, Size, Partitions, SerialNumber, Status

        # Particiones y volúmenes
        $hardwareInfo.LogicalDisks = Get-CimInstance -ClassName Win32_LogicalDisk | Select-Object `
            DeviceID, DriveType, FileSystem, Size, FreeSpace, VolumeName

        # Placa base
        Write-Host "  - Placa base..." -ForegroundColor Gray
        $hardwareInfo.Motherboard = Get-CimInstance -ClassName Win32_BaseBoard | Select-Object `
            Manufacturer, Product, SerialNumber, Version

        # Tarjeta de video
        Write-Host "  - Tarjeta de video..." -ForegroundColor Gray
        $hardwareInfo.VideoCard = Get-CimInstance -ClassName Win32_VideoController | Select-Object `
            Name, AdapterRAM, DriverVersion, VideoProcessor, VideoModeDescription, CurrentRefreshRate, `
            MaxRefreshRate, MinRefreshRate, VideoArchitecture

        Write-Host "[OK] Información de hardware recopilada" -ForegroundColor Green
        return $hardwareInfo
    }
    catch {
        Write-Host "[ERROR] Error al recopilar información de hardware: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Export-ModuleMember -Function Get-HardwareInfo
