using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Management;
using DeviceReport.Models;
using Microsoft.Win32;

namespace DeviceReport.Collectors;

public static class SoftwareCollector
{
    private static readonly string[] UninstallPaths =
    {
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    };

    public static SoftwareInfo Collect(Action<string> log)
    {
        var info = new SoftwareInfo();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        log("  • Programas instalados...");
        ReadUninstallHive(RegistryHive.LocalMachine, seen, info.InstalledPrograms);
        ReadUninstallHive(RegistryHive.CurrentUser, seen, info.InstalledPrograms);
        info.InstalledPrograms.Sort((a, b) => string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase));

        log("  • Actualizaciones recientes de Windows...");
        try
        {
            foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT HotFixID, InstalledOn FROM Win32_QuickFixEngineering").Get())
            {
                string? id = obj["HotFixID"]?.ToString();
                string? date = obj["InstalledOn"]?.ToString();
                if (!string.IsNullOrEmpty(id))
                    info.RecentUpdates.Add(string.IsNullOrEmpty(date) ? id : $"{id} ({date})");
            }
            if (info.RecentUpdates.Count > 25)
                info.RecentUpdates = info.RecentUpdates.Take(25).ToList();
        }
        catch
        {
            // Ignorar si WMI de actualizaciones no responde
        }

        log("  • Servicios y procesos...");
        try
        {
            info.RunningServicesCount = new ManagementObjectSearcher("SELECT Name FROM Win32_Service WHERE State='Running'").Get().Count;
        }
        catch { }

        try
        {
            info.ActiveProcessesCount = Process.GetProcesses().Length;
        }
        catch { }

        return info;
    }

    private static void ReadUninstallHive(RegistryHive hive, HashSet<string> seen, List<InstalledProgramInfo> target)
    {
        using var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Registry64);
        foreach (string path in UninstallPaths)
        {
            using var key = baseKey.OpenSubKey(path);
            if (key == null) continue;

            foreach (string subName in key.GetSubKeyNames())
            {
                using var sub = key.OpenSubKey(subName);
                string? name = sub?.GetValue("DisplayName")?.ToString()?.Trim();
                if (string.IsNullOrEmpty(name)) continue;

                string version = sub?.GetValue("DisplayVersion")?.ToString()?.Trim() ?? string.Empty;
                string publisher = sub?.GetValue("Publisher")?.ToString()?.Trim() ?? string.Empty;
                string dedupKey = $"{name}|{version}";
                if (seen.Add(dedupKey))
                {
                    target.Add(new InstalledProgramInfo
                    {
                        Name = name,
                        Version = version,
                        Publisher = publisher
                    });
                }
            }
        }
    }
}
