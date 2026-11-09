# Changelog

All notable changes to Plex Downloader. Stable versions live on the `main` branch, BETA versions on the `beta` branch (installed only with `fix.sh`).

## 1.3.0-beta1 – 2026-11-09 (BETA)

- **Setup wizard:** shown after the first login of a new installation (existing installations are not affected) and available again in Settings → Account → Run setup wizard. Steps: language, theme, where the library is stored, disks and folders, Plex server, TMDB key, summary.
  - Three installation types: external disks (recommended), library on the SD card (not recommended, folders in the home folder) and Plex on another device (network share).
  - Mounted disks and network shares are detected; category folders are found automatically; every folder is checked for write permission and free space; missing folders can be created.
  - Network share: step-by-step commands to mount an SMB share (also after restarts via `/etc/fstab`) with copy buttons.
  - Nothing is saved until Finish; the previous settings are kept as a restore point.
  - **“Skip – set up disks later”** in the disks step: the wizard can be finished without a disk (on a new installation the example paths are removed; when the wizard is run again, the current disks stay). The download page and the File manager then show where to add a disk, and Settings can be saved without disks.
  - `setup.sh` on a new installation no longer lists the example folders as missing – it says that disks are set in the wizard.
  - TMDB step: “Show key” now shows the saved key, and the button switches between “Skip” and “Next” as you type (fixed after the first tests).
- README (EN/PL): new section "Library on another computer (network share)" with the mount commands.

## 1.2.9-beta – 2026-11-09 (BETA)

- Everything from 1.2.7 (stable), plus the BETA-only VPN preview.
- **`fix.sh` in a window like `raspi-config`** (whiptail, arrow keys + Enter) with the same numbers as before; plain text menu on small screens or with `./fix.sh --text`.
- **New `fix.sh` option 6 – Server:** check status (service, autostart, panel address, last log lines), stop the server without changing autostart / start it again without restarting the Pi, restart the server process. Uninstall and Cancel moved to 7 and 8.

## 1.2.7 – 2026-11-09 (stable)

- **Better title recognition from pasted links:**
  - file names sent by the server with encoded characters (e.g. `%20` instead of spaces) are decoded,
  - a website address at the start of the name (`SITE.COM - Title…`) is removed,
  - a resolution in brackets such as `(720)` and subtitle notes such as `Subtitles English` are treated like other quality tags,
  - "Episode 2", "Ep 02", "Odcinek 2" (optionally with "Season 1" / "Sezon 1") are recognised as a TV episode; a title with a year after the episode number stays a movie (e.g. *Star Wars Episode 1 … 1999*).
  - a link that redirects to a web page (login, age check, expired link) is reported as "opens a web page, not a video file", and the name is taken from the original link instead of the redirect address.

## 1.2.8-beta – 2026-11-08 (BETA)

- Everything from 1.2.6 (stable).
- Keeps the BETA-only VPN preview (header badge and Settings tab) as the base for version 1.4.

## 1.2.6 – 2026-11-08 (stable)

- **File manager:** moving to another disk shows two stages with the real file size – "copying X of Y", then "verifying X of Y" – and one time-left estimate for both. Before, the counter showed double the size (copy + verification bytes added together).
- **File manager:** new option "Skip SHA-256 verification after moving" in the move confirmation (only for moves to another disk, off by default). About twice as fast; file sizes are still compared before the original is deleted. Marked "without verification" in the summary and in the activity log.
- **Settings → Preview & posters:** the TMDB key field is masked like a password, with a "Show key" checkbox. The panel no longer sends the key to the browser until you ask for it; saving without touching the field keeps the stored key.
- **Phones:** category buttons on the download page wrap instead of widening the page.
- **Settings:** the ⓘ icon after the intro text stays on the same line.
- **Terminal commands:** when the Pi's IP address is unknown, the `ssh` command shows `<raspberry-pi-ip>` instead of an example address.
- **Translations:** unused Polish strings removed; a new test checks that every string in the code has a Polish translation.
- **Documentation:** README in English (Polish version in `README.pl.md`), this changelog, roadmap in English and Polish.

## 1.2.6-beta – 2026-11-02 (BETA)

- Same features as 1.2.2 with the VPN preview; first version on the BETA channel.

## 1.2.5 – 2026-11-02 (stable)

- Stable and BETA release channels: `setup.sh` and `update.sh` use stable only, the update check announces stable versions only, BETA is installed and left with `fix.sh`.
- New `fix.sh` menu: update, reinstall, clean reinstall, install/update BETA, leave BETA, uninstall.
- VPN preview removed from the stable version until remote access works.

## 1.2.2 – 2026-11-02

- Settings backups: select and delete restore points (the newest one cannot be deleted), factory-reset note linking to `fix.sh`.
- Terminal commands collapsed by default.
- Tooltips stay inside the Settings window.

## 1.2.1 – 2026-11-02

- English (default) and Polish interface, dark and light themes; language choice at first login and in `setup.sh`.
- Activity log with viewer, clear and export, 1 MB limit with rotation.
- Move a whole TV show, a season or selected episodes; extras icon; speed, time left and move summary.
- "Update paths" scans disks for category folders; category type "Other (keep name)"; per-category TMDB switch.
- Posters always saved as `.jpg`; extras not counted as videos; folder dates preserved.
- Terminal commands with copy buttons; `fix.sh` repair menu.

## 1.2.0 – 2026-11-02

- File manager with two columns, posters, drag and drop and verified moves between disks.
- Categories (Kids and custom), advanced Plex naming (editions, versions, TMDB ID).
- Plex server status in the header, settings backups, floating Settings window, Google and YouTube buttons.

## 1.1.0 – 2026-11-01

- Movie and TV preview card from TMDB (poster, rating, cast, links to IMDb and Filmweb).

## 1.0.0 – 2026-11-01

- Downloads from direct links with aria2c (6 connections), Plex naming, three disks, resume after restart, login, systemd service.
