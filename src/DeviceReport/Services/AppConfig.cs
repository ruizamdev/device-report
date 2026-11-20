using System;
using System.IO;
using System.Reflection;
using System.Text.Json;

namespace DeviceReport.Services;

public sealed class AppConfig
{
    public VpsApiSettings VpsApi { get; set; } = new();
    public SmartCtlSettings SmartCtl { get; set; } = new();
    public DataCollectionSettings DataCollection { get; set; } = new();

    public static AppConfig Load(out string? warning)
    {
        warning = null;
        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

        // 1. Si existe un config.json externo junto al .exe, tiene prioridad
        string externalPath = Path.Combine(AppContext.BaseDirectory, "config.json");
        if (File.Exists(externalPath))
        {
            try
            {
                var ext = JsonSerializer.Deserialize<AppConfig>(File.ReadAllText(externalPath), options);
                if (ext != null) return ext;
            }
            catch (Exception ex)
            {
                warning = $"Error leyendo config.json externo ({ex.Message}).";
            }
        }

        // 2. Cargar configuración incrustada dentro del .exe
        var asm = Assembly.GetExecutingAssembly();
        using Stream? stream = asm.GetManifestResourceStream("DeviceReport.config.json");
        if (stream != null)
        {
            try
            {
                var embedded = JsonSerializer.Deserialize<AppConfig>(stream, options);
                if (embedded != null) return embedded;
            }
            catch (Exception ex)
            {
                warning = $"Error leyendo configuración incrustada ({ex.Message}).";
            }
        }

        warning = "No se encontró configuración incrustada en el ejecutable; usando valores predeterminados.";
        return new AppConfig();
    }
}

public sealed class VpsApiSettings
{
    public string EndpointUrl { get; set; } = "https://reportes.sismanager.cloud/api/v1/reports";
    public string ApiToken { get; set; } = string.Empty;
    public int TimeoutSeconds { get; set; } = 60;
}

public sealed class SmartCtlSettings
{
    public bool AutoDownload { get; set; } = true;
    public string ExecutablePath { get; set; } = Path.Combine("tools", "smartctl.exe");
}

public sealed class DataCollectionSettings
{
    public bool Hardware { get; set; } = true;
    public bool DiskHealth { get; set; } = true;
    public bool User { get; set; } = true;
    public bool Software { get; set; } = true;
    public bool Network { get; set; } = true;
}
