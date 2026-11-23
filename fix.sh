#!/usr/bin/env bash
# Plex Downloader – repair menu: update, server, repair and reinstall, add-ons, BETA, uninstall.
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

# the newest fix.sh / update.sh of this channel are used with every version (also older ones)
tools_refresh() {
  [ -n "${PLEXDL_TOOLS_FRESH:-}" ] && return 0
  command -v git >/dev/null 2>&1 || return 0
  local br f changed=0
  br="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; [ "$br" = "beta" ] || br="main"
  timeout 20 git fetch -q origin "+refs/heads/$br:refs/remotes/origin/$br" >/dev/null 2>&1 || return 0
  for f in fix.sh update.sh; do
    git cat-file -e "origin/$br:$f" 2>/dev/null || continue
    if ! git show "origin/$br:$f" 2>/dev/null | cmp -s - "$APP_DIR/$f"; then
      git show "origin/$br:$f" > "$APP_DIR/$f.new" 2>/dev/null && chmod +x "$APP_DIR/$f.new" \
        && mv -f "$APP_DIR/$f.new" "$APP_DIR/$f" && changed=1
    fi
  done
  [ $changed -eq 1 ] && PLEXDL_TOOLS_FRESH=1 exec "$APP_DIR/fix.sh" "$@"
  return 0
}
tools_refresh "$@"


# ---------------------------------------------------------------- menu: whiptail window or plain text
# Same numbers in both, so "fix.sh → 3 → 2" in the guides is always right.
UI="text"
if [ "${1:-}" != "--text" ] && command -v whiptail >/dev/null 2>&1 && [ -t 0 ] && [ -t 1 ] \
   && [ "$(tput cols 2>/dev/null || echo 0)" -ge 80 ] && [ "$(tput lines 2>/dev/null || echo 0)" -ge 20 ]; then
  UI="whiptail"
fi
TITLE="Plex Downloader"
W=78   # window width – the same in every window
# Same look in every terminal (macOS Terminal / iTerm over SSH showed two shades of grey and broken
# frame lines): one explicit colour set, and UTF-8 line drawing instead of the terminal's ACS characters.
if [ "$UI" = "whiptail" ]; then
  export NCURSES_NO_UTF8_ACS=1
  : "${NEWT_COLORS:=root=white,blue roottext=white,blue helpline=white,blue window=black,lightgray border=black,lightgray shadow=black,black title=red,lightgray textbox=black,lightgray listbox=black,lightgray sellistbox=black,lightgray actlistbox=white,red actsellistbox=white,red button=white,red actbutton=white,red compactbutton=black,lightgray entry=black,lightgray disentry=gray,lightgray checkbox=black,lightgray actcheckbox=white,red emptyscale=,gray fullscale=,red}"
  export NEWT_COLORS
fi

