# Plex Downloader – roadmap

🇬🇧 **English** · 🇵🇱 [Polski](ROADMAP.pl.md) · Changelog: [CHANGELOG.md](CHANGELOG.md)

Last updated: 11 November 2026 · stable: **1.4.0** · BETA: **1.5.0-beta0**

## Ground rules (checked for every release)

- **Languages:** English is the default (also README, CHANGELOG and this roadmap, each with a Polish version next to it); Polish lives in `locales/pl.json`. Every new interface string gets a translation right away (enforced by a test).
- **Descriptions:** short labels in the interface; longer explanations go into ⓘ tooltips.
- **Scripts:** `setup.sh` and `fix.sh` start with a language choice (1 English – default, 2 Polski). `update.sh` is English only.
- **Data safety:** no script or feature deletes movies or TV shows without an explicit confirmation in the panel. Restoring a settings backup never changes the username or password.
- **Three installation scenarios** (every new feature, the wizard and the guides are checked against each):
  1. **Recommended:** Plex and Downloader on one Pi, library on external disks (SSD, USB stick).
  2. **Testing (not recommended):** one Pi without disks, library on the SD card, optionally shared over SMB.
  3. **Two devices:** Plex on one computer, Downloader with the File manager on another, both with fixed IPs; the library is reachable by both, e.g. a permanently mounted SMB or NFS share.
- **Numbering for 1.3:** the BETA steps are `1.3.0-beta1`, `-beta2`… until stable 1.3.0; after that the usual rule (BETA two steps ahead) applies again.
- **Two release lines:** stable on `main` (setup.sh, update.sh; the panel only announces stable) and BETA on `beta` (only via `fix.sh`). New features land in BETA first, then in stable. Every release gets a `vX.Y.Z` tag (BETA: `vX.Y.Z-beta`). Numbering: BETA is two steps ahead of stable (e.g. stable 1.2.6 → BETA 1.2.8-beta).
- **Before a release:** automated tests, screenshots in EN/PL and dark/light, README, CHANGELOG and this file updated.

## Released

See [CHANGELOG.md](CHANGELOG.md) for details.

| Version | Highlights |
|---|---|
| 1.0.0 | Downloads from direct links (aria2c, 6 connections), Plex naming, 3 disks, resume after restart, login, systemd service |
| 1.1.0 | Movie and TV preview card from TMDB |
| 1.2.0 | File manager (two columns, drag and drop, SHA-256 verified copies), categories, Plex editions and versions, Plex server status, settings backups, Settings window |
| 1.2.1 | EN/PL interface, dark and light themes, activity log, season and episode moves, "Update paths", terminal commands, `fix.sh` |
| 1.2.2 | Delete selected settings backups, collapsible commands, tooltip fix |
| 1.2.5 (stable) | Stable and BETA channels, update check for stable only, new `fix.sh` menu, no VPN preview |
| 1.2.6-beta | 1.2.2 with the VPN preview, first BETA |
| 1.2.6 (stable) | Two-stage move progress, "Skip SHA-256 verification", hidden TMDB key, phone and ⓘ layout fixes, neutral `ssh` address, translation test, English documentation |
| 1.2.8-beta | 1.2.6 + VPN preview; base for 1.3 |
| 1.2.7 (stable) | Better title recognition from pasted links; links that open a web page instead of a file are reported |
| 1.2.9-beta | 1.2.7 + VPN preview, `fix.sh` in a window with the Server submenu |
| 1.3.0-beta1 | Setup wizard (three installation types, disk and folder detection, network share commands) |
| 1.3.0-beta2 | Settings export / import with a preview of changes, “SD card (not recommended)” disk template |
| 1.3.0-beta3 | EN/PL guides (in the app + PDF); File manager: edit the Plex name, file types (versions / extras) and the poster (own image, video frame, TMDB); `fix.sh` Additional modules; wizard improvements after tests on a Pi Zero |
| 1.3.0-beta4 | `fix.sh` → Install another version; the wizard also starts after switching a fresh stable installation to BETA |
| 1.3.0 (stable) | Everything from 1.3.0-beta1…beta4 without the VPN preview: setup wizard, settings export / import, edit names and posters (own image, video frame, TMDB), Plex extras, EN/PL guides, `fix.sh` Additional modules and Install another version |
| 1.3.1 (stable) | Fix: moving TV shows without season folders (error 500) |
| 1.4.0-beta0 | 1.3.0 + VPN preview; base for 1.4 (no new features) |
| 1.4.0-beta1 | Working VPN tab (Tailscale status, address, QR code, login from the panel, devices) and VPN badge in the header |
| 1.4.0-beta2 | HTTPS in the VPN, home network only / + VPN, log out / change account, WireGuard status; `fix.sh` autostart on / off and main Raspbian archive |
| 1.4.0-beta3 | VPN chapter in the EN/PL guides (WireGuard: synthetic tests only) |
| 1.4.0 (stable) | Everything from 1.4.0-beta1…beta3: remote access over VPN (Tailscale status, QR code, login, HTTPS in the VPN, home network only / + VPN, WireGuard status), VPN chapter in the guides |
| 1.5.0-beta0 | 1.4.0 with a new version number; base for 1.5 (no new features) |

