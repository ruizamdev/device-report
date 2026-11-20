using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Media;
using System.Threading.Tasks;
using System.Windows.Forms;
using DeviceReport.Collectors;
using DeviceReport.Models;
using DeviceReport.Services;

namespace DeviceReport;

public sealed class MainForm : Form
{
    private readonly AppConfig _config;
    private readonly NotifyIcon _trayIcon;

    private TextBox _txtClient = null!;
    private TextBox _txtTech = null!;
    private TextBox _txtNotes = null!;
    private CheckBox _chkHardware = null!;
    private CheckBox _chkDisks = null!;
    private CheckBox _chkUser = null!;
    private CheckBox _chkSoftware = null!;
    private CheckBox _chkNetwork = null!;

    private Panel _diskBanner = null!;
    private Label _lblDiskBanner = null!;
    private ListView _lvDisks = null!;
    private ProgressBar _progress = null!;
    private Label _lblStatus = null!;
    private TextBox _txtLog = null!;

    private Button _btnRun = null!;
    private Button _btnRetry = null!;
    private Button _btnOpenHtml = null!;

    private bool _isBusy;
    private string? _lastZipPath;
    private string? _lastHtmlPath;
    private SummaryMetadata? _lastMetadata;

    public MainForm()
    {
        _config = AppConfig.Load(out string? cfgWarning);

        Text = $"Device Report v{typeof(MainForm).Assembly.GetName().Version?.ToString(3)} — Siscom";
        ClientSize = new Size(760, 650);
        MinimumSize = new Size(700, 580);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 9.5f);
        BackColor = Color.FromArgb(248, 250, 252);

        _trayIcon = new NotifyIcon
        {
            Icon = SystemIcons.Information,
            Text = "Device Report - Siscom",
            Visible = true
        };

        BuildUi();

        if (!string.IsNullOrEmpty(cfgWarning))
            AppendLog($"[AVISO] {cfgWarning}");
        AppendLog($"[INFO] Equipo: {Environment.MachineName} | Usuario: {Environment.UserName}");
        AppendLog($"[INFO] Destino API: {_config.VpsApi.EndpointUrl}");

        FormClosing += (_, e) =>
        {
            if (_isBusy)
            {
                MessageBox.Show("Espera a que termine la recolección/envío actual.", "Proceso en curso", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                e.Cancel = true;
                return;
            }
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
        };
    }

