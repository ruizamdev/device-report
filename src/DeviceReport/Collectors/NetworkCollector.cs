using System;
using System.Diagnostics;
using System.Management;
using System.Text.RegularExpressions;
using DeviceReport.Models;

namespace DeviceReport.Collectors;

public static class NetworkCollector
{
    public static NetworkInfo Collect(Action<string> log)
    {
        var info = new NetworkInfo();

        log("  • Adaptadores de red...");
        foreach (ManagementObject obj in new ManagementObjectSearcher("SELECT Description, MACAddress, IPAddress, DefaultIPGateway, DNSServerSearchOrder FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled=TRUE").Get())
        {
            string[] ips = obj["IPAddress"] as string[] ?? Array.Empty<string>();
            string[] gw = obj["DefaultIPGateway"] as string[] ?? Array.Empty<string>();
            string[] dns = obj["DNSServerSearchOrder"] as string[] ?? Array.Empty<string>();

            info.Adapters.Add(new NetworkAdapterInfo
            {
                Name = obj["Description"]?.ToString()?.Trim() ?? string.Empty,
                MacAddress = obj["MACAddress"]?.ToString()?.Trim() ?? string.Empty,
                IpAddresses = string.Join(", ", ips),
                Gateways = string.Join(", ", gw),
                DnsServers = string.Join(", ", dns)
            });
        }

        log("  • Perfiles Wi-Fi...");
        try
        {
            var psi = new ProcessStartInfo("netsh", "wlan show profiles")
            {
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using var proc = Process.Start(psi);
            if (proc != null)
            {
                string output = proc.StandardOutput.ReadToEnd();
                proc.WaitForExit(5000);
                foreach (Match m in Regex.Matches(output, @":\s*(.+)$", RegexOptions.Multiline))
                {
                    string val = m.Groups[1].Value.Trim();
                    if (!string.IsNullOrEmpty(val) && !val.StartsWith("<"))
                        info.WifiProfiles.Add(val);
                }
            }
        }
        catch
        {
            // Equipos sin interfaz Wi-Fi pueden fallar en netsh wlan; se omite sin error.
        }

        return info;
    }
}
