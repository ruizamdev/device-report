using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Management;
using System.Net.Http;
using System.Text.Json;
using DeviceReport.Models;
using DeviceReport.Services;

namespace DeviceReport.Collectors;

public static class DiskHealthCollector
{
    private const string SmartmontoolsLatestApi = "https://api.github.com/repos/smartmontools/smartmontools/releases/latest";

    public static (List<DiskHealthInfo> Disks, string OverallStatus) Collect(SmartCtlSettings settings, Action<string> log)
    {
        var results = new List<DiskHealthInfo>();
        string? smartctlPath = ResolveSmartCtlPath(settings, log);

        if (!string.IsNullOrEmpty(smartctlPath))
        {
            log($"  • Ejecutando smartctl ({Path.GetFileName(smartctlPath)})...");
            results = CollectViaSmartCtl(smartctlPath, log);
        }

        if (results.Count == 0)
        {
            log("  • Usando diagnóstico WMI de respaldo (smartctl no disponible o sin discos detectados)...");
            results = CollectViaWmiFallback();
        }

        string overall = ComputeOverallStatus(results);
        return (results, overall);
    }

    private static string? ResolveSmartCtlPath(SmartCtlSettings settings, Action<string> log)
    {
        string configured = Path.IsPathRooted(settings.ExecutablePath)
            ? settings.ExecutablePath
            : Path.Combine(AppContext.BaseDirectory, settings.ExecutablePath);

        if (File.Exists(configured))
            return configured;

        // Buscar en PATH
        string? pathEnv = Environment.GetEnvironmentVariable("PATH");
        if (!string.IsNullOrEmpty(pathEnv))
        {
            foreach (string dir in pathEnv.Split(Path.PathSeparator))
            {
                string candidate = Path.Combine(dir.Trim(), "smartctl.exe");
                if (File.Exists(candidate))
                    return candidate;
            }
        }

        if (!settings.AutoDownload)
            return null;

        try
        {
            log("  • smartctl.exe no encontrado; descargando smartmontools oficial...");
            return DownloadSmartCtl(configured, log);
        }
        catch (Exception ex)
        {
            log($"  • No se pudo descargar smartctl.exe ({ex.Message}).");
            return null;
        }
    }

    private static string? DownloadSmartCtl(string destinationExe, Action<string> log)
    {
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(45) };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("DeviceReport-Siscom/2.0");

        string releaseJson = http.GetStringAsync(SmartmontoolsLatestApi).GetAwaiter().GetResult();
        using var doc = JsonDocument.Parse(releaseJson);
        if (!doc.RootElement.TryGetProperty("assets", out var assets))
            return null;

        string? zipUrl = null;
        foreach (var asset in assets.EnumerateArray())
        {
            string? name = asset.GetProperty("name").GetString();
            if (name != null && name.Contains("win", StringComparison.OrdinalIgnoreCase) && name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
            {
                zipUrl = asset.GetProperty("browser_download_url").GetString();
                break;
            }
        }

        if (string.IsNullOrEmpty(zipUrl))
            return null;

        byte[] zipBytes = http.GetByteArrayAsync(zipUrl).GetAwaiter().GetResult();
        string destDir = Path.GetDirectoryName(destinationExe) ?? AppContext.BaseDirectory;
        Directory.CreateDirectory(destDir);

        using var ms = new MemoryStream(zipBytes);
        using var archive = new ZipArchive(ms, ZipArchiveMode.Read);
        foreach (var entry in archive.Entries)
        {
            if (entry.Name.Equals("smartctl.exe", StringComparison.OrdinalIgnoreCase))
            {
                entry.ExtractToFile(destinationExe, overwrite: true);
                log("  • smartctl.exe descargado correctamente.");
                return destinationExe;
            }
        }

        return null;
    }

