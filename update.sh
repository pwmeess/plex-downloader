#!/usr/bin/env bash
# Update Plex Downloader to the latest STABLE version from GitHub.  Run:  ./update.sh
# BETA versions are installed and updated only with ./fix.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "This installation runs a BETA version ($(cat VERSION))."
  echo "Use ./fix.sh to update BETA or to return to the stable version."
  exit 1
fi

OLD="$(cat VERSION 2>/dev/null || echo '?')"
echo "Downloading the latest stable version from GitHub…"
git pull --ff-only origin main
rm -f "$APP_DIR/.pinned-version"   # an older version chosen in fix.sh → back to the newest
"$APP_DIR/venv/bin/pip" install -q -r requirements.txt
sudo systemctl restart plex-downloader
echo "Updated: $OLD → $(cat VERSION)"
echo "Downloads in progress will resume automatically."