## To fix

All items from the previous list shipped in 1.2.6 / 1.2.8-beta. Remaining:
- [x] **Version tags on GitHub:** tags `v1.2.5` … `v1.4.0-beta0` are on GitHub; releases published for 1.3.0 (stable) and 1.4.0-beta0 (pre-release).

## Demo website (Netlify)

- [x] Demo (first 1.2.5, then 1.2.6, now **1.3.0**): the real interface with an in-browser simulation, EN/PL, welcome window, data kept for max. 24 h, log out wipes everything, external links blocked, made-up names, IPs and keys, generated posters.
- [x] Published at https://plexdownloader.netlify.app and linked from the README.
- [ ] Demo sources (`demo.js`, build script) in the repository under `demo/`, so it can be rebuilt with one command after each stable release.
- [x] Since 1.3: the guide link in the welcome window opens the EN/PL guide (HTML and PDF).

## 1.3 – first-run wizard, guides, version choice

**First-run wizard**
- [x] Steps: language → theme → installation type → disks and folders → Plex server → TMDB key (optional) → summary (the account is created by `setup.sh`).
- [x] Installation type (matches the three scenarios):
  - [x] "External disks (recommended)": scan connected disks (`lsblk`/`df`), suggest `Movies`, `TV Shows`, `Kids` folders.
  - [x] "Library on the SD card (not recommended)": mount point `/`, folders under `~/Plex/…` created automatically, warning about capacity, wear and speed (in ⓘ).
  - [x] "Plex on another device": Plex server IP, connection check, mounted network share, write test. ⓘ note that Plex and Downloader must see the same files (paths may differ).
- [x] Check write permissions and free space for every folder.
- [x] Create missing folders on request.
- [x] Links to the guides in every step: the guide chapter for that step opens in a new window (HTML, with PDF download).
- [x] Re-run the wizard from Settings.

**Settings**
- [x] Export and import settings (JSON, without the password; preview of changes on import).
- [x] Ready-made "Library on the SD card (not recommended)" template in the Disks tab.

**Guides (EN and PL, HTML in the app + PDF)**
- [x] Installing Plex Media Server on a Raspberry Pi:
  - [x] with external disks (fstab, permissions),
  - [x] test setup with the library on the SD card (not recommended): folder, SMB share, limitations.
