#!/usr/bin/env bash
# Update Plex Downloader from GitHub.  Run:  ./update.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

OLD="$(cat VERSION 2>/dev/null || echo '?')"
echo "Downloading the latest version from GitHub…"
git pull --ff-only
"$APP_DIR/venv/bin/pip" install -q -r requirements.txt
sudo systemctl restart plex-downloader
echo "Updated: $OLD → $(cat VERSION)"
echo "Downloads in progress will resume automatically."