UI_LANG="en"
L() { if [ "$UI_LANG" = "pl" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

# number of screen lines a text takes inside a window (about 74 characters per line)
box_lines() {
  local n=0 line
  while IFS= read -r line; do n=$(( n + 1 + ${#line} / 74 )); done <<< "$1"
  echo "$n"
}

# menu "question" tag1 "text1" tag2 "text2" … → prints the chosen tag (empty = Esc / Back)
# MENU_CANCEL=… menu …  changes the label of the second button (default: Back)
menu() {
  local q="$1"; shift
  if [ "$UI" = "whiptail" ]; then
    local n=$(( $# / 2 ))
    whiptail --title "$TITLE" --ok-button "OK" --cancel-button "${MENU_CANCEL:-$(L "Back" "Wróć")}" \
      --menu "$q" $(( n + 7 + $(box_lines "$q") )) $W "$n" "$@" 3>&1 1>&2 2>&3 || true
  else
    echo >&2
    echo "$q" | sed 's/^/  /' >&2
    while [ $# -gt 1 ]; do echo "    $1) $2" >&2; shift 2; done
    local a; read -r -p "  > " a || a=""
    echo "$a"
  fi
}

# checklist "question" tag1 "text1" … → chosen tags, one per line (nothing is ticked at the start)
checklist() {
  local q="$1"; shift
  if [ "$UI" = "whiptail" ]; then
    local n=$(( $# / 2 )) args=()
    while [ $# -gt 1 ]; do args+=("$1" "$2" OFF); shift 2; done
    whiptail --title "$TITLE" --ok-button "OK" --cancel-button "$(L "Back" "Wróć")" --notags --separate-output \
      --checklist "$q" $(( n + 7 + $(box_lines "$q") )) $W "$n" "${args[@]}" 3>&1 1>&2 2>&3
  else
    echo >&2
    echo "$q" | sed 's/^/  /' >&2
    local i=1 tags=() a x
    while [ $# -gt 1 ]; do echo "    $i) $2" >&2; tags+=("$1"); i=$((i + 1)); shift 2; done
    read -r -p "  $(L "Numbers separated by spaces (Enter = none):" "Numery oddzielone spacjami (Enter = żaden):") " a || a=""
    for x in $a; do
      [[ "$x" =~ ^[0-9]+$ ]] && [ "$x" -ge 1 ] && [ "$x" -lt "$i" ] && echo "${tags[$((x - 1))]}"
    done
    return 0
  fi
}

# clean screen before text output (window mode)
screen_clear() { [ "$UI" = "whiptail" ] && { clear 2>/dev/null || true; }; echo; }

# pause after text output (status, logs) in window mode
pause() { [ "$UI" = "whiptail" ] && { echo; read -r -p "  $(L "Press Enter to go back…" "Naciśnij Enter, aby wrócić…")" _ || true; }; }
pause_continue() { [ "$UI" = "whiptail" ] && { echo; read -r -p "  $(L "Press Enter to continue…" "Naciśnij Enter, aby kontynuować…")" _ || true; }; }

confirm() {  # confirm "text" → 0 if the user typed YES/TAK
  local word a q; word="$(L YES TAK)"
  q="$1"$'\n\n'"$(L "Type YES to continue:" "Wpisz TAK, aby kontynuować:")"
  if [ "$UI" = "whiptail" ]; then
    a="$(whiptail --title "$TITLE" --ok-button "OK" --cancel-button "$(L "Cancel" "Anuluj")" \
         --inputbox "$q" $(( $(box_lines "$q") + 8 )) $W 3>&1 1>&2 2>&3)" || a=""
  else
    echo
    echo "$q" | sed 's/^/  /'
    read -r -p "  > " a || a=""
  fi
  [ "${a^^}" = "$word" ]
}

ask_yes_no() {  # ask_yes_no "question" → 0 = yes (default: no)
  if [ "$UI" = "whiptail" ]; then
    whiptail --title "$TITLE" --defaultno --yes-button "$(L Yes Tak)" --no-button "$(L No Nie)" \
      --yesno "$1" $(( $(box_lines "$1") + 6 )) $W
  else
    echo
    echo "$1" | sed 's/^/  /'
    local a; read -r -p "  [$(L "y/N" "t/N")]: " a || a=""
    [[ "$a" =~ ^[yYtT] ]]
  fi
}

cancelled() { screen_clear; echo "  $(L "Cancelled – nothing was changed." "Anulowano – nic nie zostało zmienione.")"; echo; }

# ---------------------------------------------------------------- language
# Taken from the panel settings; the question appears only when no language is known yet.
lang_menu() {
  local c
  c="$(UI_LANG=en; MENU_CANCEL="Cancel / Anuluj" menu "Choose language / Wybierz język:" 1 "English (default)" 2 "Polski (Polish)")"
  case "$c" in 1) UI_LANG="en" ;; 2) UI_LANG="pl" ;; esac
}
UI_LANG="${PLEXDL_LANG:-}"
if [ -z "$UI_LANG" ] && [ -f "$APP_DIR/config.json" ]; then
  UI_LANG="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("language", ""))' "$APP_DIR/config.json" 2>/dev/null || true)"
fi
case "$UI_LANG" in
  en|pl) ;;
  *) UI_LANG="en"; lang_menu ;;
esac
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
  git checkout -q -- fix.sh update.sh 2>/dev/null || true
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

# ---------------------------------------------------------------- 2. server
server_check_started() {
  if systemctl is-active --quiet "$SERVICE"; then
    c_ok "$1 $(panel_url)"
  else
    c_warn "$(L "The server did not start. Check:" "Serwer nie wystartował. Sprawdź:")"
    echo "    journalctl -u $SERVICE -n 50"
  fi
}

server_menu() {
  while true; do
    local state toggle auto
    state="$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
    if [ "$state" = "active" ]; then
      toggle="$(L "Stop server (autostart stays on)" "Wstrzymaj serwer (autostart bez zmian)")"
    else
      toggle="$(L "Start server (no Raspberry Pi restart needed)" "Uruchom serwer (bez restartu Raspberry Pi)")"
    fi
    if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null; then
      auto="$(L "Autostart: on → turn off (does not start after a restart)" "Autostart: włączony → wyłącz (nie wystartuje po restarcie)")"
    else
      auto="$(L "Autostart: off → turn on (starts after every restart)" "Autostart: wyłączony → włącz (startuje po każdym restarcie)")"
    fi
    local s
    s="$(menu "$(L "Plex Downloader server – status:" "Serwer Plex Downloader – stan:") ${state:-unknown}" \
         1 "$(L "Check server status" "Sprawdź status serwera")" \
         2 "$toggle" \
         3 "$(L "Restart the server" "Uruchom serwer ponownie (restart)")" \
         4 "$auto" \
         5 "$(L "Back" "Powrót")")"
    case "$s" in
      1)
        screen_clear
        echo "  Plex Downloader $CUR"
        echo "  $(L "Service:" "Usługa:")    $(systemctl is-active "$SERVICE" 2>/dev/null || echo unknown)"
        echo "  $(L "Autostart:" "Autostart:") $(systemctl is-enabled "$SERVICE" 2>/dev/null || echo unknown)"
        echo "  $(L "Panel:" "Panel:")      $(panel_url)"
        echo
        echo "  $(L "Last log entries:" "Ostatnie wpisy logu:")"
        { journalctl -u "$SERVICE" -n 10 --no-pager 2>/dev/null || sudo journalctl -u "$SERVICE" -n 10 --no-pager; } \
          | cut -c1-74 | sed 's/^/    /'
        ;;
      2)
        screen_clear
        if [ "$state" = "active" ]; then
          sudo systemctl stop "$SERVICE" && {
            c_ok "$(L "Server stopped." "Serwer wstrzymany.")"
            echo "  $(L "It starts again after a Raspberry Pi restart, or with option 2." "Wystartuje po restarcie Raspberry Pi albo opcją 2.")"
          }
        else
          sudo systemctl start "$SERVICE" && sleep 2
          server_check_started "$(L "Server started:" "Serwer uruchomiony:")"
        fi
        ;;
      3)
        screen_clear
        sudo systemctl restart "$SERVICE" && sleep 2
        server_check_started "$(L "Server restarted:" "Serwer uruchomiony ponownie:")"
        ;;
      4)
        if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null; then
          local stop_now=1
          ask_yes_no "$(L "Autostart will be turned off: after a Raspberry Pi restart the panel will not start by itself." "Autostart zostanie wyłączony: po restarcie Raspberry Pi panel nie uruchomi się sam.")"$'\n\n'"$(L "Also stop the server now?" "Wstrzymać też serwer teraz?")" || stop_now=0
          screen_clear
          sudo systemctl disable "$SERVICE" >/dev/null 2>&1
          if [ $stop_now -eq 1 ]; then
            sudo systemctl stop "$SERVICE"
            c_ok "$(L "Autostart off and server stopped." "Autostart wyłączony, serwer wstrzymany.")"
            echo "  $(L "Start it again with option 2. Turn autostart back on with option 4." "Uruchomisz go opcją 2. Autostart włączysz z powrotem opcją 4.")"
          else
            c_ok "$(L "Autostart off – the server keeps running until the next restart." "Autostart wyłączony – serwer działa do najbliższego restartu.")"
            echo "  $(L "Turn it back on here: the same option 4." "Włączysz go z powrotem tutaj: ta sama opcja 4.")"
          fi
        else
          screen_clear
          sudo systemctl enable --now "$SERVICE" >/dev/null 2>&1 && sleep 2
          c_ok "$(L "Autostart on – the server starts after every restart." "Autostart włączony – serwer startuje po każdym restarcie.")"
          server_check_started "$(L "Panel:" "Panel:")"
        fi
        ;;
      *) return 1 ;;   # back to the main menu
    esac
    pause
    [ "$UI" = "text" ] && return 0
  done
}
pkg_installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }
pkg_version()   { dpkg-query -W -f='${Version}' "$1" 2>/dev/null; }
apt_update()    { c_info "$(L "Refreshing the package list…" "Odświeżam listę pakietów…")"; sudo apt-get update -qq; }

# Raspbian (32-bit Raspberry Pi OS) downloads from a random mirror; some of them lose files of older
# releases (404) or are half-synced ("unexpected size"). The main archive always has them.
RASPBIAN_MIRROR="http://raspbian.raspberrypi.org/raspbian"
RASPBIAN_MAIN="http://archive.raspbian.org/raspbian"
mirror_fix() {
  grep -q "$RASPBIAN_MIRROR" /etc/apt/sources.list 2>/dev/null || return 1
  c_warn "$(L "Some packages could not be downloaded from a Raspbian mirror (the mirror is broken or still syncing)." "Części pakietów nie udało się pobrać z serwera lustrzanego Raspbiana (serwer jest uszkodzony albo w trakcie synchronizacji).")"
  ask_yes_no "$(L "Download from the main Raspbian archive instead (archive.raspbian.org) and try again? A copy of the package source list is kept (/etc/apt/sources.list.bak)." "Pobierać z głównego archiwum Raspbiana (archive.raspbian.org) i spróbować ponownie? Kopia listy źródeł zostanie zachowana (/etc/apt/sources.list.bak).")" || return 1
  sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
  sudo sed -i "s#$RASPBIAN_MIRROR#$RASPBIAN_MAIN#" /etc/apt/sources.list
  c_ok "$(L "Package source: main Raspbian archive" "Źródło pakietów: główne archiwum Raspbiana")"
  apt_update
}

# apt_install pkg… – like apt-get install -y, but offers the main archive when a mirror fails
apt_install() {
  local log rc; log="$(mktemp)"
  sudo apt-get install -y "$@" 2>&1 | tee "$log"; rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ] && grep -qE "404 +Not Found|unexpected size|Hash Sum mismatch|Failed to fetch|Nie udało się pobrać" "$log" \
     && mirror_fix; then
    sudo apt-get install -y "$@"; rc=$?
  fi
  rm -f "$log"
  return "$rc"
}

# ---------------------------------------------------------------- 4. add-ons (Plex, SMB, ffmpeg, VPN)
# Each add-on: status first, then the actions that make sense for that status.
MODULES="plex samba cifs ffmpeg tailscale wireguard"
mod_name() {
  case "$1" in
    plex)      echo "Plex Media Server" ;;
    samba)     L "Samba – share folders (SMB server)" "Samba – udostępnianie folderów (serwer SMB)" ;;
    cifs)      L "SMB client – mount shares (cifs)" "Klient SMB – montowanie udziałów (cifs)" ;;
    ffmpeg)    L "ffmpeg – posters from video frames" "ffmpeg – plakaty z kadrów filmu" ;;
    tailscale) L "Tailscale VPN (recommended)" "Tailscale VPN (zalecany)" ;;
    wireguard) echo "WireGuard VPN" ;;
  esac
}
mod_label() {   # short name for messages
  case "$1" in
    plex) echo "Plex Media Server" ;; samba) echo "Samba" ;; cifs) echo "cifs-utils" ;;
    ffmpeg) echo "ffmpeg" ;; tailscale) echo "Tailscale" ;; wireguard) echo "WireGuard" ;;
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
short_ver() { local v="${1#*:}"; echo "${v%%[-+~]*}"; }   # 2:4.17.12+dfsg-0 → 4.17.12
mod_state() {     # short state for the lists: "✔ 1.80.2", "✔ 1.80.2, stopped", "none"
  local pkg svc; pkg="$(mod_pkg "$1")"; svc="$(mod_service "$1")"
  if ! pkg_installed "$pkg"; then L "none" "brak"; return; fi
  printf '✔ %s' "$(short_ver "$(pkg_version "$pkg")")"
  if [ -n "$svc" ]; then
    systemctl is-active --quiet "$svc" || printf ', %s' "$(L "stopped" "zatrzymany")"
    systemctl is-enabled --quiet "$svc" 2>/dev/null || printf ', %s' "$(L "no autostart" "bez autostartu")"
  fi
}

