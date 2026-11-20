using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using DeviceReport.Models;

namespace DeviceReport.Services;

public static class VpsUploader
{
    public static async Task<(bool Success, string Message)> UploadAsync(
        string zipPath,
        SummaryMetadata metadata,
        VpsApiSettings settings)
    {
        if (string.IsNullOrWhiteSpace(settings.EndpointUrl))
            return (false, "EndpointUrl no configurado en config.json.");
        if (string.IsNullOrWhiteSpace(settings.ApiToken) || settings.ApiToken.Contains("CAMBIAR"))
            return (false, "ApiToken no configurado en config.json.");

        using var http = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(Math.Max(15, settings.TimeoutSeconds))
        };
        http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", settings.ApiToken);

        using var form = new MultipartFormDataContent();
        byte[] zipBytes = await File.ReadAllBytesAsync(zipPath);
        var fileContent = new ByteArrayContent(zipBytes);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/zip");
        form.Add(fileContent, "file", Path.GetFileName(zipPath));

        string metaJson = JsonSerializer.Serialize(metadata);
        form.Add(new StringContent(metaJson, Encoding.UTF8, "application/json"), "metadata");

        using var resp = await http.PostAsync(settings.EndpointUrl, form);
        string body = await resp.Content.ReadAsStringAsync();

        if (!resp.IsSuccessStatusCode)
            return (false, $"HTTP {(int)resp.StatusCode}: {body}");

        return (true, body);
    }
}
