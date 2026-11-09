#!/usr/bin/env bash
# Plex Downloader – repair menu: update, reinstall, BETA, server, uninstall.
# Run as a regular user:  ./fix.sh          (window menu like raspi-config)
#                         ./fix.sh --text   (plain text menu)
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

# ---------------------------------------------------------------- menu: whiptail window or plain text
# Same numbers in both, so "fix.sh → option 4" in the guides is always right.
UI="text"
if [ "${1:-}" != "--text" ] && command -v whiptail >/dev/null 2>&1 && [ -t 0 ] && [ -t 1 ] \
   && [ "$(tput cols 2>/dev/null || echo 0)" -ge 60 ] && [ "$(tput lines 2>/dev/null || echo 0)" -ge 18 ]; then
  UI="whiptail"
fi
TITLE="Plex Downloader"

# menu "question" tag1 "text1" tag2 "text2" … → prints the chosen tag (empty = Esc / Cancel)
menu() {
  local q="$1"; shift
  if [ "$UI" = "whiptail" ]; then
    local n=$(( $# / 2 ))
    whiptail --title "$TITLE" --menu "$q" $(( n + 9 )) 78 "$n" "$@" 3>&1 1>&2 2>&3 || true
  else
    echo >&2
    echo "  $q" >&2
    while [ $# -gt 1 ]; do echo "    $1) $2" >&2; shift 2; done
    local a; read -r -p "  > " a || a=""
    echo "$a"
  fi
}

# pause after text output (status, logs) in window mode
pause() { [ "$UI" = "whiptail" ] && { read -r -p "  $(L "Press Enter to go back…" "Naciśnij Enter, aby wrócić…")" _ || true; }; }

echo
LANG_CHOICE="$(UI_LANG=en; menu "Choose language:" 1 "English (default)" 2 "Polski (Polish)")"
case "$LANG_CHOICE" in 2) UI_LANG="pl" ;; *) UI_LANG="en" ;; esac
L() { if [ "$UI_LANG" = "pl" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

confirm() {  # confirm "question" → 0 if the user typed YES/TAK
  local word a; word="$(L YES TAK)"
  if [ "$UI" = "whiptail" ]; then
    a="$(whiptail --title "$TITLE" --inputbox "$1"$'\n\n'"$(L "Type" "Wpisz") $word:" 12 72 3>&1 1>&2 2>&3)" || a=""
  else
    read -r -p "  $1 $(L "Type" "Wpisz") $word: " a || a=""
  fi
  [ "$a" = "$word" ] || [ "$a" = "${word,,}" ]
}

ask_yes_no() {  # ask_yes_no "question" → 0 = yes (default: no)
  if [ "$UI" = "whiptail" ]; then
    whiptail --title "$TITLE" --defaultno --yes-button "$(L Yes Tak)" --no-button "$(L No Nie)" --yesno "$1" 12 72
  else
    local a; read -r -p "  $1 [y/N]: " a || a=""
    [[ "$a" =~ ^[yYtT] ]]
  fi
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

# ---------------------------------------------------------------- server submenu
panel_url() {
  local port ip
  port="$("$APP_DIR/venv/bin/python" -c "import json;print(json.load(open('$APP_DIR/config.json')).get('port',8800))" 2>/dev/null || echo 8800)"
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "http://${ip:-<raspberry-pi-ip>}:$port"
}

server_menu() {
  while true; do
    local state; state="$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
    local toggle_text
    if [ "$state" = "active" ]; then
      toggle_text="$(L "Stop server (autostart stays on)" "Wstrzymaj serwer (autostart bez zmian)")"
    else
      toggle_text="$(L "Start server (no Raspberry Pi restart needed)" "Uruchom serwer (bez restartu Raspberry Pi)")"
    fi
    local s
    s="$(menu "$(L "Server" "Serwer") – $(L "now" "teraz"): ${state:-unknown}" \
         1 "$(L "Check server status" "Sprawdź status serwera")" \
         2 "$toggle_text" \
         3 "$(L "Restart the server process" "Restart procesu serwera")" \
         4 "$(L "Back" "Powrót")")"
    case "$s" in
      1)
        [ "$UI" = "whiptail" ] && { clear 2>/dev/null || true; }
        echo
        echo "  Plex Downloader $CUR"
        echo "  $(L "Service:" "Usługa:")    $(systemctl is-active "$SERVICE" 2>/dev/null || echo unknown)"
        echo "  $(L "Autostart:" "Autostart:") $(systemctl is-enabled "$SERVICE" 2>/dev/null || echo unknown)"
        echo "  $(L "Panel:" "Panel:")      $(panel_url)"
        echo
        echo "  $(L "Last log entries:" "Ostatnie wpisy logu:")"
        journalctl -u "$SERVICE" -n 10 --no-pager 2>/dev/null | sed 's/^/    /' \
          || sudo journalctl -u "$SERVICE" -n 10 --no-pager | sed 's/^/    /'
        echo
        pause
        [ "$UI" = "text" ] && return 0
        ;;
      2)
        if [ "$state" = "active" ]; then
          sudo systemctl stop "$SERVICE" && c_ok "$(L "Server stopped. It starts again after a Raspberry Pi restart, or with option 2." "Serwer wstrzymany. Wystartuje po restarcie Raspberry Pi albo opcją 2.")"
        else
          sudo systemctl start "$SERVICE" && sleep 2
          if systemctl is-active --quiet "$SERVICE"; then
            c_ok "$(L "Server started:" "Serwer uruchomiony:") $(panel_url)"
          else
            c_warn "$(L "The server did not start. Check:" "Serwer nie wystartował. Sprawdź:")  journalctl -u $SERVICE -n 50"
          fi
        fi
        pause
        [ "$UI" = "text" ] && return 0
        ;;
      3)
        sudo systemctl restart "$SERVICE" && sleep 2
        if systemctl is-active --quiet "$SERVICE"; then
          c_ok "$(L "Server restarted:" "Serwer zrestartowany:") $(panel_url)"
        else
          c_warn "$(L "The server did not start. Check:" "Serwer nie wystartował. Sprawdź:")  journalctl -u $SERVICE -n 50"
        fi
        pause
        [ "$UI" = "text" ] && return 0
        ;;
      *) return 1 ;;   # back to the main menu
    esac
  done
}