mod_status() {
  local m="$1" pkg svc ip; pkg="$(mod_pkg "$m")"; svc="$(mod_service "$m")"
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  screen_clear
  echo "  $(mod_name "$m")"
  if pkg_installed "$pkg"; then
    local line; line="$(L "Installed:" "Zainstalowano:") $(short_ver "$(pkg_version "$pkg")")"
    if [ -n "$svc" ]; then
      line="$line  ·  $(L "service:" "usługa:") $(systemctl is-active "$svc" 2>/dev/null || echo unknown)"
      line="$line  ·  autostart: $(systemctl is-enabled "$svc" 2>/dev/null || echo unknown)"
    fi
    echo "  $line"
  else
    echo "  $(L "Not installed." "Nie zainstalowano.")"
  fi
  case "$m" in
    plex)
      echo "  $(L "Plex runs as the user 'plex' – it needs read access" "Plex działa jako użytkownik 'plex' – potrzebuje prawa odczytu")"
      echo "  $(L "to the library folders." "folderów biblioteki.")"
      pkg_installed "$pkg" && echo "  $(L "Plex web app:" "Aplikacja Plex w przeglądarce:") http://${ip:-<raspberry-pi-ip>}:32400/web" ;;
    samba)
      if pkg_installed "$pkg"; then
        echo "  $(L "Shares:" "Udziały:")"
        testparm -s 2>/dev/null | grep -E '^\[' | grep -viE '^\[(global|printers|print\$)\]' | sed 's/^/    /' \
          | grep . || echo "    –"
      else
        echo "  $(L "Lets Windows, macOS and other devices open" "Pozwala otwierać foldery biblioteki przez sieć")"
        echo "  $(L "the library folders over the network." "z Windows, macOS i innych urządzeń.")"
      fi ;;
    cifs)
      echo "  $(L "Mounted SMB shares:" "Zamontowane udziały SMB:")"
      findmnt -t cifs -n -o TARGET,SOURCE 2>/dev/null | sed 's/^/    /' | grep . || echo "    –" ;;
    ffmpeg)
      echo "  $(L "Turn it on in the panel: Settings → Preview & posters." "Włączysz w panelu: Ustawienia → Podgląd i plakaty.")" ;;
    tailscale)
      if pkg_installed "$pkg"; then
        local tip; tip="$(tailscale ip -4 2>/dev/null | head -1)"
        if [ -n "$tip" ]; then
          echo "  $(L "Logged in – VPN address:" "Zalogowano – adres w VPN:") $tip"
        else
          echo "  $(L "Not logged in – log in in the panel: Settings → VPN." "Nie zalogowano – zalogujesz się w panelu: Ustawienia → VPN.")"
        fi
      else
        echo "  $(L "Remote access to the panel without opening ports on the router." "Zdalny dostęp do panelu bez otwierania portów na routerze.")"
      fi
      echo "  $(L "Status, panel address and QR code for the phone: panel → Settings → VPN." "Status, adres panelu i kod QR dla telefonu: panel → Ustawienia → VPN.")" ;;
    wireguard)
      if ! pkg_installed "$pkg"; then
        echo "  $(L "For advanced users – needs a port opened on the router." "Dla zaawansowanych – wymaga otwarcia portu na routerze.")"
        echo "  $(L "Easier option: Tailscale." "Łatwiejsza opcja: Tailscale.")"
      elif [ -f /etc/wireguard/wg0.conf ]; then
        sudo wg show 2>/dev/null | sed 's/^/    /'
      else
        echo "  $(L "No configuration yet (/etc/wireguard/wg0.conf) – keys and peers" "Brak konfiguracji (/etc/wireguard/wg0.conf) – klucze i połączenia")"
        echo "  $(L "are set up by hand (guide, Stage 6). Tailscale is simpler." "ustawia się ręcznie (instrukcja, Etap 6). Tailscale jest prostszy.")"
      fi ;;
  esac
}

