#!/bin/zsh
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Uso: ./sync_data.sh <source_env_file> <target_env_file>"
  echo "Exemplo: ./sync_data.sh .env.real .env.local"
  exit 1
fi

SOURCE_ENV="$1"
TARGET_ENV="$2"
FIXTURE_PATH="/tmp/sdt_sync_fixture.json"

echo "Exportando dados de ${SOURCE_ENV}..."
ENV_FILE="${SOURCE_ENV}" ./.venv/bin/python manage.py dumpdata \
  --exclude contenttypes \
  --exclude auth.permission \
  --exclude admin.logentry \
  --exclude sessions \
  --exclude token_blacklist \
  --indent 2 > "${FIXTURE_PATH}"

echo "Limpando banco de destino ${TARGET_ENV}..."
ENV_FILE="${TARGET_ENV}" ./.venv/bin/python manage.py flush --no-input

echo "Importando dados para ${TARGET_ENV}..."
ENV_FILE="${TARGET_ENV}" ./.venv/bin/python manage.py loaddata "${FIXTURE_PATH}"

echo "Sincronizacao concluida: ${SOURCE_ENV} -> ${TARGET_ENV}"
