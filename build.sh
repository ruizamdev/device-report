#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

DOTNET_BIN="dotnet"
if [ -x "$HOME/.dotnet/dotnet" ]; then
  DOTNET_BIN="$HOME/.dotnet/dotnet"
fi

rm -rf dist
"$DOTNET_BIN" publish src/DeviceReport/DeviceReport.csproj \
  -c Release \
  -r win-x64 \
  --self-contained true \
  -p:PublishSingleFile=true \
  -p:DebugType=None \
  -p:DebugSymbols=false \
  -o dist/

echo "Compilado en dist/DeviceReport.exe"
ls -lh dist/
