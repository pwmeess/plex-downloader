#!/usr/bin/env bash
# Plex Downloader installer for Raspberry Pi OS.
# Run as a regular user (e.g. pi):  ./setup.sh
# Optional: PLEXDL_LANG=en|pl skips the language question (used by fix.sh).
set -euo pipefail

SERVICE="plex-downloader"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="$(id -un)"
RUN_GROUP="$(id -gn)"

c_ok()   { printf '\033[32m✔ %s\033[0m\n' "$*"; }
c_info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m! %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- language
UI_LANG="${PLEXDL_LANG:-}"
if [ -z "$UI_LANG" ]; then
  echo
  echo "  Choose language:"
  echo "    1) English (default)"
  echo "    2) Polski (Polish)"
  read -r -p "  [1/2]: " ans || ans=""
  case "$ans" in 2) UI_LANG="pl" ;; *) UI_LANG="en" ;; esac
fi
# L "english text" "polski tekst"
L() { if [ "$UI_LANG" = "pl" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

if [ "$(id -u)" -eq 0 ]; then
  L "Run without sudo, as a regular user:  ./setup.sh" "Uruchom bez sudo, jako zwykły użytkownik:  ./setup.sh"; echo
  L "(the script asks for sudo itself where needed)" "(skrypt sam poprosi o sudo tam, gdzie jest potrzebne)"; echo
  exit 1
fi

echo
echo "  Plex Downloader – $(L "installation" "instalacja")"
echo "  $(L "Folder:" "Katalog:")     $APP_DIR"
echo "  $(L "User:" "Użytkownik:")       $RUN_USER"
echo

c_info "$(L "Installing system packages (aria2, python3-venv, git)…" "Instaluję pakiety systemowe (aria2, python3-venv, git)…")"
sudo apt-get update -qq
sudo apt-get install -y -qq aria2 python3 python3-venv python3-pip git >/dev/null
c_ok "aria2c $(aria2c --version | head -1 | awk '{print $3}')"
# ffmpeg: posters from video frames (optional). Nothing is shown when it is already there; installing it
# never stops the setup. On a Pi Zero it takes several minutes, so say so instead of looking frozen.
if ! command -v ffmpeg >/dev/null 2>&1; then
  c_info "$(L "Installing ffmpeg (posters from video frames) – on a Pi Zero this can take 5–15 minutes, please wait…" "Instaluję ffmpeg (plakaty z kadrów filmu) – na Pi Zero może to potrwać 5–15 minut, proszę czekać…")"
  if sudo apt-get install -y -qq ffmpeg >/dev/null 2>&1; then
    c_ok "ffmpeg"
  else
    c_warn "$(L "ffmpeg was not installed – you can add it later with fix.sh → Additional modules." "Nie zainstalowano ffmpeg – możesz go dodać później w fix.sh → Moduły dodatkowe.")"
  fi
fi

c_info "$(L "Creating the Python environment (venv)…" "Tworzę środowisko Pythona (venv)…")"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
# Slow or unstable Wi-Fi (Pi Zero): more retries and a longer timeout. Upgrading pip itself is optional.
PIP_NET=(--retries 10 --timeout 60)
"$APP_DIR/venv/bin/pip" install -q "${PIP_NET[@]}" --upgrade pip 2>/dev/null \
  || c_warn "$(L "pip was not upgraded (network) – continuing with the system version." "Nie zaktualizowano pip (sieć) – kontynuuję z wersją systemową.")"
if ! "$APP_DIR/venv/bin/pip" install -q "${PIP_NET[@]}" -r "$APP_DIR/requirements.txt"; then
  c_warn "$(L "Could not download the Python packages (connection to pypi.org). Check the network and run ./setup.sh again – nothing is lost." "Nie udało się pobrać pakietów Pythona (połączenie z pypi.org). Sprawdź sieć i uruchom ./setup.sh ponownie – nic nie zostanie utracone.")"
  exit 1
fi
c_ok "$(L "Python dependencies installed" "Zależności Pythona zainstalowane")"

if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
  chmod 600 "$APP_DIR/config.json"
  c_ok "$(L "Created config.json with default settings" "Utworzono config.json z ustawieniami domyślnymi")"
fi

"$APP_DIR/venv/bin/python" "$APP_DIR/app.py" --set-language "$UI_LANG"
c_ok "$(L "Interface language: English (change it in Settings → Account)" "Język interfejsu: polski (zmienisz go w Ustawienia → Konto)")"

if ! grep -q '"password_hash": "[^"]' "$APP_DIR/config.json"; then
  echo
  "$APP_DIR/venv/bin/python" "$APP_DIR/app.py" --set-password
  echo
fi

c_info "$(L "Checking library folders from config.json…" "Sprawdzam foldery bibliotek z config.json…")"
"$APP_DIR/venv/bin/python" "$APP_DIR/app.py" --check-folders

c_info "$(L "Registering the systemd service" "Rejestruję usługę systemd") ($SERVICE)…"
sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<EOF
[Unit]
Description=Plex Downloader (download manager for the Plex library)
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
  c_ok "$(L "The service is running and starts automatically after a reboot" "Usługa działa i uruchomi się automatycznie po restarcie Pi")"
  echo
  echo "  $(L "Open in the browser:" "Otwórz w przeglądarce:")  http://$IP:$PORT"
  echo
  echo "  $(L "Logs:" "Logi:")          journalctl -u $SERVICE -f"
  echo "  $(L "Update:" "Aktualizacja:")  ./update.sh"
  echo "  $(L "Repair menu:" "Menu naprawy:")  ./fix.sh"
else
  c_warn "$(L "The service did not start. Check:" "Usługa nie wystartowała. Sprawdź:")  journalctl -u $SERVICE -n 50"
  exit 1
fi