- [x] Installing Plex Downloader (`setup.sh`, first login, wizard).
- [x] Two-device setup: fixed IPs, SMB/NFS share in fstab, adding the Plex server manually.
  - [x] Example (already in the README): one disk with two paths (`/media/ssd1` on the Plex Pi, `/mnt/ssd1` on the Downloader Pi), "Update paths" after an import, one category with different folder names on two disks (`Concerts` / `Live`) and both folders in one Plex library, a password with `\` in `.smbcredentials`.
- [x] Everyday use: File manager, settings backups, activity log, `update.sh`, `fix.sh`, factory reset.
- [x] Home network security (no DMZ, no port forwarding for 8800, strong passwords, Samba with `valid users`).

**Release steps**
- [x] `1.3.0-beta1`: first-run wizard (the `fix.sh` server submenu already shipped in 1.2.9-beta).
- [x] `1.3.0-beta2`: settings export / import, SD-card template.
- [x] `1.3.0-beta3`: EN/PL guides (HTML in the app + PDF).
  - [x] File manager: edit name and poster (pen icon on the card).
  - [x] Posters from video frames (ffmpeg): in the Edit window and automatically (Settings / wizard, off by default).
  - [x] `fix.sh` → Additional modules: Plex Media Server, Samba, SMB client, ffmpeg, Tailscale, WireGuard (status, install, update, stop / start, restart, uninstall).
- [x] `1.3.0-beta4`: "Install another version" in `fix.sh`; the wizard also starts after switching a fresh stable installation to BETA.
- [x] `1.3.0`: stable release.

**`fix.sh` – server submenu**
- [x] New option "Server" (in 1.2.9-beta): 1) check status (service state, autostart, panel address, last log lines), 2) stop the server – does not change autostart / start it again (shown depending on the state), 3) restart the service process, 4) back.
- [x] Menu look: `whiptail` window like `raspi-config` with the same numbers, plain text fallback (`--text`).

**Choosing a version in `fix.sh`**
- [x] Stable (`main`) and BETA (`beta`) lines; installing and leaving BETA in `fix.sh` (since 1.2.5 / 1.2.6-beta).
- [x] `CHANGELOG.md` (since 1.2.6).
- [x] Every release since **1.2.5** has a git tag `vX.Y.Z`; from 1.3.0 on each one also gets a GitHub release with notes.
- [x] New `fix.sh` option 8 "Install another version": list of stable versions since 1.2.5 with a short description (`releases.txt`, so it works without tags); copies `config.json` and the backups to `.version-snapshots`, switches the code, rebuilds the environment and restarts the service.
- [x] Panel and `update.sh` know when an older (pinned) version is installed; one step back to the latest. (the `fix.sh` header shows “older version”, the panel announces the newest stable, `update.sh` / option 1 go back).
- [x] Settings compatibility: newer versions migrate `config.json` automatically, older versions keep unknown keys; going back keeps the current settings, a copy from before the switch is in `.version-snapshots`.

## 1.4 – remote access over VPN

Release steps: `1.4.0-beta0` (= 1.3.0 + VPN preview, done) → `1.4.0-beta1` (VPN tab working, done) → `1.4.0-beta2` (HTTPS, home network only / + VPN, WireGuard status, done) → `1.4.0-beta3` (guide, done) → `1.4.0` (released).

The VPN preview (Settings tab and header badge) is visible only in BETA; it returns to stable together with the working feature.

- [x] Installing Tailscale with the sign-in link (and WireGuard): `fix.sh` → Additional modules (1.3.0-beta3, instead of a separate `setup-vpn.sh`).
- [x] VPN tab: Tailscale status and address, QR code for phones, login from the panel, devices in the VPN, header badge (1.4.0-beta1).
- [x] HTTPS in the VPN with Tailscale's own certificate (1.4.0-beta2).
- [x] "Home network only" or "home network + VPN"; WireGuard status; `fix.sh`: autostart on / off, main Raspbian archive when mirrors fail; log out / change account (1.4.0-beta2).
- [x] No open ports on the router (Tailscale).
- [x] EN/PL guide (Tailscale on the Pi, phone and computer; WireGuard checked in synthetic tests only) (1.4.0-beta3).

## 1.5 – TV shows, adding files from a computer and a USB stick

Release steps: `1.5.0-beta0` (= 1.4.0, done) → `1.5.0-beta1` … → `1.5.0`.

- [ ] TV shows: “Episodes / Whole show” switch on the selection bar; a whole show into an existing show folder is merged; conflicts: Skip existing (default) / Overwrite / Cancel.
- [ ] Episode view in the File manager: shared thumbnail, S01E01 labels, edit only season and episode, delete.
- [ ] Local moves and a few fixes from testing.
- [ ] Drag a file from the computer into the browser window: chunked upload with resume, progress bar, disk and category choice, Plex naming.
- [ ] Several files at once (e.g. a whole season with subtitles).
- [ ] Import from a USB stick plugged into the Pi: detection, file list, SHA-256 verified copy into the chosen category.
- [ ] Free-space check before uploading.

## Ideas to decide (no version yet)

Suggestions from Claude, not approved yet:
- [ ] Refresh the Plex library automatically after a download or move (needs a Plex token).
- [ ] Notification when a download finishes (e.g. Telegram or e-mail).
- [ ] Download schedule (e.g. nights only) and time-based speed limit.
- [ ] Disk health (SMART, temperature) in the Disks tab.
- [ ] Subtitle search and download (e.g. OpenSubtitles).
