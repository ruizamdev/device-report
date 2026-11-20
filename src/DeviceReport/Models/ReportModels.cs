using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace DeviceReport.Models;

public sealed class DeviceReportData
{
    public string ClientName { get; set; } = string.Empty;
    public string Technician { get; set; } = string.Empty;
    public string Notes { get; set; } = string.Empty;
    public string Hostname { get; set; } = Environment.MachineName;
    public string Username { get; set; } = Environment.UserName;
    public DateTime CollectedAtUtc { get; set; } = DateTime.UtcNow;

    public HardwareInfo? Hardware { get; set; }
    public List<DiskHealthInfo> DisksHealth { get; set; } = new();
    public string DiskOverallStatus { get; set; } = "UNKNOWN";
    public UserOsInfo? UserOs { get; set; }
    public SoftwareInfo? Software { get; set; }
    public NetworkInfo? Network { get; set; }
}

public sealed class HardwareInfo
{
    public string Manufacturer { get; set; } = string.Empty;
    public string Model { get; set; } = string.Empty;
    public string SerialNumber { get; set; } = string.Empty;
    public string BiosVersion { get; set; } = string.Empty;
    public string Motherboard { get; set; } = string.Empty;
    public string CpuName { get; set; } = string.Empty;
    public int CpuCores { get; set; }
    public int CpuLogicalProcessors { get; set; }
    public double TotalRamGb { get; set; }
    public List<RamModuleInfo> RamModules { get; set; } = new();
    public List<string> Gpus { get; set; } = new();
    public List<LogicalVolumeInfo> Volumes { get; set; } = new();
}

public sealed class RamModuleInfo
{
    public string Slot { get; set; } = string.Empty;
    public double CapacityGb { get; set; }
    public int SpeedMhz { get; set; }
    public string Manufacturer { get; set; } = string.Empty;
    public string PartNumber { get; set; } = string.Empty;
}

public sealed class LogicalVolumeInfo
{
    public string DriveLetter { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string FileSystem { get; set; } = string.Empty;
    public double TotalGb { get; set; }
    public double FreeGb { get; set; }
}

public sealed class DiskHealthInfo
{
    [JsonPropertyName("device")]
    public string Device { get; set; } = string.Empty;

    [JsonPropertyName("model")]
    public string Model { get; set; } = string.Empty;

    [JsonPropertyName("serial")]
    public string Serial { get; set; } = string.Empty;

    [JsonPropertyName("protocol")]
    public string Protocol { get; set; } = string.Empty;

    [JsonPropertyName("capacity_gb")]
    public double CapacityGb { get; set; }

    [JsonPropertyName("smart_passed")]
    public bool? SmartPassed { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = "UNKNOWN"; // OK, WARNING, CRITICAL, UNKNOWN

    [JsonPropertyName("temperature_c")]
    public int? TemperatureC { get; set; }

    [JsonPropertyName("power_on_hours")]
    public long? PowerOnHours { get; set; }

    [JsonPropertyName("wear_percent")]
    public int? WearPercent { get; set; }

    [JsonPropertyName("reallocated_sectors")]
    public long? ReallocatedSectors { get; set; }

    [JsonPropertyName("pending_sectors")]
    public long? PendingSectors { get; set; }

    [JsonPropertyName("source")]
    public string Source { get; set; } = "smartctl";

    [JsonPropertyName("summary")]
    public string Summary { get; set; } = string.Empty;
}

public sealed class UserOsInfo
{
    public string OsName { get; set; } = string.Empty;
    public string OsVersion { get; set; } = string.Empty;
    public string OsBuild { get; set; } = string.Empty;
    public string Architecture { get; set; } = string.Empty;
    public string DomainOrWorkgroup { get; set; } = string.Empty;
    public string Uptime { get; set; } = string.Empty;
    public DateTime? LastBootTime { get; set; }
}

public sealed class SoftwareInfo
{
    public List<InstalledProgramInfo> InstalledPrograms { get; set; } = new();
    public List<string> RecentUpdates { get; set; } = new();
    public int RunningServicesCount { get; set; }
    public int ActiveProcessesCount { get; set; }
}

public sealed class InstalledProgramInfo
{
    public string Name { get; set; } = string.Empty;
    public string Version { get; set; } = string.Empty;
    public string Publisher { get; set; } = string.Empty;
}

public sealed class NetworkInfo
{
    public List<NetworkAdapterInfo> Adapters { get; set; } = new();
    public List<string> WifiProfiles { get; set; } = new();
}

public sealed class NetworkAdapterInfo
{
    public string Name { get; set; } = string.Empty;
    public string MacAddress { get; set; } = string.Empty;
    public string IpAddresses { get; set; } = string.Empty;
    public string Gateways { get; set; } = string.Empty;
    public string DnsServers { get; set; } = string.Empty;
}

public sealed class SummaryMetadata
{
    [JsonPropertyName("client_name")]
    public string ClientName { get; set; } = string.Empty;

    [JsonPropertyName("technician")]
    public string Technician { get; set; } = string.Empty;

    [JsonPropertyName("notes")]
    public string Notes { get; set; } = string.Empty;

    [JsonPropertyName("hostname")]
    public string Hostname { get; set; } = string.Empty;

    [JsonPropertyName("username")]
    public string Username { get; set; } = string.Empty;

    [JsonPropertyName("serial_number")]
    public string SerialNumber { get; set; } = string.Empty;

    [JsonPropertyName("manufacturer")]
    public string Manufacturer { get; set; } = string.Empty;

    [JsonPropertyName("model")]
    public string Model { get; set; } = string.Empty;

    [JsonPropertyName("os_name")]
    public string OsName { get; set; } = string.Empty;

    [JsonPropertyName("cpu")]
    public string Cpu { get; set; } = string.Empty;

    [JsonPropertyName("ram_gb")]
    public double RamGb { get; set; }

    [JsonPropertyName("disk_overall_status")]
    public string DiskOverallStatus { get; set; } = "UNKNOWN";

    [JsonPropertyName("disks")]
    public List<DiskHealthInfo> Disks { get; set; } = new();

    [JsonPropertyName("collected_at")]
    public string CollectedAt { get; set; } = string.Empty;
}