    private void BuildUi()
    {
        var main = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(14),
            ColumnCount = 1,
            RowCount = 5
        };
        main.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        main.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        main.RowStyles.Add(new RowStyle(SizeType.Absolute, 165));
        main.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        main.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        // 1. Datos del servicio
        var grpClient = new GroupBox
        {
            Text = "Datos del Servicio",
            Dock = DockStyle.Fill,
            Padding = new Padding(10),
            AutoSize = true
        };
        var tblClient = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 4, AutoSize = true };
        tblClient.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        tblClient.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 55));
        tblClient.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        tblClient.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 45));

        _txtClient = new TextBox { Dock = DockStyle.Fill, PlaceholderText = "Ej. Juan Pérez / Empresa ABC" };
        _txtTech = new TextBox { Dock = DockStyle.Fill, PlaceholderText = "Opcional" };
        _txtNotes = new TextBox { Dock = DockStyle.Fill, PlaceholderText = "Observaciones del equipo o falla reportada (opcional)" };

        tblClient.Controls.Add(new Label { Text = "Cliente *:", AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(0, 6, 8, 6) }, 0, 0);
        tblClient.Controls.Add(_txtClient, 1, 0);
        tblClient.Controls.Add(new Label { Text = "Técnico:", AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(12, 6, 8, 6) }, 2, 0);
        tblClient.Controls.Add(_txtTech, 3, 0);

        tblClient.Controls.Add(new Label { Text = "Notas:", AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(0, 6, 8, 4) }, 0, 1);
        tblClient.SetColumnSpan(_txtNotes, 3);
        tblClient.Controls.Add(_txtNotes, 1, 1);

        grpClient.Controls.Add(tblClient);
        main.Controls.Add(grpClient, 0, 0);

        // 2. Módulos a recopilar
        var grpOpts = new GroupBox
        {
            Text = "Información a Recopilar",
            Dock = DockStyle.Fill,
            Padding = new Padding(10, 6, 10, 8),
            AutoSize = true
        };
        var flowOpts = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
        _chkHardware = new CheckBox { Text = "Hardware", Checked = _config.DataCollection.Hardware, AutoSize = true, Margin = new Padding(4, 2, 16, 2) };
        _chkDisks = new CheckBox { Text = "Salud de Discos (S.M.A.R.T.)", Checked = _config.DataCollection.DiskHealth, AutoSize = true, Margin = new Padding(4, 2, 16, 2) };
        _chkUser = new CheckBox { Text = "Usuario y SO", Checked = _config.DataCollection.User, AutoSize = true, Margin = new Padding(4, 2, 16, 2) };
        _chkSoftware = new CheckBox { Text = "Software", Checked = _config.DataCollection.Software, AutoSize = true, Margin = new Padding(4, 2, 16, 2) };
        _chkNetwork = new CheckBox { Text = "Red / Wi-Fi", Checked = _config.DataCollection.Network, AutoSize = true, Margin = new Padding(4, 2, 4, 2) };
        flowOpts.Controls.AddRange(new Control[] { _chkHardware, _chkDisks, _chkUser, _chkSoftware, _chkNetwork });
        grpOpts.Controls.Add(flowOpts);
        main.Controls.Add(grpOpts, 0, 1);

        // 3. Panel de Salud de Disco
        var grpDisk = new GroupBox { Text = "Diagnóstico de Salud de Discos", Dock = DockStyle.Fill, Padding = new Padding(8) };
        var diskLayout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2 };
        diskLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        diskLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        _diskBanner = new Panel { Dock = DockStyle.Fill, BackColor = Color.FromArgb(226, 232, 240), Padding = new Padding(8, 5, 8, 5) };
        _lblDiskBanner = new Label
        {
            Text = "Estado global de discos: Pendiente de análisis",
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            TextAlign = ContentAlignment.MiddleLeft
        };
        _diskBanner.Controls.Add(_lblDiskBanner);

        _lvDisks = new ListView
        {
            Dock = DockStyle.Fill,
            View = View.Details,
            FullRowSelect = true,
            GridLines = true
        };
        _lvDisks.Columns.Add("Estado", 90);
        _lvDisks.Columns.Add("Modelo", 210);
        _lvDisks.Columns.Add("Capacidad", 80);
        _lvDisks.Columns.Add("Temp", 60);
        _lvDisks.Columns.Add("Horas", 70);
        _lvDisks.Columns.Add("Detalle", 190);

        diskLayout.Controls.Add(_diskBanner, 0, 0);
        diskLayout.Controls.Add(_lvDisks, 0, 1);
        grpDisk.Controls.Add(diskLayout);
        main.Controls.Add(grpDisk, 0, 2);

        // 4. Consola en vivo
        var grpLog = new GroupBox { Text = "Registro de Ejecución", Dock = DockStyle.Fill, Padding = new Padding(8) };
        _txtLog = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Vertical,
            Font = new Font("Consolas", 9f),
            BackColor = Color.FromArgb(15, 23, 42),
            ForeColor = Color.FromArgb(226, 232, 240)
        };
        grpLog.Controls.Add(_txtLog);
        main.Controls.Add(grpLog, 0, 3);

        // 5. Progreso y botones
        var bottom = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2, AutoSize = true, Margin = new Padding(0, 6, 0, 0) };
        bottom.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        bottom.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        _progress = new ProgressBar { Dock = DockStyle.Fill, Height = 22, Style = ProgressBarStyle.Continuous };
        _lblStatus = new Label { Text = "Listo para iniciar.", Dock = DockStyle.Fill, AutoSize = true, Padding = new Padding(0, 4, 0, 0) };

        var btnFlow = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
        _btnRun = new Button
        {
            Text = "Generar y Enviar Reporte",
            Width = 190,
            Height = 34,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold)
        };
        _btnRun.FlatAppearance.BorderSize = 0;
        _btnRun.Click += async (_, _) => await RunReportAsync();

        _btnRetry = new Button { Text = "Reintentar Envío", Width = 130, Height = 34, Enabled = false };
        _btnRetry.Click += async (_, _) => await RetryUploadAsync();

        _btnOpenHtml = new Button { Text = "Ver HTML", Width = 95, Height = 34, Enabled = false };
        _btnOpenHtml.Click += (_, _) =>
        {
            if (!string.IsNullOrEmpty(_lastHtmlPath) && File.Exists(_lastHtmlPath))
                Process.Start(new ProcessStartInfo(_lastHtmlPath) { UseShellExecute = true });
        };

        btnFlow.Controls.Add(_btnRun);
        btnFlow.Controls.Add(_btnRetry);
        btnFlow.Controls.Add(_btnOpenHtml);

        bottom.Controls.Add(_progress, 0, 0);
        bottom.Controls.Add(_lblStatus, 0, 1);
        bottom.SetRowSpan(btnFlow, 2);
        bottom.Controls.Add(btnFlow, 1, 0);

        main.Controls.Add(bottom, 0, 4);
        Controls.Add(main);
    }

    private async Task RunReportAsync()
    {
        string clientName = _txtClient.Text.Trim();
        if (string.IsNullOrWhiteSpace(clientName))
        {
            MessageBox.Show("El nombre del cliente es obligatorio.", "Dato requerido", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            _txtClient.Focus();
            return;
        }

        SetBusy(true, "Iniciando recolección...");
        _lvDisks.Items.Clear();
        UpdateDiskBanner("ANALIZANDO");
        _progress.Value = 5;

        var data = new DeviceReportData
        {
            ClientName = clientName,
            Technician = _txtTech.Text.Trim(),
            Notes = _txtNotes.Text.Trim(),
            CollectedAtUtc = DateTime.UtcNow
        };

        try
        {
            if (_chkHardware.Checked)
            {
                SetStatus("Recopilando información de hardware...", 15);
                AppendLog("[1/5] Recopilando hardware...");
                data.Hardware = await Task.Run(() => HardwareCollector.Collect(AppendLog));
            }

            if (_chkDisks.Checked)
            {
                SetStatus("Analizando salud de discos (S.M.A.R.T.)...", 35);
                AppendLog("[2/5] Analizando salud de discos...");
                var (disks, overall) = await Task.Run(() => DiskHealthCollector.Collect(_config.SmartCtl, AppendLog));
                data.DisksHealth = disks;
                data.DiskOverallStatus = overall;
                PopulateDiskList(disks, overall);
            }

            if (_chkUser.Checked)
            {
                SetStatus("Recopilando usuario y sistema operativo...", 55);
                AppendLog("[3/5] Recopilando usuario y SO...");
                data.UserOs = await Task.Run(() => UserCollector.Collect(AppendLog));
            }

            if (_chkSoftware.Checked)
            {
                SetStatus("Recopilando software instalado...", 70);
                AppendLog("[4/5] Recopilando software...");
                data.Software = await Task.Run(() => SoftwareCollector.Collect(AppendLog));
            }

            if (_chkNetwork.Checked)
            {
                SetStatus("Recopilando configuración de red...", 82);
                AppendLog("[5/5] Recopilando red...");
                data.Network = await Task.Run(() => NetworkCollector.Collect(AppendLog));
            }

            SetStatus("Generando reportes y empaquetando ZIP...", 90);
            AppendLog("[ZIP] Generando reporte HTML/TXT/JSON...");
            var (zipPath, htmlPath, metadata) = await Task.Run(() => ReportGenerator.GenerateAndZip(data));
            _lastZipPath = zipPath;
            _lastHtmlPath = htmlPath;
            _lastMetadata = metadata;
            _btnOpenHtml.Enabled = true;

            SetStatus("Enviando reporte al VPS siscom...", 95);
            AppendLog($"[VPS] Enviando {Path.GetFileName(zipPath)}...");
            var (ok, msg) = await VpsUploader.UploadAsync(zipPath, metadata, _config.VpsApi);

            if (ok)
            {
                try { File.Delete(zipPath); } catch { }
                _lastZipPath = null;
                _btnRetry.Enabled = false;
                SetStatus("Proceso completado y enviado al VPS.", 100);
                AppendLog($"[OK] Reporte registrado en VPS: {msg}");
                TriggerCompletionAlert(success: true, data.DiskOverallStatus, null);
            }
            else
            {
                _btnRetry.Enabled = true;
                SetStatus("Reporte generado, pero falló el envío al VPS.", 100);
                AppendLog($"[ERROR VPS] {msg}");
                AppendLog($"[INFO] ZIP conservado temporalmente en: {zipPath}");
                TriggerCompletionAlert(success: false, data.DiskOverallStatus, msg);
            }
        }
        catch (Exception ex)
        {
            AppendLog($"[ERROR FATAL] {ex.Message}");
            SetStatus("Error durante el proceso.", 0);
            SystemSounds.Exclamation.Play();
            MessageBox.Show($"Ocurrió un error:\n{ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            SetBusy(false, _lblStatus.Text);
        }
    }

    private async Task RetryUploadAsync()
    {
        if (string.IsNullOrEmpty(_lastZipPath) || !File.Exists(_lastZipPath) || _lastMetadata == null)
        {
            MessageBox.Show("No hay un paquete pendiente por reenviar.", "Aviso", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        SetBusy(true, "Reintentando envío al VPS...");
        var (ok, msg) = await VpsUploader.UploadAsync(_lastZipPath, _lastMetadata, _config.VpsApi);
        if (ok)
        {
            try { File.Delete(_lastZipPath); } catch { }
            _lastZipPath = null;
            _btnRetry.Enabled = false;
            SetStatus("Envío completado al VPS.", 100);
            AppendLog($"[OK] Reenvío exitoso: {msg}");
            TriggerCompletionAlert(success: true, _lastMetadata.DiskOverallStatus, null);
        }
        else
        {
            SetStatus("Falló el reenvío al VPS.", 100);
            AppendLog($"[ERROR VPS] {msg}");
            TriggerCompletionAlert(success: false, _lastMetadata.DiskOverallStatus, msg);
        }
        SetBusy(false, _lblStatus.Text);
    }

    private void TriggerCompletionAlert(bool success, string diskStatus, string? errorMsg)
    {
        bool diskAlert = diskStatus is "WARNING" or "CRITICAL";

        if (!success || diskAlert)
            SystemSounds.Exclamation.Play();
        else
            SystemSounds.Asterisk.Play();

        string title = success ? "Device Report Completado" : "Device Report — Error de Envío";
        string body = success
            ? $"Reporte enviado al VPS.\nSalud de discos: {diskStatus}"
            : $"No se pudo enviar al VPS ({errorMsg}).\nSalud de discos: {diskStatus}";

        _trayIcon.BalloonTipTitle = title;
        _trayIcon.BalloonTipText = body;
        _trayIcon.BalloonTipIcon = (!success || diskStatus == "CRITICAL")
            ? ToolTipIcon.Error
            : (diskStatus == "WARNING" ? ToolTipIcon.Warning : ToolTipIcon.Info);
        _trayIcon.ShowBalloonTip(6000);

        MessageBoxIcon icon = (!success || diskStatus == "CRITICAL")
            ? MessageBoxIcon.Warning
            : MessageBoxIcon.Information;
        MessageBox.Show(body, title, MessageBoxButtons.OK, icon);
    }

    private void PopulateDiskList(List<DiskHealthInfo> disks, string overall)
    {
        UpdateDiskBanner(overall);
        _lvDisks.Items.Clear();
        foreach (var d in disks)
        {
            var item = new ListViewItem(d.Status);
            item.SubItems.Add(d.Model);
            item.SubItems.Add($"{d.CapacityGb} GB");
            item.SubItems.Add(d.TemperatureC.HasValue ? $"{d.TemperatureC}°C" : "N/A");
            item.SubItems.Add(d.PowerOnHours?.ToString() ?? "N/A");
            item.SubItems.Add(d.Summary);
            item.BackColor = d.Status switch
            {
                "OK" => Color.FromArgb(240, 253, 244),
                "WARNING" => Color.FromArgb(255, 251, 235),
                "CRITICAL" => Color.FromArgb(254, 242, 242),
                _ => Color.White
            };
            _lvDisks.Items.Add(item);
        }
    }

    private void UpdateDiskBanner(string status)
    {
        switch (status)
        {
            case "OK":
                _diskBanner.BackColor = Color.FromArgb(22, 163, 74);
                _lblDiskBanner.ForeColor = Color.White;
                _lblDiskBanner.Text = "Estado global de discos: SALUDABLE (OK)";
                break;
            case "WARNING":
                _diskBanner.BackColor = Color.FromArgb(217, 119, 6);
                _lblDiskBanner.ForeColor = Color.White;
                _lblDiskBanner.Text = "Estado global de discos: ADVERTENCIA (Revisar atributos SMART)";
                break;
            case "CRITICAL":
                _diskBanner.BackColor = Color.FromArgb(220, 38, 38);
                _lblDiskBanner.ForeColor = Color.White;
                _lblDiskBanner.Text = "Estado global de discos: CRÍTICO (Riesgo de falla inminente)";
                break;
            case "ANALIZANDO":
                _diskBanner.BackColor = Color.FromArgb(59, 130, 246);
                _lblDiskBanner.ForeColor = Color.White;
                _lblDiskBanner.Text = "Estado global de discos: Analizando...";
                break;
            default:
                _diskBanner.BackColor = Color.FromArgb(226, 232, 240);
                _lblDiskBanner.ForeColor = Color.FromArgb(30, 41, 59);
                _lblDiskBanner.Text = $"Estado global de discos: {status}";
                break;
        }
    }

    private void SetBusy(bool busy, string status)
    {
        _isBusy = busy;
        _btnRun.Enabled = !busy;
        _txtClient.Enabled = !busy;
        _txtTech.Enabled = !busy;
        _txtNotes.Enabled = !busy;
        _lblStatus.Text = status;
    }

    private void SetStatus(string text, int percent)
    {
        if (InvokeRequired)
        {
            Invoke(() => SetStatus(text, percent));
            return;
        }
        _lblStatus.Text = text;
        _progress.Value = Math.Clamp(percent, 0, 100);
    }

    private void AppendLog(string line)
    {
        if (InvokeRequired)
        {
            Invoke(() => AppendLog(line));
            return;
        }
        _txtLog.AppendText($"[{DateTime.Now:HH:mm:ss}] {line}{Environment.NewLine}");
    }
}
