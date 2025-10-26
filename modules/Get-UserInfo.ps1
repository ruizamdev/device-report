function Get-UserInfo {
    <#
    .SYNOPSIS
    Recopila información del usuario y del sistema operativo.

    .DESCRIPTION
    Obtiene información sobre:
    - Usuario actual
    - Sistema operativo
    - Configuración regional
    - Variables de entorno
    - Perfiles de usuario
    - Información de dominio/workgroup

    .EXAMPLE
    $userInfo = Get-UserInfo
    #>

    [CmdletBinding()]
    param()

    Write-Host "[INFO] Recopilando información de usuario..." -ForegroundColor Cyan

    $userInfo = @{
        CurrentUser = $null
        OperatingSystem = $null
        Environment = $null
        UserProfiles = $null
        TimeZone = $null
        TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    try {
        # Usuario actual
        Write-Host "  - Usuario actual..." -ForegroundColor Gray
        $userInfo.CurrentUser = @{
            UserName = $env:USERNAME
            UserDomain = $env:USERDOMAIN
            UserProfile = $env:USERPROFILE
            ComputerName = $env:COMPUTERNAME
            LogonServer = $env:LOGONSERVER
        }

        # Sistema operativo
        Write-Host "  - Sistema operativo..." -ForegroundColor Gray
        $os = Get-CimInstance -ClassName Win32_OperatingSystem
        $userInfo.OperatingSystem = @{
            Caption = $os.Caption
            Version = $os.Version
            BuildNumber = $os.BuildNumber
            Architecture = $os.OSArchitecture
            SerialNumber = $os.SerialNumber
            InstallDate = $os.InstallDate
            LastBootUpTime = $os.LastBootUpTime
            LocalDateTime = $os.LocalDateTime
            Manufacturer = $os.Manufacturer
            RegisteredUser = $os.RegisteredUser
            Organization = $os.Organization
            SystemDirectory = $os.SystemDirectory
            WindowsDirectory = $os.WindowsDirectory
            FreePhysicalMemory = $os.FreePhysicalMemory
            TotalVisibleMemorySize = $os.TotalVisibleMemorySize
        }

        # Configuración regional y zona horaria
        Write-Host "  - Configuración regional..." -ForegroundColor Gray
        $userInfo.TimeZone = Get-TimeZone | Select-Object Id, DisplayName, StandardName, BaseUtcOffset

        # Variables de entorno relevantes
        Write-Host "  - Variables de entorno..." -ForegroundColor Gray
        $userInfo.Environment = @{
            PATH = $env:PATH
            TEMP = $env:TEMP
            SystemRoot = $env:SystemRoot
            ProgramFiles = $env:ProgramFiles
            ProgramFilesX86 = ${env:ProgramFiles(x86)}
            CommonProgramFiles = $env:CommonProgramFiles
            ProcessorArchitecture = $env:PROCESSOR_ARCHITECTURE
            NumberOfProcessors = $env:NUMBER_OF_PROCESSORS
        }

        # Perfiles de usuario en el sistema
        Write-Host "  - Perfiles de usuario..." -ForegroundColor Gray
        $userInfo.UserProfiles = Get-CimInstance -ClassName Win32_UserProfile |
            Where-Object { -not $_.Special } |
            Select-Object LocalPath, LastUseTime, Loaded, SID

        Write-Host "[OK] Información de usuario recopilada" -ForegroundColor Green
        return $userInfo
    }
    catch {
        Write-Host "[ERROR] Error al recopilar información de usuario: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Export-ModuleMember -Function Get-UserInfo
