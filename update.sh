#!/usr/bin/env bash
# Aktualizacja Plex Downloader z GitHuba.  Uruchom:  ./update.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

OLD="$(cat VERSION 2>/dev/null || echo '?')"
git pull --ff-only
"$APP_DIR/venv/bin/pip" install -q -r requirements.txt
sudo systemctl restart plex-downloader
echo "Zaktualizowano: $OLD → $(cat VERSION)"
echo "Trwające pobierania zostaną automatycznie wznowione."
