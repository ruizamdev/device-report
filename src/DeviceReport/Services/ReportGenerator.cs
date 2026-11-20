using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using DeviceReport.Models;

namespace DeviceReport.Services;

public static class ReportGenerator
{
    private static readonly JsonSerializerOptions FullReportJsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false
    };

    public static (string ZipPath, string HtmlPath, SummaryMetadata Metadata) GenerateAndZip(DeviceReportData data)
    {
        string safeClient = Regex.Replace(data.ClientName.Trim(), @"[^A-Za-z0-9_-]", "_");
        if (string.IsNullOrEmpty(safeClient)) safeClient = "Cliente";
        string ts = DateTime.Now.ToString("yyyyMMdd_HHmmss");

        string rootTemp = Path.Combine(Path.GetTempPath(), "DeviceReports");
        string workDir = Path.Combine(rootTemp, $"{safeClient}_{data.Hostname}_{ts}");
        Directory.CreateDirectory(workDir);

        var metadata = new SummaryMetadata
        {
            ClientName = data.ClientName,
            Technician = data.Technician,
            Notes = data.Notes,
            Hostname = data.Hostname,
            Username = data.Username,
            SerialNumber = data.Hardware?.SerialNumber ?? string.Empty,
            Manufacturer = data.Hardware?.Manufacturer ?? string.Empty,
            Model = data.Hardware?.Model ?? string.Empty,
            OsName = data.UserOs?.OsName ?? string.Empty,
            Cpu = data.Hardware?.CpuName ?? string.Empty,
            RamGb = data.Hardware?.TotalRamGb ?? 0,
            DiskOverallStatus = data.DiskOverallStatus,
            Disks = data.DisksHealth,
            CollectedAt = data.CollectedAtUtc.ToString("o")
        };

        string jsonPath = Path.Combine(workDir, "summary.json");
        File.WriteAllText(jsonPath, JsonSerializer.Serialize(metadata, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);

        // Reporte completo en JSON (snake_case) para que el panel web pueda mostrar todo el detalle.
        string fullJsonPath = Path.Combine(workDir, "report.json");
        File.WriteAllText(fullJsonPath, JsonSerializer.Serialize(data, FullReportJsonOptions), new UTF8Encoding(false));

        string txtPath = Path.Combine(workDir, "reporte.txt");
        File.WriteAllText(txtPath, BuildTextReport(data), Encoding.UTF8);

        string htmlPath = Path.Combine(workDir, "reporte.html");
        File.WriteAllText(htmlPath, BuildHtmlReport(data), Encoding.UTF8);

        string zipPath = Path.Combine(rootTemp, $"{safeClient}_{data.Hostname}_{ts}.zip");
        if (File.Exists(zipPath)) File.Delete(zipPath);
        ZipFile.CreateFromDirectory(workDir, zipPath, CompressionLevel.Optimal, includeBaseDirectory: false);

        // Conservar una copia del HTML junto al ZIP por si se desea abrir localmente, borrar carpeta temporal
        string standaloneHtml = Path.Combine(rootTemp, $"{safeClient}_{data.Hostname}_{ts}.html");
        File.Copy(htmlPath, standaloneHtml, overwrite: true);
        try { Directory.Delete(workDir, recursive: true); } catch { }

        return (zipPath, standaloneHtml, metadata);
    }

    private static string BuildTextReport(DeviceReportData d)
    {
        var sb = new StringBuilder();
        sb.AppendLine("============================================================");
        sb.AppendLine("                  DEVICE REPORT - SISCOM                    ");
        sb.AppendLine("============================================================");
        sb.AppendLine($"Cliente:     {d.ClientName}");
        sb.AppendLine($"Técnico:     {d.Technician}");
        sb.AppendLine($"Equipo:      {d.Hostname} ({d.Username})");
        sb.AppendLine($"Fecha (UTC): {d.CollectedAtUtc:yyyy-MM-dd HH:mm:ss}");
        if (!string.IsNullOrWhiteSpace(d.Notes))
            sb.AppendLine($"Notas:       {d.Notes}");
        sb.AppendLine();

        sb.AppendLine($"--- SALUD DE DISCOS (Estado Global: {d.DiskOverallStatus}) ---");
        foreach (var disk in d.DisksHealth)
        {
            sb.AppendLine($"  [{disk.Status}] {disk.Model} ({disk.CapacityGb} GB, {disk.Protocol})");
            sb.AppendLine($"      Temp: {disk.TemperatureC?.ToString() ?? "N/A"}°C | Horas: {disk.PowerOnHours?.ToString() ?? "N/A"} | {disk.Summary}");
        }
        sb.AppendLine();

        if (d.Hardware != null)
        {
            sb.AppendLine("--- HARDWARE ---");
            sb.AppendLine($"Fabricante/Modelo: {d.Hardware.Manufacturer} {d.Hardware.Model}");
            sb.AppendLine($"Serie / BIOS:      {d.Hardware.SerialNumber} / {d.Hardware.BiosVersion}");
            sb.AppendLine($"Placa Base:        {d.Hardware.Motherboard}");
            sb.AppendLine($"CPU:               {d.Hardware.CpuName} ({d.Hardware.CpuCores}C/{d.Hardware.CpuLogicalProcessors}T)");
            sb.AppendLine($"RAM Total:         {d.Hardware.TotalRamGb} GB");
            foreach (var v in d.Hardware.Volumes)
                sb.AppendLine($"Volumen {v.DriveLetter} ({v.Label}): {v.FreeGb} GB libres de {v.TotalGb} GB ({v.FileSystem})");
            sb.AppendLine();
        }

        if (d.UserOs != null)
        {
            sb.AppendLine("--- SISTEMA OPERATIVO ---");
            sb.AppendLine($"SO:       {d.UserOs.OsName} ({d.UserOs.Architecture})");
            sb.AppendLine($"Versión:  {d.UserOs.OsVersion} Build {d.UserOs.OsBuild}");
            sb.AppendLine($"Uptime:   {d.UserOs.Uptime}");
            sb.AppendLine();
        }

        if (d.Network != null)
        {
            sb.AppendLine("--- RED ---");
            foreach (var a in d.Network.Adapters)
                sb.AppendLine($"  • {a.Name} | IP: {a.IpAddresses} | MAC: {a.MacAddress}");
            if (d.Network.WifiProfiles.Count > 0)
                sb.AppendLine($"Perfiles Wi-Fi: {string.Join(", ", d.Network.WifiProfiles)}");
            sb.AppendLine();
        }

        if (d.Software != null)
        {
            sb.AppendLine($"--- SOFTWARE ({d.Software.InstalledPrograms.Count} programas, {d.Software.RunningServicesCount} servicios, {d.Software.ActiveProcessesCount} procesos) ---");
            foreach (var p in d.Software.InstalledPrograms)
                sb.AppendLine($"  • {p.Name} {p.Version} ({p.Publisher})");
        }

        return sb.ToString();
    }

    private static string BuildHtmlReport(DeviceReportData d)
    {
        static string H(string? s) => WebUtility.HtmlEncode(s ?? string.Empty);

        string badgeColor = d.DiskOverallStatus switch
        {
            "OK" => "#16a34a",
            "WARNING" => "#d97706",
            "CRITICAL" => "#dc2626",
            _ => "#64748b"
        };

        var sb = new StringBuilder();
        sb.AppendLine("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>");
        sb.AppendLine($"<title>Reporte - {H(d.ClientName)} ({H(d.Hostname)})</title>");
        sb.AppendLine("<style>body{font-family:'Segoe UI',sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:24px;}");
        sb.AppendLine(".card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px;margin-bottom:18px;box-shadow:0 1px 3px rgba(0,0,0,.04);}");
        sb.AppendLine("h1{margin:0 0 6px;font-size:22px;}h2{margin:0 0 12px;font-size:16px;color:#1e293b;border-bottom:1px solid #e2e8f0;padding-bottom:6px;}");
        sb.AppendLine("table{width:100%;border-collapse:collapse;font-size:13px;}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #f1f5f9;}th{background:#f8fafc;color:#475569;}");
        sb.AppendLine(".badge{display:inline-block;padding:3px 10px;border-radius:999px;color:#fff;font-weight:600;font-size:12px;}</style></head><body>");

        sb.AppendLine("<div class='card'>");
        sb.AppendLine($"<h1>Reporte de Dispositivo: {H(d.ClientName)}</h1>");
        sb.AppendLine($"<p><strong>Equipo:</strong> {H(d.Hostname)} | <strong>Usuario:</strong> {H(d.Username)} | <strong>Técnico:</strong> {H(d.Technician)} | <strong>Fecha UTC:</strong> {d.CollectedAtUtc:yyyy-MM-dd HH:mm:ss}</p>");
        if (!string.IsNullOrWhiteSpace(d.Notes))
            sb.AppendLine($"<p><strong>Notas:</strong> {H(d.Notes)}</p>");
        sb.AppendLine($"<p><strong>Salud Global de Discos:</strong> <span class='badge' style='background:{badgeColor}'>{H(d.DiskOverallStatus)}</span></p>");
        sb.AppendLine("</div>");

        sb.AppendLine("<div class='card'><h2>Salud de Discos (S.M.A.R.T.)</h2><table><tr><th>Estado</th><th>Modelo</th><th>Capacidad</th><th>Temp</th><th>Horas</th><th>Detalle</th></tr>");
        foreach (var disk in d.DisksHealth)
        {
            string c = disk.Status switch { "OK" => "#16a34a", "WARNING" => "#d97706", "CRITICAL" => "#dc2626", _ => "#64748b" };
            sb.AppendLine($"<tr><td><span class='badge' style='background:{c}'>{H(disk.Status)}</span></td><td>{H(disk.Model)}</td><td>{disk.CapacityGb} GB</td><td>{(disk.TemperatureC.HasValue ? disk.TemperatureC + " °C" : "N/A")}</td><td>{disk.PowerOnHours?.ToString() ?? "N/A"}</td><td>{H(disk.Summary)}</td></tr>");
        }
        sb.AppendLine("</table></div>");

        if (d.Hardware != null)
        {
            sb.AppendLine("<div class='card'><h2>Hardware</h2><table>");
            sb.AppendLine($"<tr><th>Equipo</th><td>{H(d.Hardware.Manufacturer)} {H(d.Hardware.Model)} (S/N: {H(d.Hardware.SerialNumber)})</td></tr>");
            sb.AppendLine($"<tr><th>Procesador</th><td>{H(d.Hardware.CpuName)} ({d.Hardware.CpuCores} núcleos / {d.Hardware.CpuLogicalProcessors} hilos)</td></tr>");
            sb.AppendLine($"<tr><th>Memoria RAM</th><td>{d.Hardware.TotalRamGb} GB</td></tr>");
            sb.AppendLine($"<tr><th>Placa / BIOS</th><td>{H(d.Hardware.Motherboard)} / {H(d.Hardware.BiosVersion)}</td></tr>");
            sb.AppendLine($"<tr><th>GPU</th><td>{H(string.Join(", ", d.Hardware.Gpus))}</td></tr>");
            sb.AppendLine("</table></div>");
        }

        if (d.UserOs != null)
        {
            sb.AppendLine("<div class='card'><h2>Sistema Operativo</h2><table>");
            sb.AppendLine($"<tr><th>SO</th><td>{H(d.UserOs.OsName)} ({H(d.UserOs.Architecture)})</td></tr>");
            sb.AppendLine($"<tr><th>Versión / Build</th><td>{H(d.UserOs.OsVersion)} / {H(d.UserOs.OsBuild)}</td></tr>");
            sb.AppendLine($"<tr><th>Tiempo encendido</th><td>{H(d.UserOs.Uptime)}</td></tr>");
            sb.AppendLine("</table></div>");
        }

        if (d.Network != null)
        {
            sb.AppendLine("<div class='card'><h2>Red</h2><table><tr><th>Adaptador</th><th>IPs</th><th>MAC</th><th>Puerta de enlace</th></tr>");
            foreach (var a in d.Network.Adapters)
                sb.AppendLine($"<tr><td>{H(a.Name)}</td><td>{H(a.IpAddresses)}</td><td>{H(a.MacAddress)}</td><td>{H(a.Gateways)}</td></tr>");
            sb.AppendLine("</table></div>");
        }

        if (d.Software != null)
        {
            sb.AppendLine($"<div class='card'><h2>Software Instalado ({d.Software.InstalledPrograms.Count})</h2><table><tr><th>Nombre</th><th>Versión</th><th>Editor</th></tr>");
            foreach (var p in d.Software.InstalledPrograms)
                sb.AppendLine($"<tr><td>{H(p.Name)}</td><td>{H(p.Version)}</td><td>{H(p.Publisher)}</td></tr>");
            sb.AppendLine("</table></div>");
        }

        sb.AppendLine("</body></html>");
        return sb.ToString();
    }
}