    private static List<DiskHealthInfo> CollectViaSmartCtl(string smartctlPath, Action<string> log)
    {
        var list = new List<DiskHealthInfo>();
        string? scanJson = RunSmartCtl(smartctlPath, "--scan --json");
        if (string.IsNullOrWhiteSpace(scanJson))
            return list;

        var devices = new List<(string Name, string? Type)>();
        try
        {
            using var scanDoc = JsonDocument.Parse(scanJson);
            if (scanDoc.RootElement.TryGetProperty("devices", out var devs))
            {
                foreach (var d in devs.EnumerateArray())
                {
                    string? name = d.TryGetProperty("name", out var n) ? n.GetString() : null;
                    string? type = d.TryGetProperty("type", out var t) ? t.GetString() : null;
                    if (!string.IsNullOrEmpty(name))
                        devices.Add((name, type));
                }
            }
        }
        catch (Exception ex)
        {
            log($"  • Error leyendo --scan de smartctl: {ex.Message}");
            return list;
        }

        foreach (var (devName, devType) in devices)
        {
            string args = string.IsNullOrEmpty(devType)
                ? $"-a --json \"{devName}\""
                : $"-a --json -d {devType} \"{devName}\"";
            string? detailJson = RunSmartCtl(smartctlPath, args);
            if (string.IsNullOrWhiteSpace(detailJson))
                continue;

            try
            {
                var info = ParseSmartCtlDetail(devName, detailJson);
                list.Add(info);
            }
            catch (Exception ex)
            {
                log($"  • Error parseando disco {devName}: {ex.Message}");
            }
        }

        return list;
    }

    public static DiskHealthInfo ParseSmartCtlDetail(string deviceName, string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        var info = new DiskHealthInfo
        {
            Device = deviceName,
            Source = "smartctl",
            Model = GetString(root, "model_name") ?? GetString(root, "scsi_model_name") ?? "Disco desconocido",
            Serial = GetString(root, "serial_number") ?? string.Empty,
            Protocol = root.TryGetProperty("device", out var devObj) ? (GetString(devObj, "protocol") ?? GetString(devObj, "type") ?? string.Empty) : string.Empty
        };

        if (root.TryGetProperty("user_capacity", out var cap) && cap.TryGetProperty("bytes", out var capBytes) && capBytes.TryGetInt64(out long bytes))
            info.CapacityGb = Math.Round(bytes / (1024.0 * 1024.0 * 1024.0), 1);

        if (root.TryGetProperty("smart_status", out var smart) && smart.TryGetProperty("passed", out var passed) && (passed.ValueKind == JsonValueKind.True || passed.ValueKind == JsonValueKind.False))
            info.SmartPassed = passed.GetBoolean();

        if (root.TryGetProperty("temperature", out var temp) && temp.TryGetProperty("current", out var currTemp) && currTemp.TryGetInt32(out int tVal))
            info.TemperatureC = tVal;

        if (root.TryGetProperty("power_on_time", out var pot) && pot.TryGetProperty("hours", out var hrs) && hrs.TryGetInt64(out long hVal))
            info.PowerOnHours = hVal;

        // Atributos SATA
        if (root.TryGetProperty("ata_smart_attributes", out var ata) && ata.TryGetProperty("table", out var table))
        {
            foreach (var attr in table.EnumerateArray())
            {
                int id = attr.TryGetProperty("id", out var idEl) && idEl.TryGetInt32(out int idV) ? idV : -1;
                long raw = attr.TryGetProperty("raw", out var rEl) && rEl.TryGetProperty("value", out var rv) && rv.TryGetInt64(out long rVal) ? rVal : 0;
                if (id == 5) info.ReallocatedSectors = raw;
                if (id == 197) info.PendingSectors = raw;
            }
        }

        // Atributos NVMe
        int? nvmeCritical = null;
        long? nvmeMediaErrors = null;
        if (root.TryGetProperty("nvme_smart_health_information_log", out var nvme))
        {
            if (nvme.TryGetProperty("percentage_used", out var pu) && pu.TryGetInt32(out int puVal))
                info.WearPercent = puVal;
            if (nvme.TryGetProperty("critical_warning", out var cw) && cw.TryGetInt32(out int cwVal))
                nvmeCritical = cwVal;
            if (nvme.TryGetProperty("media_errors", out var me) && me.TryGetInt64(out long meVal))
                nvmeMediaErrors = meVal;
        }

        // Clasificación de salud
        var reasons = new List<string>();
        bool isCritical = false;
        bool isWarning = false;

        if (info.SmartPassed == false)
        {
            isCritical = true;
            reasons.Add("SMART FAILED");
        }
        if (nvmeCritical.HasValue && nvmeCritical.Value > 0)
        {
            isCritical = true;
            reasons.Add($"NVMe critical_warning={nvmeCritical.Value}");
        }
        if ((info.PendingSectors ?? 0) > 0)
        {
            isCritical = true;
            reasons.Add($"Sectores pendientes: {info.PendingSectors}");
        }
        if ((info.ReallocatedSectors ?? 0) > 10)
        {
            isCritical = true;
            reasons.Add($"Sectores reasignados altos: {info.ReallocatedSectors}");
        }
        else if ((info.ReallocatedSectors ?? 0) > 0)
        {
            isWarning = true;
            reasons.Add($"Sectores reasignados: {info.ReallocatedSectors}");
        }
        if ((nvmeMediaErrors ?? 0) > 0)
        {
            isWarning = true;
            reasons.Add($"Errores de medio NVMe: {nvmeMediaErrors}");
        }
        if (info.WearPercent.HasValue && info.WearPercent.Value >= 90)
        {
            isCritical = true;
            reasons.Add($"Desgaste SSD crítico: {info.WearPercent}%");
        }
        else if (info.WearPercent.HasValue && info.WearPercent.Value >= 75)
        {
            isWarning = true;
            reasons.Add($"Desgaste SSD elevado: {info.WearPercent}%");
        }
        if (info.TemperatureC.HasValue && info.TemperatureC.Value >= 65)
        {
            isCritical = true;
            reasons.Add($"Temperatura crítica: {info.TemperatureC}°C");
        }
        else if (info.TemperatureC.HasValue && info.TemperatureC.Value >= 55)
        {
            isWarning = true;
            reasons.Add($"Temperatura elevada: {info.TemperatureC}°C");
        }

        info.Status = isCritical ? "CRITICAL"
            : isWarning ? "WARNING"
            : (info.SmartPassed == true ? "OK" : "UNKNOWN");

        info.Summary = reasons.Count > 0
            ? string.Join("; ", reasons)
            : (info.Status == "OK" ? "Saludable (SMART PASSED)" : "Estado no determinado");

        return info;
    }