# The panel runs as this user; as the Tailscale "operator" it may log in / switch Tailscale on itself.
app_user() { local u; u="$(systemctl show -p User --value plex-downloader 2>/dev/null)"; echo "${u:-$(id -un)}"; }
ts_operator() {
  sudo tailscale set --operator="$(app_user)" 2>/dev/null \
    && echo "  $(L "The panel may now log in to Tailscale (Settings → VPN)." "Panel może teraz logować się do Tailscale (Ustawienia → VPN).")"
}

mod_install() {
  local m="$1" pkg; pkg="$(mod_pkg "$m")"
  case "$m" in
    plex)
      sudo apt-get install -y -qq curl gnupg >/dev/null
      curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | sudo gpg --dearmor --yes -o /usr/share/keyrings/plex.gpg
      echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://downloads.plex.tv/repo/deb public main" \
        | sudo tee /etc/apt/sources.list.d/plexmediaserver.list >/dev/null
      apt_update && apt_install plexmediaserver ;;
    tailscale)
      if ! curl -fsSL https://tailscale.com/install.sh | sh; then
        # the Tailscale repository is added first – a failure after that is usually a broken Raspbian mirror
        [ -f /etc/apt/sources.list.d/tailscale.list ] && mirror_fix && apt_install tailscale tailscale-archive-keyring || return 1
      fi
      ts_operator
      if ask_yes_no "$(L "Log in to Tailscale now? A link to open in the browser will be shown." "Zalogować się teraz do Tailscale? Pojawi się link do otwarcia w przeglądarce.")"; then
        screen_clear
        sudo tailscale up
      else
        echo "  $(L "Log in later in the panel (Settings → VPN) or with:" "Zalogujesz się później w panelu (Ustawienia → VPN) albo poleceniem:")"
        echo "    sudo tailscale up"
      fi ;;
    ffmpeg)
      echo "  $(L "This takes a few minutes – the screen may stand still, do not interrupt." "To potrwa kilka minut – ekran może stać, nie przerywaj.")"
      apt_update && apt_install ffmpeg ;;
    *) apt_update && apt_install "$pkg" ;;
  esac
  pkg_installed "$pkg" || return 1
  c_ok "$(L "Installed:" "Zainstalowano:") $(mod_label "$m") $(short_ver "$(pkg_version "$pkg")")"
  case "$m" in
    plex)      echo "  $(L "Open:" "Otwórz:") http://$(hostname -I | awk '{print $1}'):32400/web" ;;
    samba)     echo "  $(L "Share folders and passwords: see the guide, Stage 4." "Udostępnianie folderów i hasła: instrukcja, Etap 4.")" ;;
    cifs)      echo "  $(L "Mounting a share (fstab line): see the guide, Stage 4." "Montowanie udziału (linia w fstab): instrukcja, Etap 4.")" ;;
    ffmpeg)    echo "  $(L "Turn it on in the panel: Settings → Preview & posters." "Włączysz w panelu: Ustawienia → Podgląd i plakaty.")" ;;
    wireguard) echo "  $(L "Configuration (keys, router port): see the guide, Stage 6." "Konfiguracja (klucze, port na routerze): instrukcja, Etap 6.")" ;;
  esac
}

mod_update() {
  local pkg old; pkg="$(mod_pkg "$1")"; old="$(short_ver "$(pkg_version "$pkg")")"
  apt_update && apt_install --only-upgrade "$pkg" || return 1
  local new; new="$(short_ver "$(pkg_version "$pkg")")"
  if [ "$old" = "$new" ]; then
    c_ok "$(mod_label "$1") – $(L "up to date:" "aktualna wersja:") $new"
  else
    c_ok "$(L "Updated:" "Zaktualizowano:") $(mod_label "$1") $old → $new"
  fi
  [ "$1" = "tailscale" ] && ts_operator
  return 0
}

# warning shown before removing an add-on
mod_remove_note() {
  case "$1" in
    plex)      L "Plex Media Server will be removed. Movies and TV shows on the disks stay untouched. Whether to delete the Plex library database (watched status, posters, collections) you decide in the next step." \
                 "Plex Media Server zostanie usunięty. Filmy i seriale na dyskach pozostaną nietknięte. O usunięciu bazy biblioteki Plexa (obejrzane, plakaty, kolekcje) zdecydujesz w następnym kroku." ;;
    samba)     L "Other devices will no longer see the shares. Files stay; /etc/samba/smb.conf is kept." \
                 "Inne urządzenia przestaną widzieć udziały. Pliki zostają; /etc/samba/smb.conf jest zachowany." ;;
    cifs)      if findmnt -t cifs -n >/dev/null 2>&1; then
                 L "Shares are mounted now – they stop working after a restart (remove them from /etc/fstab)." \
                   "Udziały są teraz zamontowane – po restarcie przestaną działać (usuń je z /etc/fstab)."
               else L "SMB shares can no longer be mounted." "Nie będzie można montować udziałów SMB."; fi ;;
    ffmpeg)    L "Posters from video frames will not be created any more (saved ones stay)." \
                 "Plakaty z kadrów nie będą już tworzone (zapisane zostają)." ;;
    tailscale) L "Tailscale will be removed and this Raspberry Pi logs out of your Tailscale account. Remote access stops. If you are connected over the VPN right now, this connection will drop." \
                 "Tailscale zostanie usunięty, a ta Malina wyloguje się z Twojego konta Tailscale. Dostęp zdalny przestanie działać. Jeśli łączysz się teraz przez VPN, to połączenie zostanie zerwane." ;;
    wireguard) L "WireGuard connections of this Raspberry Pi stop working." "Połączenia WireGuard tej Maliny przestaną działać." ;;
  esac
}

