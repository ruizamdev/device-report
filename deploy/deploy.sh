#!/usr/bin/env bash
# Ejecutado en el VPS por GitHub Actions dentro de /srv/apps/<app>.
# Uso: IMAGE_TAG=<tag> ./deploy.sh        (rollback: IMAGE_TAG=<tag anterior>)
set -euo pipefail
cd "$(dirname "$0")"

: "${IMAGE_TAG:?IMAGE_TAG requerido}"
[[ "$IMAGE_TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]
[[ -f .env ]] || { echo ".env no existe en $(pwd)" >&2; exit 1; }

app=$(grep -E '^APP_NAME=' .env | cut -d= -f2- || true)
app=${app:-device-reports}

exec 9>.deploy.lock
flock -w 300 9

previous=$(grep -E '^IMAGE_TAG=' .env | cut -d= -f2- || true)
echo "Desplegando $app: ${previous:-?} -> $IMAGE_TAG"

docker compose config -q
IMAGE_TAG="$IMAGE_TAG" docker compose pull api

if ! IMAGE_TAG="$IMAGE_TAG" docker compose up -d --remove-orphans --wait --wait-timeout 180; then
  echo "Despliegue falló; logs de la api:" >&2
  docker compose logs --tail 80 api >&2 || true
  # `latest` ya apunta a la imagen que acaba de fallar: no sirve como rollback.
  if [[ -z "$previous" || "$previous" == "latest" ]]; then
    echo "Sin tag anterior desplegado; no hay rollback." >&2
  elif [[ "$previous" != "$IMAGE_TAG" ]]; then
    echo "Regresando a $previous" >&2
    IMAGE_TAG="$previous" docker compose up -d --remove-orphans --wait --wait-timeout 180 || true
  fi
  exit 1
fi

# Persistir el tag para que `docker compose up -d` manual reproduzca este estado.
if grep -qE '^IMAGE_TAG=' .env; then
  sed -i -E "s|^IMAGE_TAG=.*|IMAGE_TAG=$IMAGE_TAG|" .env
else
  printf 'IMAGE_TAG=%s\n' "$IMAGE_TAG" >> .env
fi
printf '%s %s\n' "$(date -Is)" "$IMAGE_TAG" >> .deploy-history

# El disco es compartido: borrar solo imágenes sin usar de este repo.
# (Staging y producción comparten repo: prune -a solo borra las que ningún contenedor usa.)
docker image prune -af --filter "label=org.opencontainers.image.source=https://github.com/ruizamdev/device-report" >/dev/null || true

echo "OK $app $IMAGE_TAG"
