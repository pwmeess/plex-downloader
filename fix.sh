#!/usr/bin/env bash
# Plex Downloader – repair menu: update, reinstall, BETA, server, additional modules, uninstall.
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
# Same look in every terminal (macOS Terminal / iTerm over SSH showed two shades of grey and broken
# frame lines): one explicit colour set, and UTF-8 line drawing instead of the terminal's ACS characters.
if [ "$UI" = "whiptail" ]; then
  export NCURSES_NO_UTF8_ACS=1
  : "${NEWT_COLORS:=root=white,blue roottext=white,blue helpline=white,blue window=black,lightgray border=black,lightgray shadow=black,black title=red,lightgray textbox=black,lightgray listbox=black,lightgray sellistbox=black,lightgray actlistbox=white,red actsellistbox=white,red button=black,lightgray actbutton=white,red compactbutton=black,lightgray entry=black,lightgray disentry=gray,lightgray checkbox=black,lightgray actcheckbox=white,red emptyscale=,gray fullscale=,red}"
  export NEWT_COLORS
fi

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

# ---------------------------------------------------------------- additional modules (Plex, SMB, ffmpeg, VPN)
# Each module: status first, then the actions that make sense for that status.
MODULES="plex samba cifs ffmpeg tailscale wireguard"

pkg_installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }
pkg_version()   { dpkg-query -W -f='${Version}' "$1" 2>/dev/null; }
apt_update()    { c_info "$(L "Refreshing the package list…" "Odświeżam listę pakietów…")"; sudo apt-get update -qq; }

mod_name() {
  case "$1" in
    plex)      echo "Plex Media Server" ;;
    samba)     echo "$(L "Samba – share folders over SMB (server)" "Samba – udostępnianie folderów SMB (serwer)")" ;;
    cifs)      echo "$(L "SMB client – mount shares (cifs-utils)" "Klient SMB – montowanie udziałów (cifs-utils)")" ;;
    ffmpeg)    echo "$(L "ffmpeg – posters from video frames" "ffmpeg – plakaty z kadrów filmu")" ;;
    tailscale) echo "$(L "Tailscale VPN (recommended)" "Tailscale VPN (zalecany)")" ;;
    wireguard) echo "WireGuard VPN" ;;
  esac
}
mod_pkg() {
  case "$1" in
    plex) echo plexmediaserver ;; samba) echo samba ;; cifs) echo cifs-utils ;;
    ffmpeg) echo ffmpeg ;; tailscale) echo tailscale ;; wireguard) echo wireguard-tools ;;
  esac
}
mod_service() {   # empty = no background service
  case "$1" in
    plex) echo plexmediaserver ;; samba) echo smbd ;; tailscale) echo tailscaled ;;
    wireguard) [ -f /etc/wireguard/wg0.conf ] && echo "wg-quick@wg0" ;;
  esac
}
mod_state() {     # short state for the module list
  local pkg svc; pkg="$(mod_pkg "$1")"; svc="$(mod_service "$1")"
  if ! pkg_installed "$pkg"; then L "not installed" "nie zainstalowano"; return; fi
  if [ -n "$svc" ]; then
    if systemctl is-active --quiet "$svc"; then L "running" "działa"; else L "stopped" "zatrzymany"; fi
  else
    L "installed" "zainstalowano"
  fi
}

mod_status() {
  local m="$1" pkg svc; pkg="$(mod_pkg "$m")"; svc="$(mod_service "$m")"
  [ "$UI" = "whiptail" ] && { clear 2>/dev/null || true; }
  echo
  echo "  $(mod_name "$m")"
  if pkg_installed "$pkg"; then
    echo "  $(L "Installed:" "Zainstalowano:") $(pkg_version "$pkg")"
  else
    echo "  $(L "Not installed." "Nie zainstalowano.")"
  fi
  if [ -n "$svc" ] && pkg_installed "$pkg"; then
    echo "  $(L "Service:" "Usługa:")   $svc – $(systemctl is-active "$svc" 2>/dev/null || echo unknown)"
    echo "  $(L "Autostart:" "Autostart:") $(systemctl is-enabled "$svc" 2>/dev/null || echo unknown)"
  fi
  local ip; ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  case "$m" in
    plex)
      pkg_installed "$pkg" && echo "  $(L "Plex Web:" "Plex Web:")  http://${ip:-<raspberry-pi-ip>}:32400/web"
      echo "  $(L "Plex runs as the user 'plex' – it needs read access to the library folders." "Plex działa jako użytkownik 'plex' – potrzebuje prawa odczytu folderów biblioteki.")" ;;
    samba)
      if pkg_installed "$pkg"; then
        echo "  $(L "Shares:" "Udziały:")"
        testparm -s 2>/dev/null | grep -E '^\[' | grep -viE '^\[(global|printers|print\$)\]' | sed 's/^/    /' \
          || echo "    –"
      fi ;;
    cifs)
      echo "  $(L "Mounted SMB shares:" "Zamontowane udziały SMB:")"
      findmnt -t cifs -n -o TARGET,SOURCE 2>/dev/null | sed 's/^/    /' | grep . || echo "    –" ;;
    ffmpeg)
      command -v ffmpeg >/dev/null && echo "  $(ffmpeg -version 2>/dev/null | head -1)"
      echo "  $(L "Turn it on in the panel: Settings → Preview & posters." "Włączysz w panelu: Ustawienia → Podgląd i plakaty.")" ;;
    tailscale)
      if pkg_installed "$pkg"; then
        echo "  $(L "VPN address:" "Adres w VPN:") $(tailscale ip -4 2>/dev/null || echo "– ($(L "not logged in" "nie zalogowano"))")"
        tailscale status 2>/dev/null | head -5 | sed 's/^/    /'
      fi
      echo "  $(L "Remote access to the panel without opening ports on the router (guide in 1.4)." "Zdalny dostęp do panelu bez otwierania portów na routerze (instrukcja w 1.4).")" ;;
    wireguard)
      if pkg_installed "$pkg"; then
        if [ -f /etc/wireguard/wg0.conf ]; then sudo wg show 2>/dev/null | sed 's/^/    /'
        else echo "  $(L "No configuration yet (/etc/wireguard/wg0.conf) – keys and peers are set up by hand; Tailscale is simpler." "Brak konfiguracji (/etc/wireguard/wg0.conf) – klucze i połączenia ustawia się ręcznie; Tailscale jest prostszy.")"; fi
      fi ;;
  esac
  echo
}