    private static List<DiskHealthInfo> CollectViaWmiFallback()
    {
        var list = new List<DiskHealthInfo>();
        try
        {
            var predictMap = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
            try
            {
                foreach (ManagementObject obj in new ManagementObjectSearcher(@"root\WMI", "SELECT InstanceName, PredictFailure FROM MSStorageDriver_FailurePredictStatus").Get())
                {
                    string? inst = obj["InstanceName"]?.ToString();
                    bool fail = obj["PredictFailure"] is bool b && b;
                    if (!string.IsNullOrEmpty(inst))
                        predictMap[inst] = fail;
                }
            }
            catch { }

            foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT DeviceID, Model, SerialNumber, InterfaceType, Size, Status, PNPDeviceID FROM Win32_DiskDrive").Get())
            {
                double capGb = ulong.TryParse(obj["Size"]?.ToString(), out ulong b) ? Math.Round(b / (1024.0 * 1024.0 * 1024.0), 1) : 0;
                string wmiStatus = obj["Status"]?.ToString() ?? "OK";
                string pnp = obj["PNPDeviceID"]?.ToString() ?? string.Empty;
                bool predictFail = predictMap.Any(kv => kv.Key.Contains(pnp, StringComparison.OrdinalIgnoreCase) && kv.Value);

                bool ok = !predictFail && wmiStatus.Equals("OK", StringComparison.OrdinalIgnoreCase);
                list.Add(new DiskHealthInfo
                {
                    Device = obj["DeviceID"]?.ToString() ?? string.Empty,
                    Model = obj["Model"]?.ToString()?.Trim() ?? "Disco",
                    Serial = obj["SerialNumber"]?.ToString()?.Trim() ?? string.Empty,
                    Protocol = obj["InterfaceType"]?.ToString() ?? string.Empty,
                    CapacityGb = capGb,
                    SmartPassed = ok,
                    Status = predictFail ? "CRITICAL" : (ok ? "OK" : "WARNING"),
                    Source = "WMI",
                    Summary = predictFail ? "WMI PredictFailure activo" : $"WMI Status: {wmiStatus}"
                });
            }
        }
        catch { }

        return list;
    }

    public static string ComputeOverallStatus(List<DiskHealthInfo> disks)
    {
        if (disks.Count == 0) return "UNKNOWN";
        if (disks.Any(d => d.Status == "CRITICAL")) return "CRITICAL";
        if (disks.Any(d => d.Status == "WARNING")) return "WARNING";
        if (disks.Any(d => d.Status == "OK")) return "OK";
        return "UNKNOWN";
    }

    private static string? RunSmartCtl(string exePath, string arguments)
    {
        try
        {
            var psi = new ProcessStartInfo(exePath, arguments)
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using var proc = Process.Start(psi);
            if (proc == null) return null;
            string output = proc.StandardOutput.ReadToEnd();
            proc.WaitForExit(15000);
            return output;
        }
        catch
        {
            return null;
        }
    }

    private static string? GetString(JsonElement el, string prop)
        => el.TryGetProperty(prop, out var val) && val.ValueKind == JsonValueKind.String ? val.GetString() : null;
}