plex_db_question() {
  ask_yes_no "$(L "Also delete the Plex library database (/var/lib/plexmediaserver: watched status, posters, collections, Plex settings)?" "Usunąć też bazę biblioteki Plexa (/var/lib/plexmediaserver: obejrzane, plakaty, kolekcje, ustawienia Plexa)?")"$'\n\n'"$(L "No = the database stays and a new Plex installation picks it up." "Nie = baza zostaje i nowa instalacja Plexa ją przejmie.")"
}

# mod_remove <module> – removes without asking (the caller has confirmed); Plex: asks about its database
mod_remove() {
  local m="$1" pkg; pkg="$(mod_pkg "$m")"
  case "$m" in
    plex)
      sudo systemctl stop plexmediaserver 2>/dev/null || true
      sudo apt-get purge -y -qq plexmediaserver >/dev/null
      sudo rm -f /etc/apt/sources.list.d/plexmediaserver.list /usr/share/keyrings/plex.gpg
      if [ -d /var/lib/plexmediaserver ]; then
        local del="${PLEX_DB_DELETE:-}"
        if [ -z "$del" ]; then plex_db_question && del=yes || del=no; fi
        [ "$del" = "yes" ] && sudo rm -rf /var/lib/plexmediaserver && c_ok "$(L "Plex library database deleted" "Usunięto bazę biblioteki Plexa")"
      fi ;;
    samba) sudo apt-get remove -y -qq samba >/dev/null ;;
    tailscale)
      sudo tailscale logout 2>/dev/null || sudo tailscale down 2>/dev/null || true
      sudo apt-get purge -y -qq tailscale >/dev/null
      sudo rm -f /etc/apt/sources.list.d/tailscale.list ;;
    wireguard)
      [ -f /etc/wireguard/wg0.conf ] && sudo systemctl disable --now wg-quick@wg0 2>/dev/null || true
      sudo apt-get purge -y -qq wireguard-tools wireguard >/dev/null 2>&1 || sudo apt-get purge -y -qq wireguard-tools >/dev/null ;;
    *) sudo apt-get purge -y -qq "$pkg" >/dev/null ;;
  esac
  sudo apt-get autoremove -y -qq >/dev/null 2>&1 || true
  if pkg_installed "$pkg"; then
    c_warn "$(L "Could not remove:" "Nie udało się usunąć:") $(mod_label "$m")"
    return 1
  fi
  c_ok "$(L "Removed:" "Usunięto:") $(mod_label "$m")"
  [ "$m" = "tailscale" ] && echo "  $(L "Remove the device from your account too: login.tailscale.com → Machines." "Usuń też urządzenie z konta: login.tailscale.com → Machines.")"
  return 0
}

mod_uninstall() {
  confirm "$(mod_remove_note "$1")" || { screen_clear; echo "  $(L "Cancelled – nothing was changed." "Anulowano – nic nie zostało zmienione.")"; return 0; }
  screen_clear
  mod_remove "$1"
  echo "  $(L "Your movies and TV shows were not touched." "Twoje filmy i seriale nie zostały ruszone.")"
}

module_menu() {
  local m="$1"
  mod_status "$m"; pause
  while true; do
    local pkg svc state; pkg="$(mod_pkg "$m")"; svc="$(mod_service "$m")"
    local args=() i=1 acts=()
    add() { args+=("$i" "$2"); acts+=("$1"); i=$((i + 1)); }
    add status "$(L "Check status" "Sprawdź status")"
    if ! pkg_installed "$pkg"; then
      state="$(L "not installed" "nie zainstalowano")"
      add install "$(L "Install" "Zainstaluj")"
    else
      state="$(mod_state "$m")"
      add update "$(L "Update" "Zaktualizuj")"
      if [ -n "$svc" ]; then
        if systemctl is-active --quiet "$svc"; then
          add stop "$(L "Stop (until the next restart – autostart stays on)" "Zatrzymaj (do restartu – autostart bez zmian)")"
          add restart "$(L "Restart" "Uruchom ponownie (restart)")"
        else
          add start "$(L "Start" "Uruchom")"
        fi
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
          add autostart_off "$(L "Autostart: on → turn off (does not start after a restart)" "Autostart: włączony → wyłącz (nie wystartuje po restarcie)")"
        else
          add autostart_on "$(L "Autostart: off → turn on (starts after every restart)" "Autostart: wyłączony → włącz (startuje po każdym restarcie)")"
        fi
      fi
      add uninstall "$(L "Uninstall completely" "Odinstaluj całkowicie")"
    fi
    add back "$(L "Back" "Powrót")"
    local c; c="$(menu "$(mod_name "$m") – $state" "${args[@]}")"
    { [ -z "$c" ] || ! [[ "$c" =~ ^[0-9]+$ ]] || [ "$c" -lt 1 ] || [ "$c" -ge "$i" ]; } && return 0
    local act="${acts[$((c - 1))]}"
    case "$act" in
      status)  mod_status "$m" ;;
      install) screen_clear; mod_install "$m" ;;
      update)  screen_clear; mod_update "$m" ;;
      stop)
        if [ "$m" = "tailscale" ] && ! ask_yes_no "$(L "Stop Tailscale? Remote access stops until the next restart." "Zatrzymać Tailscale? Dostęp zdalny przestanie działać do najbliższego restartu.")"$'\n\n'"$(L "If you are connected over the VPN right now, this connection will drop." "Jeśli łączysz się teraz przez VPN, to połączenie zostanie zerwane.")"; then
          continue
        fi
        screen_clear
        sudo systemctl stop "$svc" && c_ok "$(L "Stopped – starts again after a restart." "Zatrzymano – wystartuje po restarcie.")" ;;
      start)   screen_clear; sudo systemctl start "$svc" && sleep 1 && c_ok "$(L "Started:" "Uruchomiono:") $(systemctl is-active "$svc")" ;;
      restart) screen_clear; sudo systemctl restart "$svc" && sleep 1 && c_ok "$(L "Restarted:" "Uruchomiono ponownie:") $(systemctl is-active "$svc")" ;;
      autostart_off)
        screen_clear
        sudo systemctl disable "$svc" >/dev/null 2>&1 && c_ok "$(L "Autostart off – it stays off after a restart." "Autostart wyłączony – po restarcie się nie uruchomi.")"
        if [ "$m" = "tailscale" ]; then
          echo "  $(L "After a Raspberry Pi restart remote access will not work" "Po restarcie Raspberry Pi dostęp zdalny nie zadziała,")"
          echo "  $(L "until you turn autostart back on (the same option)." "dopóki nie włączysz autostartu z powrotem (ta sama opcja).")"
        else
          echo "  $(L "Turn it back on here: the same option." "Włączysz go z powrotem tutaj: ta sama opcja.")"
        fi ;;
      autostart_on)
        screen_clear
        sudo systemctl enable --now "$svc" >/dev/null 2>&1 && sleep 1 \
          && c_ok "$(L "Autostart on – running:" "Autostart włączony – działa:") $(systemctl is-active "$svc")" ;;
      uninstall)
        mod_uninstall "$m"
        pause
        [ "$UI" = "text" ] && return 0
        pkg_installed "$pkg" || return 0 ;;   # removed → back to the add-on list
      *) return 0 ;;
    esac
    [ "$act" = "uninstall" ] && continue
    pause
    [ "$UI" = "text" ] && return 0
  done
}