mod_install() {
  local m="$1" pkg; pkg="$(mod_pkg "$m")"
  case "$m" in
    plex)
      sudo apt-get install -y -qq curl gnupg >/dev/null
      curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | sudo gpg --dearmor --yes -o /usr/share/keyrings/plex.gpg
      echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://downloads.plex.tv/repo/deb public main" \
        | sudo tee /etc/apt/sources.list.d/plexmediaserver.list >/dev/null
      apt_update && sudo apt-get install -y plexmediaserver ;;
    tailscale)
      curl -fsSL https://tailscale.com/install.sh | sh || return 1
      if ask_yes_no "$(L "Log in to Tailscale now? A link to open in the browser will be shown." "Zalogować się teraz do Tailscale? Pojawi się link do otwarcia w przeglądarce.")"; then
        sudo tailscale up
      else
        echo "  $(L "Log in later with:" "Zalogujesz się później:")  sudo tailscale up"
      fi ;;
    wireguard) apt_update && sudo apt-get install -y wireguard-tools ;;
    *) apt_update && sudo apt-get install -y "$pkg" ;;
  esac
  pkg_installed "$pkg" && c_ok "$(mod_name "$m"): $(L "installed" "zainstalowano") $(pkg_version "$pkg")"
  [ "$m" = "plex" ] && pkg_installed "$pkg" && echo "  $(L "Open:" "Otwórz:") http://$(hostname -I | awk '{print $1}'):32400/web"
}

mod_update() {
  local pkg; pkg="$(mod_pkg "$1")"
  apt_update && sudo apt-get install -y --only-upgrade "$pkg" \
    && c_ok "$(mod_name "$1"): $(pkg_version "$pkg")"
  local svc; svc="$(mod_service "$1")"
  [ -n "$svc" ] && systemctl is-active --quiet "$svc" || true
}

mod_uninstall() {
  local m="$1" pkg; pkg="$(mod_pkg "$m")"
  local extra=""
  case "$m" in
    plex) extra="$(L "Movies and TV shows stay. The Plex database (watch history, posters) is removed only if you agree in the next step." "Filmy i seriale zostają. Baza Plexa (historia oglądania, plakaty) zostanie usunięta tylko, jeśli zgodzisz się w następnym kroku.")" ;;
    samba) extra="$(L "Other devices will no longer see the shares. Files stay; /etc/samba/smb.conf is kept." "Inne urządzenia przestaną widzieć udziały. Pliki zostają; /etc/samba/smb.conf jest zachowany.")" ;;
    cifs) findmnt -t cifs -n >/dev/null 2>&1 && extra="$(L "Shares are mounted now – they stop working after a restart (remove them from /etc/fstab)." "Udziały są teraz zamontowane – po restarcie przestaną działać (usuń je z /etc/fstab).")" ;;
    ffmpeg) extra="$(L "Posters from video frames will not be created any more (saved ones stay)." "Plakaty z kadrów nie będą już tworzone (zapisane zostają).")" ;;
    tailscale) extra="$(L "Remote access over Tailscale stops." "Zdalny dostęp przez Tailscale przestanie działać.")" ;;
  esac
  confirm "$(L "Completely uninstall" "Całkowicie odinstalować") $(mod_name "$m")? $extra" || { echo "  $(L "Cancelled." "Anulowano.")"; return 0; }
  case "$m" in
    plex)
      sudo systemctl stop plexmediaserver 2>/dev/null || true
      sudo apt-get purge -y plexmediaserver
      sudo rm -f /etc/apt/sources.list.d/plexmediaserver.list /usr/share/keyrings/plex.gpg
      if [ -d /var/lib/plexmediaserver ] && ask_yes_no "$(L "Also delete the Plex database (/var/lib/plexmediaserver: watch history, metadata, posters)?" "Usunąć też bazę Plexa (/var/lib/plexmediaserver: historia oglądania, metadane, plakaty)?")"; then
        sudo rm -rf /var/lib/plexmediaserver && c_ok "$(L "Plex database deleted" "Baza Plexa usunięta")"
      fi ;;
    samba) sudo apt-get remove -y samba ;;
    tailscale)
      sudo tailscale down 2>/dev/null || true
      sudo apt-get purge -y tailscale
      sudo rm -f /etc/apt/sources.list.d/tailscale.list ;;
    wireguard)
      [ -f /etc/wireguard/wg0.conf ] && sudo systemctl disable --now wg-quick@wg0 2>/dev/null || true
      sudo apt-get purge -y wireguard-tools wireguard 2>/dev/null || sudo apt-get purge -y wireguard-tools ;;
    *) sudo apt-get purge -y "$pkg" ;;
  esac
  sudo apt-get autoremove -y -qq >/dev/null 2>&1 || true
  pkg_installed "$pkg" || c_ok "$(mod_name "$m"): $(L "uninstalled" "odinstalowano")"
  echo "  $(L "Your movies and TV shows were not touched." "Twoje filmy i seriale nie zostały ruszone.")"
}

