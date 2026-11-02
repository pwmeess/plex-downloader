#!/usr/bin/env bash
# Plex Downloader – repair menu: update, reinstall, clean reinstall, uninstall.
# Run as a regular user:  ./fix.sh
# Movies and TV shows in the library folders are NEVER touched.
set -uo pipefail

SERVICE="plex-downloader"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT="/etc/systemd/system/$SERVICE.service"
cd "$APP_DIR"

c_ok()   { printf '\033[32m✔ %s\033[0m\n' "$*"; }
c_info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m! %s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then
  echo "Run without sudo, as a regular user:  ./fix.sh"
  exit 1
fi

echo
echo "  Choose language:"
echo "    1) English (default)"
echo "    2) Polski (Polish)"
read -r -p "  [1/2]: " ans || ans=""
case "$ans" in 2) UI_LANG="pl" ;; *) UI_LANG="en" ;; esac
L() { if [ "$UI_LANG" = "pl" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

confirm() {  # confirm "question" → 0 if the user typed YES/TAK
  local word; word="$(L YES TAK)"
  read -r -p "  $1 $(L "Type" "Wpisz") $word: " a || a=""
  [ "$a" = "$word" ] || [ "$a" = "${word,,}" ]
}

fetch_code() {
  c_info "$(L "Downloading the latest code from GitHub…" "Pobieram najnowszy kod z GitHuba…")"
  git fetch -q origin || { c_warn "$(L "Could not connect to GitHub." "Nie udało się połączyć z GitHubem.")"; return 1; }
  local br; br="$(git rev-parse --abbrev-ref HEAD)"
  git reset -q --hard "origin/$br"   # code only – config.json, backups/, logs/ are not tracked
}

stop_service() { sudo systemctl stop "$SERVICE" 2>/dev/null || true; }

echo
echo "  Plex Downloader – $(L "repair menu" "menu naprawy")  ($(cat VERSION 2>/dev/null || echo '?'))"
echo "  $(L "Your movies and TV shows are never touched." "Twoje filmy i seriale nie są nigdy ruszane.")"
echo
echo "    1) $(L "Update (check and install)" "Aktualizacja (sprawdź i zainstaluj)")"
echo "    2) $(L "Reinstall (keep settings)" "Reinstalacja (zachowaj ustawienia)")"
echo "    3) $(L "Clean reinstall (reset settings, backups and logs)" "Czysta reinstalacja (reset ustawień, kopii i logów)")"
echo "    4) $(L "Uninstall" "Odinstaluj")"
echo "    5) $(L "Cancel" "Anuluj")"
read -r -p "  [1-5]: " opt || opt="5"
echo

case "$opt" in
  1)
    c_info "$(L "Checking for updates…" "Sprawdzam aktualizacje…")"
    if ! git fetch -q origin; then c_warn "$(L "Could not connect to GitHub." "Nie udało się połączyć z GitHubem.")"; exit 1; fi
    behind="$(git rev-list --count HEAD..@{u} 2>/dev/null || echo 0)"
    if [ "$behind" = "0" ]; then
      c_ok "$(L "You have the latest version" "Masz najnowszą wersję"): $(cat VERSION)"
      exit 0
    fi
    echo "  $(L "New changes available:" "Dostępne nowe zmiany:") $behind"
    "$APP_DIR/update.sh"
    ;;
  2)
    stop_service
    fetch_code || exit 1
    c_info "$(L "Rebuilding the Python environment…" "Odbudowuję środowisko Pythona…")"
    rm -rf "$APP_DIR/venv"
    PLEXDL_LANG="$UI_LANG" "$APP_DIR/setup.sh"
    ;;
  3)
    echo "  $(L "This deletes: settings (config.json, login and password), settings backups, activity logs and the download list." \
                "Zostaną usunięte: ustawienia (config.json, login i hasło), kopie ustawień, dzienniki aktywności i lista pobierań.")"
    echo "  $(L "Movies and TV shows on the disks stay untouched." "Filmy i seriale na dyskach pozostaną nietknięte.")"
    confirm "$(L "Continue?" "Kontynuować?")" || { echo "  $(L "Cancelled." "Anulowano.")"; exit 0; }
    stop_service
    fetch_code || exit 1
    rm -rf "$APP_DIR/venv" "$APP_DIR/backups" "$APP_DIR/logs"
    rm -f "$APP_DIR/config.json" "$APP_DIR/config.json.tmp" "$APP_DIR"/plexdl.db*
    c_ok "$(L "Settings, backups and logs removed" "Usunięto ustawienia, kopie i logi")"
    PLEXDL_LANG="$UI_LANG" "$APP_DIR/setup.sh"
    ;;
  4)
    echo "  $(L "The service will be stopped and removed from autostart." "Usługa zostanie zatrzymana i usunięta z autostartu.")"
    confirm "$(L "Uninstall Plex Downloader?" "Odinstalować Plex Downloader?")" || { echo "  $(L "Cancelled." "Anulowano.")"; exit 0; }
    sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
    sudo rm -f "$UNIT"
    sudo systemctl daemon-reload
    c_ok "$(L "Service removed" "Usługa usunięta")"
    read -r -p "  $(L "Also delete the application folder" "Usunąć też folder aplikacji") $APP_DIR ($(L "settings, backups, logs" "ustawienia, kopie, logi"))? [y/N]: " a || a=""
    if [[ "$a" =~ ^[yYtT] ]]; then
      cd "$HOME" && rm -rf "$APP_DIR"
      c_ok "$(L "Folder deleted" "Folder usunięty"): $APP_DIR"
    else
      echo "  $(L "The folder stays. Reinstall any time with" "Folder pozostaje. Ponowna instalacja w dowolnej chwili:")  ./setup.sh"
    fi
    echo "  $(L "aria2 stays installed (remove it with: sudo apt remove aria2)." "aria2 pozostaje zainstalowane (usuniesz je: sudo apt remove aria2).")"
    echo "  $(L "Your movies and TV shows were not touched." "Twoje filmy i seriale nie zostały ruszone.")"
    ;;
  *)
    echo "  $(L "Cancelled – nothing was changed." "Anulowano – nic nie zostało zmienione.")"
    ;;
esac