modules_menu() {
  while true; do
    local args=() i=1 list=() m
    for m in $MODULES; do args+=("$i" "$(mod_name "$m") – $(mod_state "$m")"); list+=("$m"); i=$((i + 1)); done
    args+=("$i" "$(L "Back" "Powrót")")
    local c; c="$(menu "$(L "Add-ons – programs that work with Plex Downloader" "Dodatki – programy współpracujące z Plex Downloaderem")" "${args[@]}")"
    { [ -z "$c" ] || ! [[ "$c" =~ ^[0-9]+$ ]] || [ "$c" -ge "$i" ] || [ "$c" -lt 1 ]; } && return 1
    module_menu "${list[$((c - 1))]}"
    [ "$UI" = "text" ] && return 0
  done
}

# ---------------------------------------------------------------- 3. repair and reinstall
PIN="$APP_DIR/.pinned-version"
VSNAP="$APP_DIR/.version-snapshots"

do_reinstall() {
  screen_clear
  fetch_all || exit 1
  stop_service
  switch_code "$BRANCH" || exit 1
  c_info "$(L "Rebuilding the Python environment…" "Odbudowuję środowisko Pythona…")"
  rm -rf "$APP_DIR/venv"
  run_setup
}

do_clean_reinstall() {
  local note=""
  [ $ON_BETA -eq 1 ] && note=$'\n'"$(L "The stable version is installed – this also leaves BETA." "Instalowana jest wersja stabilna – to także wyjście z BETA.")"
  confirm "$(L "This deletes: settings (config.json, login and password), settings backups, activity logs and the download list. Movies and TV shows on the disks stay untouched." "Zostaną usunięte: ustawienia (config.json, login i hasło), kopie ustawień, dzienniki aktywności i lista pobierań. Filmy i seriale na dyskach pozostaną nietknięte.")$note" \
    || { cancelled; exit 0; }
  screen_clear
  fetch_all || exit 1
  stop_service
  switch_code main || exit 1
  rm -rf "$APP_DIR/venv" "$SNAP"
  rm -f "$PIN"
  wipe_settings
  c_ok "$(L "Settings, backups and logs removed" "Usunięto ustawienia, kopie i logi")"
  run_setup
}

# list of stable versions from releases.txt; 0 = a version was installed, 1 = back
version_menu() {
  screen_clear
  fetch_all || { pause; return 1; }
  local list
  list="$(git show origin/main:releases.txt 2>/dev/null || git show origin/beta:releases.txt 2>/dev/null)" || true
  list="$(printf '%s\n' "$list" | grep -v '^#' | grep '|' || true)"
  if [ -z "$list" ]; then
    c_warn "$(L "The list of versions is not available right now." "Lista wersji jest teraz niedostępna.")"
    pause; return 1
  fi
  while true; do
    local args=() vers=() commits=() i=1 ver commit en pl desc suffix max
    while IFS='|' read -r ver commit en pl; do
      desc="$(L "$en" "$pl")"; suffix=""
      [ "$ver" = "$CUR" ] && suffix=" ($(L "installed" "zainstalowana"))"
      max=$(( 64 - ${#ver} - ${#suffix} ))
      [ "${#desc}" -gt "$max" ] && desc="${desc:0:$((max - 1))}…"
      args+=("$i" "$ver – $desc$suffix"); vers+=("$ver"); commits+=("$commit"); i=$((i + 1))
    done <<< "$list"
    args+=("$i" "$(L "Back" "Powrót")")
    local c; c="$(menu "$(L "Install another stable version" "Zainstaluj inną wersję stabilną") · $(L "now" "teraz"): $CUR" "${args[@]}")"
    { [ -z "$c" ] || ! [[ "$c" =~ ^[0-9]+$ ]] || [ "$c" -ge "$i" ] || [ "$c" -lt 1 ]; } && return 1
    local target="${vers[$((c - 1))]}" ref="${commits[$((c - 1))]}"
    if [ "$target" = "$CUR" ] && [ $ON_BETA -eq 0 ]; then
      screen_clear
      echo "  $(L "This version is already installed:" "Ta wersja jest już zainstalowana:") $CUR"
      pause; [ "$UI" = "text" ] && return 0; continue
    fi
    if ! git cat-file -e "$ref^{commit}" 2>/dev/null; then
      screen_clear
      c_warn "$(L "Version $target was not found on GitHub." "Nie znaleziono wersji $target na GitHubie.")"
      pause; [ "$UI" = "text" ] && return 0; continue
    fi
    local note=""
    [ $ON_BETA -eq 1 ] && note=$'\n'"$(L "This also leaves BETA – your current settings are kept." "To także wyjście z BETA – obecne ustawienia zostają.")"
    ask_yes_no "$(L "Install Plex Downloader" "Zainstalować Plex Downloader") $target ($(L "now" "teraz") $CUR)?"$'\n\n'"$(L "Your settings are kept and copied to .version-snapshots first. Movies are not touched." "Ustawienia zostają, a ich kopia trafia najpierw do .version-snapshots. Filmy nie są ruszane.")"$'\n'"$(L "Back to the newest version: main menu → 1 Update." "Powrót do najnowszej wersji: menu główne → 1 Aktualizacja.")$note" \
      || { [ "$UI" = "text" ] && { cancelled; return 0; }; continue; }
    screen_clear
    local tools; tools="$(mktemp -d)"; cp -p "$APP_DIR/fix.sh" "$APP_DIR/update.sh" "$tools/" 2>/dev/null
    local snap="$VSNAP/$(date +%Y%m%d-%H%M)-$CUR"
    mkdir -p "$snap"
    [ -f config.json ] && cp -p config.json "$snap/"
    [ -d backups ] && cp -rp backups "$snap/"
    c_ok "$(L "Settings copied to" "Kopia ustawień:") ${snap/#$HOME/\~}"
    stop_service
    git checkout -q -- fix.sh update.sh 2>/dev/null || true
    git checkout -q -B main "$ref" && git branch -q --set-upstream-to=origin/main main 2>/dev/null
    git reset -q --hard "$ref" || { c_warn "$(L "Switching failed." "Przełączenie nie powiodło się.")"; return 0; }
    cp -p "$tools/fix.sh" "$tools/update.sh" "$APP_DIR/" 2>/dev/null; rm -rf "$tools"
    # newest stable (the code may differ only in releases.txt) → not an „older version”
    if git diff --quiet HEAD origin/main -- . ':(exclude)releases.txt' ':(exclude)fix.sh' ':(exclude)update.sh' ':(exclude)*.md' 2>/dev/null; then rm -f "$PIN"; else echo "$target" > "$PIN"; fi
    "$APP_DIR/venv/bin/pip" install -q -r requirements.txt
    sudo systemctl restart "$SERVICE" && sleep 2
    c_ok "$(L "Installed" "Zainstalowano"): $CUR → $(cat VERSION)  ·  $(panel_url)"
    return 0
  done
}

repair_menu() {
  while true; do
    local c
    c="$(menu "$(L "Repair and reinstall" "Naprawa i reinstalacja")" \
         1 "$(L "Reinstall (keep settings)" "Reinstalacja (zachowaj ustawienia)")" \
         2 "$(L "Clean reinstall (deletes settings)" "Czysta reinstalacja (usuwa ustawienia)")" \
         3 "$(L "Install another version" "Zainstaluj inną wersję")" \
         4 "$(L "Back" "Powrót")")"
    case "$c" in
      1) do_reinstall; exit 0 ;;
      2) do_clean_reinstall; exit 0 ;;
      3) version_menu && return 0 ;;
      *) return 1 ;;
    esac
    [ "$UI" = "text" ] && return 0
  done
}

