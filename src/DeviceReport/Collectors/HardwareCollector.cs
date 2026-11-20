using System;
using System.Management;
using DeviceReport.Models;

namespace DeviceReport.Collectors;

public static class HardwareCollector
{
    public static HardwareInfo Collect(Action<string> log)
    {
        var info = new HardwareInfo();

        log("  • Sistema y placa base...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Manufacturer, Model, TotalPhysicalMemory FROM Win32_ComputerSystem").Get())
        {
            info.Manufacturer = obj["Manufacturer"]?.ToString()?.Trim() ?? string.Empty;
            info.Model = obj["Model"]?.ToString()?.Trim() ?? string.Empty;
            if (ulong.TryParse(obj["TotalPhysicalMemory"]?.ToString(), out ulong bytes))
                info.TotalRamGb = Math.Round(bytes / (1024.0 * 1024.0 * 1024.0), 2);
        }

        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT SerialNumber, SMBIOSBIOSVersion FROM Win32_BIOS").Get())
        {
            info.SerialNumber = obj["SerialNumber"]?.ToString()?.Trim() ?? string.Empty;
            info.BiosVersion = obj["SMBIOSBIOSVersion"]?.ToString()?.Trim() ?? string.Empty;
        }

        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Manufacturer, Product FROM Win32_BaseBoard").Get())
        {
            string mfg = obj["Manufacturer"]?.ToString()?.Trim() ?? string.Empty;
            string prod = obj["Product"]?.ToString()?.Trim() ?? string.Empty;
            info.Motherboard = $"{mfg} {prod}".Trim();
        }

        log("  • Procesador...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Name, NumberOfCores, NumberOfLogicalProcessors FROM Win32_Processor").Get())
        {
            info.CpuName = obj["Name"]?.ToString()?.Trim() ?? string.Empty;
            if (int.TryParse(obj["NumberOfCores"]?.ToString(), out int cores))
                info.CpuCores += cores;
            if (int.TryParse(obj["NumberOfLogicalProcessors"]?.ToString(), out int logical))
                info.CpuLogicalProcessors += logical;
        }

        log("  • Módulos RAM...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT DeviceLocator, Capacity, Speed, Manufacturer, PartNumber FROM Win32_PhysicalMemory").Get())
        {
            double capGb = ulong.TryParse(obj["Capacity"]?.ToString(), out ulong b)
                ? Math.Round(b / (1024.0 * 1024.0 * 1024.0), 2)
                : 0;
            int.TryParse(obj["Speed"]?.ToString(), out int speed);
            info.RamModules.Add(new RamModuleInfo
            {
                Slot = obj["DeviceLocator"]?.ToString()?.Trim() ?? string.Empty,
                CapacityGb = capGb,
                SpeedMhz = speed,
                Manufacturer = obj["Manufacturer"]?.ToString()?.Trim() ?? string.Empty,
                PartNumber = obj["PartNumber"]?.ToString()?.Trim() ?? string.Empty
            });
        }

        log("  • Tarjetas de video y volúmenes...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Name FROM Win32_VideoController").Get())
        {
            string? name = obj["Name"]?.ToString()?.Trim();
            if (!string.IsNullOrEmpty(name))
                info.Gpus.Add(name);
        }

        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT DeviceID, VolumeName, FileSystem, Size, FreeSpace FROM Win32_LogicalDisk WHERE DriveType=3").Get())
        {
            double totalGb = ulong.TryParse(obj["Size"]?.ToString(), out ulong t) ? Math.Round(t / (1024.0 * 1024.0 * 1024.0), 2) : 0;
            double freeGb = ulong.TryParse(obj["FreeSpace"]?.ToString(), out ulong f) ? Math.Round(f / (1024.0 * 1024.0 * 1024.0), 2) : 0;
            info.Volumes.Add(new LogicalVolumeInfo
            {
                DriveLetter = obj["DeviceID"]?.ToString() ?? string.Empty,
                Label = obj["VolumeName"]?.ToString() ?? string.Empty,
                FileSystem = obj["FileSystem"]?.ToString() ?? string.Empty,
                TotalGb = totalGb,
                FreeGb = freeGb
            });
        }

        return info;
    }
}
