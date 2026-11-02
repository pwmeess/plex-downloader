#!/usr/bin/env bash
# Plex Downloader – repair menu: update, reinstall, BETA, uninstall.
# Run as a regular user:  ./fix.sh
# Movies and TV shows in the library folders are NEVER touched.
#
# Release channels (GitHub branches):
#   main = stable (installed by setup.sh, updated by update.sh)
#   beta = BETA   (installed and updated only here)
set -uo pipefail

SERVICE="plex-downloader"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT="/etc/systemd/system/$SERVICE.service"
SNAP="$APP_DIR/.stable-snapshot"   # stable settings saved before switching to BETA
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

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
ON_BETA=0; [ "$BRANCH" = "beta" ] && ON_BETA=1

fetch_all() {
  c_info "$(L "Checking GitHub…" "Sprawdzam GitHuba…")"
  git fetch -q origin "+refs/heads/main:refs/remotes/origin/main" "+refs/heads/beta:refs/remotes/origin/beta" 2>/dev/null \
    || git fetch -q origin "+refs/heads/main:refs/remotes/origin/main" \
    || { c_warn "$(L "Could not connect to GitHub." "Nie udało się połączyć z GitHubem.")"; return 1; }
}

# switch_code <branch> – code only; config.json, backups/, logs/ are not tracked by git
switch_code() {
  git checkout -q -B "$1" "origin/$1" && git branch -q --set-upstream-to="origin/$1" "$1" 2>/dev/null
  git reset -q --hard "origin/$1"
}

stop_service() { sudo systemctl stop "$SERVICE" 2>/dev/null || true; }

run_setup() { PLEXDL_LANG="$UI_LANG" "$APP_DIR/setup.sh"; }

wipe_settings() {
  rm -rf "$APP_DIR/backups" "$APP_DIR/logs"
  rm -f "$APP_DIR/config.json" "$APP_DIR/config.json.tmp" "$APP_DIR"/plexdl.db*
}

CUR="$(cat VERSION 2>/dev/null || echo '?')"
echo
echo "  Plex Downloader – $(L "repair menu" "menu naprawy")  ($CUR)"
[ $ON_BETA -eq 1 ] && echo "  $(L "You are using a BETA version." "Używasz wersji BETA.")"
echo "  $(L "Your movies and TV shows are never touched." "Twoje filmy i seriale nie są nigdy ruszane.")"
echo
echo "    1) $(L "Update (check and install)" "Aktualizacja (sprawdź i zainstaluj)")"
echo "    2) $(L "Reinstall (keep settings)" "Reinstalacja (zachowaj ustawienia)")"
echo "    3) $(L "Clean reinstall of the stable version (reset settings, backups and logs)" "Czysta reinstalacja wersji stabilnej (reset ustawień, kopii i logów)")"
echo "    4) $(L "Install / update the latest BETA" "Zainstaluj / zaktualizuj najnowszą BETA")"
echo "    5) $(L "Leave BETA (back to stable, remove experimental settings)" "Wyjście z BETA (powrót do stabilnej, usunięcie ustawień eksperymentalnych)")"
echo "    6) $(L "Uninstall" "Odinstaluj")"
echo "    7) $(L "Cancel" "Anuluj")"
read -r -p "  [1-7]: " opt || opt="7"
echo

case "$opt" in
  1)
    if [ $ON_BETA -eq 1 ]; then
      echo "  $(L "You are on BETA. Use option 4 to update BETA or option 5 to return to stable." \
                  "Jesteś na wersji BETA. Opcja 4 aktualizuje BETA, opcja 5 wraca do wersji stabilnej.")"
      exit 0
    fi
    fetch_all || exit 1
    NEW="$(git show origin/main:VERSION 2>/dev/null || echo "$CUR")"
    if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
      c_ok "$(L "You have the latest version" "Masz najnowszą wersję"): $CUR"
      exit 0
    fi
    echo "  $(L "Available:" "Dostępna:") $NEW"
    "$APP_DIR/update.sh"
    ;;
  2)
    fetch_all || exit 1
    stop_service
    switch_code "$BRANCH" || exit 1
    c_info "$(L "Rebuilding the Python environment…" "Odbudowuję środowisko Pythona…")"
    rm -rf "$APP_DIR/venv"
    run_setup
    ;;
  3)
    echo "  $(L "This deletes: settings (config.json, login and password), settings backups, activity logs and the download list." \
                "Zostaną usunięte: ustawienia (config.json, login i hasło), kopie ustawień, dzienniki aktywności i lista pobierań.")"
    echo "  $(L "Movies and TV shows on the disks stay untouched." "Filmy i seriale na dyskach pozostaną nietknięte.")"
    confirm "$(L "Continue?" "Kontynuować?")" || { echo "  $(L "Cancelled." "Anulowano.")"; exit 0; }
    fetch_all || exit 1
    stop_service
    switch_code main || exit 1
    rm -rf "$APP_DIR/venv" "$SNAP"
    wipe_settings
    c_ok "$(L "Settings, backups and logs removed" "Usunięto ustawienia, kopie i logi")"
    run_setup
    ;;
  4)
    fetch_all || exit 1
    if ! git rev-parse -q --verify origin/beta >/dev/null; then
      c_warn "$(L "No BETA version is available right now." "W tej chwili nie ma wersji BETA.")"
      exit 0
    fi
    NEW="$(git show origin/beta:VERSION 2>/dev/null || echo '?')"
    if [ $ON_BETA -eq 1 ] && [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/beta)" ]; then
      c_ok "$(L "You have the latest BETA" "Masz najnowszą BETA"): $CUR"
      exit 0
    fi
    if [ $ON_BETA -eq 0 ]; then
      echo "  $(L "BETA versions contain new, less tested features." "Wersje BETA zawierają nowe, mniej przetestowane funkcje.")"
      echo "  $(L "Your current settings are saved and restored when you leave BETA (option 5)." \
                  "Obecne ustawienia zostaną zapisane i przywrócone przy wyjściu z BETA (opcja 5).")"
      rm -rf "$SNAP"; mkdir -p "$SNAP"
      [ -f config.json ] && cp -p config.json "$SNAP/"
      [ -d backups ] && cp -rp backups "$SNAP/"
      c_ok "$(L "Stable settings saved" "Zapisano ustawienia wersji stabilnej")"
    fi
    stop_service
    switch_code beta || exit 1
    "$APP_DIR/venv/bin/pip" install -q -r requirements.txt
    sudo systemctl restart "$SERVICE"
    c_ok "$(L "BETA installed" "Zainstalowano BETA"): $CUR → $NEW"
    ;;
  5)
    if [ $ON_BETA -eq 0 ]; then
      c_ok "$(L "You are already on the stable version" "Masz już wersję stabilną"): $CUR"
      exit 0
    fi
    fetch_all || exit 1
    stop_service
    switch_code main || exit 1
    wipe_settings
    if [ -f "$SNAP/config.json" ]; then
      cp -p "$SNAP/config.json" config.json
      [ -d "$SNAP/backups" ] && cp -rp "$SNAP/backups" backups
      c_ok "$(L "Settings from before BETA restored" "Przywrócono ustawienia sprzed BETA")"
    else
      c_warn "$(L "No saved stable settings – starting with default settings." "Brak zapisanych ustawień – start z ustawieniami domyślnymi.")"
    fi
    rm -rf "$SNAP" "$APP_DIR/venv"
    run_setup
    ;;
  6)
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