# ---------------------------------------------------------------- 1. update · 5. BETA
do_beta_install() {   # install BETA, or update it when already on BETA
  screen_clear
  fetch_all || exit 1
  if ! git rev-parse -q --verify origin/beta >/dev/null; then
    c_warn "$(L "No BETA version is available right now." "W tej chwili nie ma wersji BETA.")"
    exit 0
  fi
  local new; new="$(git show origin/beta:VERSION 2>/dev/null || echo '?')"
  if [ $ON_BETA -eq 1 ] && [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/beta)" ]; then
    c_ok "$(L "You have the latest BETA" "Masz najnowszą BETA"): $CUR"
    exit 0
  fi
  if [ $ON_BETA -eq 0 ]; then
    echo "  $(L "BETA versions contain new, less tested features." "Wersje BETA zawierają nowe, mniej przetestowane funkcje.")"
    rm -rf "$SNAP"; mkdir -p "$SNAP"
    [ -f config.json ] && cp -p config.json "$SNAP/"
    [ -d backups ] && cp -rp backups "$SNAP/"
    c_ok "$(L "Stable settings saved" "Zapisano ustawienia wersji stabilnej")"
  fi
  stop_service
  switch_code beta || exit 1
  rm -f "$PIN"
  "$APP_DIR/venv/bin/pip" install -q -r requirements.txt
  sudo systemctl restart "$SERVICE"
  if [ $ON_BETA -eq 1 ]; then
    c_ok "$(L "BETA updated" "Zaktualizowano BETA"): $CUR → $new"
  else
    c_ok "$(L "BETA installed" "Zainstalowano BETA"): $CUR → $new"
    echo "  $(L "Update BETA later: main menu → 1 Update." "Aktualizacja BETA później: menu główne → 1 Aktualizacja.")"
    echo "  $(L "Back to stable: main menu → 5 → Leave BETA." "Powrót do stabilnej: menu główne → 5 → Wyjście z BETA.")"
  fi
}

do_beta_leave() {
  screen_clear
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
}

do_update() {
  if [ $ON_BETA -eq 1 ]; then do_beta_install; return; fi
  screen_clear
  fetch_all || exit 1
  local new; new="$(git show origin/main:VERSION 2>/dev/null || echo "$CUR")"
  if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
    c_ok "$(L "You have the latest version" "Masz najnowszą wersję"): $CUR"
    return 0
  fi
  echo "  $(L "Available:" "Dostępna:") $new"
  "$APP_DIR/update.sh" && rm -f "$PIN"
}

beta_menu() {
  local c
  if [ $ON_BETA -eq 1 ]; then
    c="$(menu "$(L "BETA version – now: BETA" "Wersja BETA – teraz: BETA") $CUR"$'\n'"$(L "Update BETA: main menu → 1 Update." "Aktualizacja BETA: menu główne → 1 Aktualizacja.")" \
         1 "$(L "Leave BETA (back to stable)" "Wyjście z BETA (powrót do stabilnej)")" \
         2 "$(L "Back" "Powrót")")"
    [ "$c" = "1" ] || return 1
    ask_yes_no "$(L "Back to the stable version?" "Wrócić do wersji stabilnej?")"$'\n\n'"$(L "Your settings from before BETA are restored – changes made while on BETA are lost." "Ustawienia sprzed BETA zostaną przywrócone – zmiany zrobione na BETA przepadną.")" \
      || return 1
    do_beta_leave; exit 0
  else
    c="$(menu "$(L "BETA version – now: stable" "Wersja BETA – teraz: stabilna") $CUR"$'\n'"$(L "BETA = new, less tested features. Your settings are saved and restored when you leave BETA." "BETA = nowe, mniej przetestowane funkcje. Ustawienia zostaną zapisane i przywrócone przy wyjściu z BETA.")" \
         1 "$(L "Switch to the latest BETA" "Przejdź na najnowszą BETA")" \
         2 "$(L "Back" "Powrót")")"
    [ "$c" = "1" ] || return 1
    do_beta_install; exit 0
  fi
}

