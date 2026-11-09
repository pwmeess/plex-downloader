# Changelog

All notable changes to Plex Downloader. Stable versions live on the `main` branch, BETA versions on the `beta` branch (installed only with `fix.sh`).

## 1.2.9-beta – 2026-11-09 (BETA)

- Everything from 1.2.7 (stable), plus the BETA-only VPN preview.

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