module_menu() {
  local m="$1"
  mod_status "$m"; pause
  while true; do
    local pkg svc; pkg="$(mod_pkg "$m")"; svc="$(mod_service "$m")"
    local args=() i=1 acts=()
    add() { args+=("$i" "$2"); acts+=("$1"); i=$((i + 1)); }
    add status "$(L "Check status" "Sprawdź status")"
    if ! pkg_installed "$pkg"; then
      add install "$(L "Install" "Zainstaluj")"
    else
      add update "$(L "Update" "Zaktualizuj")"
      if [ -n "$svc" ]; then
        if systemctl is-active --quiet "$svc"; then
          add stop "$(L "Stop (until the next restart – autostart stays on)" "Zatrzymaj (do restartu – autostart bez zmian)")"
          add restart "$(L "Restart" "Uruchom ponownie (restart)")"
        else
          add start "$(L "Start" "Uruchom")"
        fi
      fi
      add uninstall "$(L "Uninstall completely" "Odinstaluj całkowicie")"
    fi
    add back "$(L "Back" "Powrót")"
    local c; c="$(menu "$(mod_name "$m") – $(mod_state "$m")" "${args[@]}")"
    [ -z "$c" ] && return 0
    local act="${acts[$((c - 1))]:-back}"
    [ "$UI" = "whiptail" ] && [ "$act" != "status" ] && [ "$act" != "back" ] && { clear 2>/dev/null || true; }
    case "$act" in
      status)    mod_status "$m" ;;
      install)   mod_install "$m" ;;
      update)    mod_update "$m" ;;
      stop)      sudo systemctl stop "$svc" && c_ok "$(L "Stopped – starts again after a restart." "Zatrzymano – wystartuje po restarcie.")" ;;
      start)     sudo systemctl start "$svc" && sleep 1 && c_ok "$(L "Started:" "Uruchomiono:") $(systemctl is-active "$svc")" ;;
      restart)   sudo systemctl restart "$svc" && sleep 1 && c_ok "$(L "Restarted:" "Zrestartowano:") $(systemctl is-active "$svc")" ;;
      uninstall) mod_uninstall "$m" ;;
      *)         return 0 ;;
    esac
    pause
    [ "$UI" = "text" ] && return 0
  done
}

modules_menu() {
  while true; do
    local args=() i=1 list=()
    for m in $MODULES; do args+=("$i" "$(mod_name "$m") – $(mod_state "$m")"); list+=("$m"); i=$((i + 1)); done
    args+=("$i" "$(L "Back" "Powrót")")
    local c; c="$(menu "$(L "Additional modules – programs that work with Plex Downloader" "Moduły dodatkowe – programy współpracujące z Plex Downloaderem")" "${args[@]}")"
    { [ -z "$c" ] || ! [[ "$c" =~ ^[0-9]+$ ]] || [ "$c" -ge "$i" ] || [ "$c" -lt 1 ]; } && return 1
    module_menu "${list[$((c - 1))]}"
    [ "$UI" = "text" ] && return 0
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
    7 "$(L "Additional modules: Plex, SMB, ffmpeg, VPN" "Moduły dodatkowe: Plex, SMB, ffmpeg, VPN")" \
    8 "$(L "Uninstall" "Odinstaluj")" \
    9 "$(L "Cancel" "Anuluj")")"
  if [ "$opt" = "6" ]; then
    server_menu && exit 0
    continue
  fi
  if [ "$opt" = "7" ]; then
    modules_menu && exit 0
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
  8)
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