# ---------------------------------------------------------------- 6. uninstall
do_uninstall() {   # do_uninstall "add-ons to remove too (space separated)"
  local addons="$1" q
  if [ -n "$addons" ]; then
    q="$(L "Plex Downloader and the selected add-ons will be removed. Uninstall?" "Plex Downloader i zaznaczone dodatki zostaną usunięte. Odinstalować?")"
  else
    q="$(L "The service will be stopped and removed from autostart. Uninstall Plex Downloader?" "Usługa zostanie zatrzymana i usunięta z autostartu. Odinstalować Plex Downloader?")"
  fi
  confirm "$q" || { cancelled; exit 0; }
  case " $addons " in
    *" plex "*) [ -d /var/lib/plexmediaserver ] && { plex_db_question && PLEX_DB_DELETE=yes || PLEX_DB_DELETE=no; } ;;
  esac
  screen_clear
  sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
  sudo rm -f "$UNIT"
  sudo systemctl daemon-reload
  local shown_dir="${APP_DIR/#$HOME/\~}" deleted=0
  if ask_yes_no "$(L "Also delete the application folder" "Usunąć też folder aplikacji") $shown_dir ($(L "settings, backups, logs" "ustawienia, kopie, logi"))?"$'\n\n'"$(L "No = the folder stays and a reinstall keeps your settings." "Nie = folder zostaje, a ponowna instalacja zachowa ustawienia.")"; then
    cd "$HOME" && rm -rf "$APP_DIR" && deleted=1
  fi
  screen_clear
  c_ok "$(L "Service removed" "Usługa usunięta")"
  # add-ons last, Tailscale at the very end: removing it can drop an SSH connection over the VPN
  local m
  for m in $addons; do [ "$m" != "tailscale" ] && mod_remove "$m"; done
  echo
  c_ok "$(L "Plex Downloader uninstalled" "Odinstalowano Plex Downloader")"
  if [ $deleted -eq 1 ]; then
    c_ok "$(L "Folder deleted" "Folder usunięty"): $shown_dir"
  else
    echo "  $(L "The folder $shown_dir stays (settings, backups, logs)." "Folder $shown_dir zostaje (ustawienia, kopie, logi).")"
  fi
  echo "  $(L "The aria2 package stays in the system. Remove it with:" "Pakiet aria2 zostaje w systemie. Usuniesz go poleceniem:")"
  echo "    sudo apt remove aria2"
  echo "  $(L "Your movies and TV shows were not touched." "Twoje filmy i seriale nie zostały ruszone.")"
  echo
  if [ $deleted -eq 1 ]; then
    echo "  $(L "Install again (two commands):" "Ponowna instalacja (dwa polecenia):")"
    echo "    git clone https://github.com/pwmeess/plex-downloader.git $shown_dir"
  else
    echo "  $(L "Install again with your settings:" "Ponowna instalacja z Twoimi ustawieniami:")"
  fi
  echo "    cd $shown_dir && ./setup.sh"
  case " $addons " in *" tailscale "*) echo; mod_remove tailscale ;; esac
  echo
}

uninstall_menu() {
  local c
  c="$(menu "$(L "Uninstall" "Odinstaluj")"$'\n'"$(L "Your movies and TV shows are never touched." "Twoje filmy i seriale nie są nigdy ruszane.")" \
       1 "$(L "Uninstall Plex Downloader" "Odinstaluj Plex Downloader")" \
       2 "$(L "Uninstall Plex Downloader and add-ons" "Odinstaluj Plex Downloader razem z dodatkami")" \
       3 "$(L "Back" "Powrót")")"
  case "$c" in
    1) do_uninstall ""; exit 0 ;;
    2)
      local args=() m
      for m in $MODULES; do
        pkg_installed "$(mod_pkg "$m")" || continue
        args+=("$m" "$(mod_label "$m") $(short_ver "$(pkg_version "$(mod_pkg "$m")")")")
      done
      if [ ${#args[@]} -eq 0 ]; then
        screen_clear
        echo "  $(L "No add-ons are installed – only Plex Downloader will be removed." "Żaden dodatek nie jest zainstalowany – usunięty zostanie tylko Plex Downloader.")"
        pause_continue
        do_uninstall ""; exit 0
      fi
      local q sel
      q="$(L "Which add-ons should be removed too?" "Które dodatki usunąć?")"
      [ "$UI" = "whiptail" ] && q="$q $(L "Space = tick / untick." "Spacja = zaznacz / odznacz.")"
      pkg_installed plexmediaserver && q="$q"$'\n'"$(L "Plex Media Server: you decide separately about its library database." "Plex Media Server: o jego bazie biblioteki zdecydujesz osobno.")"
      pkg_installed tailscale && q="$q"$'\n'"$(L "Tailscale is removed last – a connection over the VPN drops then." "Tailscale jest usuwany na końcu – połączenie przez VPN wtedy się zerwie.")"
      sel="$(checklist "$q" "${args[@]}")" || return 1
      do_uninstall "$(echo $sel)"; exit 0 ;;
    *) return 1 ;;
  esac
}

# ---------------------------------------------------------------- main menu
main_header() {
  local h; h="$(L "Repair menu" "Menu naprawy") · $CUR"
  [ $ON_BETA -eq 1 ] && h="$h · $(L "BETA version" "wersja BETA")"
  [ -f "$PIN" ] && [ "$(cat "$PIN")" = "$CUR" ] && h="$h · $(L "older version (newest: option 1)" "starsza wersja (najnowsza: opcja 1)")"
  printf '%s\n%s' "$h" "$(L "Your movies and TV shows are never touched." "Twoje filmy i seriale nie są nigdy ruszane.")"
}

while true; do
  opt="$(MENU_CANCEL="$(L "Cancel" "Anuluj")" menu "$(main_header)" \
    1 "$(L "Update (check and install)" "Aktualizacja (sprawdź i zainstaluj)")" \
    2 "$(L "Server: status, stop / start, restart" "Serwer: status, wstrzymaj / uruchom, restart")" \
    3 "$(L "Repair and reinstall" "Naprawa i reinstalacja")" \
    4 "$(L "Add-ons: Plex, SMB, ffmpeg, VPN" "Dodatki: Plex, SMB, ffmpeg, VPN")" \
    5 "$(L "BETA version: install, update, leave" "Wersja BETA: instalacja, aktualizacja, wyjście")" \
    6 "$(L "Uninstall" "Odinstaluj")" \
    7 "Language / Język" \
    8 "$(L "Cancel" "Anuluj")")"
  case "$opt" in
    1) do_update; echo; exit 0 ;;
    2) server_menu && exit 0 ;;
    3) repair_menu && exit 0 ;;
    4) modules_menu && exit 0 ;;
    5) beta_menu && exit 0 ;;
    6) uninstall_menu && exit 0 ;;
    7) lang_menu ;;
    *) cancelled; exit 0 ;;
  esac
done
