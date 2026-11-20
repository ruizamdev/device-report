using System;
using System.Management;
using DeviceReport.Models;

namespace DeviceReport.Collectors;

public static class UserCollector
{
    public static UserOsInfo Collect(Action<string> log)
    {
        var info = new UserOsInfo
        {
            Architecture = Environment.Is64BitOperatingSystem ? "64-bit" : "32-bit",
            DomainOrWorkgroup = Environment.UserDomainName
        };

        log("  • Sistema operativo y tiempo de actividad...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Caption, Version, BuildNumber, LastBootUpTime FROM Win32_OperatingSystem").Get())
        {
            info.OsName = obj["Caption"]?.ToString()?.Trim() ?? string.Empty;
            info.OsVersion = obj["Version"]?.ToString()?.Trim() ?? string.Empty;
            info.OsBuild = obj["BuildNumber"]?.ToString()?.Trim() ?? string.Empty;

            string? bootStr = obj["LastBootUpTime"]?.ToString();
            if (!string.IsNullOrEmpty(bootStr))
            {
                DateTime boot = ManagementDateTimeConverter.ToDateTime(bootStr);
                info.LastBootTime = boot;
                TimeSpan up = DateTime.Now - boot;
                info.Uptime = $"{(int)up.TotalDays}d {up.Hours}h {up.Minutes}m";
            }
        }

        return info;
    }
}
