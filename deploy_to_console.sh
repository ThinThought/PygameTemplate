#!/usr/bin/env sh

: "${DEPLOY_CONSOLE_IP:?Define DEPLOY_CONSOLE_IP con la IP de la consola de destino}"
IP="$DEPLOY_CONSOLE_IP"
DEPLOY_CONSOLE_USER="${DEPLOY_CONSOLE_USER:-root}"
DEST="$DEPLOY_CONSOLE_USER@$IP:/userdata/roms/pygame"
GAME_NAME="PygameTemplate"

PROJECT_DIR="."
PROJECT_DIR_DEST="$DEST/$GAME_NAME"

set -eu
rm -rf vendor
mkdir -p vendor

uv pip freeze \
  | grep -vE '^-e |^file:|^\.$' \
  | sed 's/@.*//' \
  | xargs -n1 uv pip install --target vendor --no-compile


echo "✅ vendor/ listo"
echo "📦 Root: $PROJECT_DIR"
echo "🎯 Dest: $PROJECT_DIR_DEST"

# 1) Sincroniza el proyecto
rsync -av --delete --no-owner --no-group \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  "$PROJECT_DIR" \
  "$PROJECT_DIR_DEST"

echo "✅ Synced."