# ---------------------------------------------------------------- main menu
HEAD_TEXT="$(L "Repair menu" "Menu naprawy") · $CUR"
[ $ON_BETA -eq 1 ] && HEAD_TEXT="$HEAD_TEXT · $(L "BETA version" "wersja BETA")"
HEAD_TEXT="$HEAD_TEXT"$'\n'"$(L "Your movies and TV shows are never touched." "Twoje filmy i seriale nie są nigdy ruszane.")"

while true; do
  opt="$(menu "$HEAD_TEXT" \
    1 "$(L "Update (check and install)" "Aktualizacja (sprawdź i zainstaluj)")" \
    2 "$(L "Reinstall (keep settings)" "Reinstalacja (zachowaj ustawienia)")" \
    3 "$(L "Clean reinstall of the stable version" "Czysta reinstalacja wersji stabilnej")" \
    4 "$(L "Install / update the latest BETA" "Zainstaluj / zaktualizuj najnowszą BETA")" \
    5 "$(L "Leave BETA (back to stable)" "Wyjście z BETA (powrót do stabilnej)")" \
    6 "$(L "Server: status, stop / start, restart" "Serwer: status, wstrzymaj / uruchom, restart")" \
    7 "$(L "Uninstall" "Odinstaluj")" \
    8 "$(L "Cancel" "Anuluj")")"
  if [ "$opt" = "6" ]; then
    server_menu && exit 0
    continue
  fi
  break
done
[ "$UI" = "whiptail" ] && clear
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
    confirm "$(L "This deletes: settings (config.json, login and password), settings backups, activity logs and the download list. Movies and TV shows on the disks stay untouched. Continue?" \
                 "Zostaną usunięte: ustawienia (config.json, login i hasło), kopie ustawień, dzienniki aktywności i lista pobierań. Filmy i seriale na dyskach pozostaną nietknięte. Kontynuować?")" || { echo "  $(L "Cancelled." "Anulowano.")"; exit 0; }
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
  7)
    confirm "$(L "The service will be stopped and removed from autostart. Uninstall Plex Downloader?" "Usługa zostanie zatrzymana i usunięta z autostartu. Odinstalować Plex Downloader?")" || { echo "  $(L "Cancelled." "Anulowano.")"; exit 0; }
    sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
    sudo rm -f "$UNIT"
    sudo systemctl daemon-reload
    c_ok "$(L "Service removed" "Usługa usunięta")"
    if ask_yes_no "$(L "Also delete the application folder" "Usunąć też folder aplikacji") $APP_DIR ($(L "settings, backups, logs" "ustawienia, kopie, logi"))?"; then
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
