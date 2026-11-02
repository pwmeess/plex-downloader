#!/usr/bin/env bash
# Instalator Plex Downloader dla Raspberry Pi OS.
# Uruchom jako zwykły użytkownik (np. pi):  ./setup.sh
set -euo pipefail

SERVICE="plex-downloader"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="$(id -un)"
RUN_GROUP="$(id -gn)"

c_ok()   { printf '\033[32m✔ %s\033[0m\n' "$*"; }
c_info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m! %s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then
  echo "Uruchom bez sudo, jako zwykły użytkownik:  ./setup.sh"
  echo "(skrypt sam poprosi o sudo tam, gdzie jest potrzebne)"
  exit 1
fi

echo
echo "  Plex Downloader – instalacja"
echo "  Katalog:     $APP_DIR"
echo "  Użytkownik:  $RUN_USER"
echo

c_info "Instaluję pakiety systemowe (aria2, python3-venv, git)…"
sudo apt-get update -qq
sudo apt-get install -y -qq aria2 python3 python3-venv python3-pip git >/dev/null
c_ok "aria2c $(aria2c --version | head -1 | awk '{print $3}')"

c_info "Tworzę środowisko Pythona (venv)…"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
c_ok "Zależności Pythona zainstalowane"
if "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements-optional.txt" 2>/dev/null; then
  c_ok "Pillow zainstalowany (okładki .thumb.png)"
else
  c_warn "Nie udało się zainstalować Pillow – okładki będą zapisywane jako .thumb.jpg"
fi

if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
  chmod 600 "$APP_DIR/config.json"
  c_ok "Utworzono config.json z ustawieniami domyślnymi"
fi

if ! grep -q '"password_hash": "[^"]' "$APP_DIR/config.json"; then
  echo
  "$APP_DIR/venv/bin/python" "$APP_DIR/app.py" --set-password
  echo
fi

c_info "Sprawdzam foldery bibliotek z config.json…"
"$APP_DIR/venv/bin/python" "$APP_DIR/app.py" --check-folders

c_info "Rejestruję usługę systemd ($SERVICE)…"
sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<EOF
[Unit]
Description=Plex Downloader (menedżer pobierania do biblioteki Plex)
After=network-online.target local-fs.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/app.py
Environment=PYTHONUNBUFFERED=1
UMask=0002
Restart=on-failure
RestartSec=5
KillMode=control-group
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null 2>&1
sudo systemctl restart "$SERVICE"
sleep 2

PORT="$("$APP_DIR/venv/bin/python" -c "import json;print(json.load(open('$APP_DIR/config.json')).get('port',8800))")"
IP="$(hostname -I | awk '{print $1}')"
if systemctl is-active --quiet "$SERVICE"; then
  c_ok "Usługa działa i uruchomi się automatycznie po restarcie Pi"
  echo
  echo "  Otwórz w przeglądarce:  http://$IP:$PORT"
  echo
  echo "  Logi:        journalctl -u $SERVICE -f"
  echo "  Aktualizacja: ./update.sh"
else
  c_warn "Usługa nie wystartowała. Sprawdź:  journalctl -u $SERVICE -n 50"
  exit 1
fi
