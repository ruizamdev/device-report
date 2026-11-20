@echo off
setlocal
cd /d "%~dp0"

if exist dist rmdir /s /q dist
dotnet publish src\DeviceReport\DeviceReport.csproj ^
  -c Release ^
  -r win-x64 ^
  --self-contained true ^
  -p:PublishSingleFile=true ^
  -p:DebugType=None ^
  -p:DebugSymbols=false ^
  -o dist\

if errorlevel 1 (
    echo Error al compilar. Verifica que .NET 8 SDK este instalado.
    pause
    exit /b 1
)

echo.
echo Compilado correctamente en dist\DeviceReport.exe
pause
