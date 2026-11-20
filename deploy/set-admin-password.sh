#!/usr/bin/env bash
# Configura (o cambia) el usuario y la contraseña del panel web.
# Uso en el VPS, como deploy, en una terminal interactiva:
#   ssh -t deploy@<vps> /srv/apps/<app>/set-admin-password.sh [usuario]
# Solo modifica .env (ADMIN_USER, ADMIN_PASSWORD_HASH y, si falta, SESSION_SECRET)
# y reinicia el contenedor. La contraseña nunca se escribe en disco ni en argumentos.
set -euo pipefail
cd "$(dirname "$0")"
[[ -f .env ]] || { echo ".env no existe en $(pwd)" >&2; exit 1; }
[[ -t 0 ]] || { echo "Ejecuta este script en una terminal interactiva (ssh -t)." >&2; exit 1; }

user=${1:-admin}
[[ "$user" =~ ^[A-Za-z0-9._-]{3,32}$ ]] || { echo "Usuario inválido (3-32: letras, números, . _ -)" >&2; exit 1; }

read -rsp "Contraseña para '$user' (mín. 10 caracteres): " p1; echo
read -rsp "Repite la contraseña: " p2; echo
[[ "$p1" == "$p2" ]] || { echo "Las contraseñas no coinciden." >&2; exit 1; }

hash=$(printf '%s\n' "$p1" | docker compose exec -T api python app.py hash-password)
unset p1 p2
[[ "$hash" =~ ^scrypt:[0-9]+:[0-9]+:[0-9]+:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$ ]] || { echo "No se pudo generar el hash." >&2; exit 1; }

set_kv() {
  if grep -qE "^$1=" .env; then sed -i -E "s|^$1=.*|$1=$2|" .env; else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
set_kv ADMIN_USER "$user"
set_kv ADMIN_PASSWORD_HASH "$hash"
grep -qE '^SESSION_SECRET=.{32,}$' .env || set_kv SESSION_SECRET "$(openssl rand -hex 32)"
chmod 600 .env

docker compose up -d --wait --wait-timeout 120 api
echo "Listo: usuario '$user' configurado. Las sesiones abiertas anteriores quedaron invalidadas."
