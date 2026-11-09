# Changelog

All notable changes to Plex Downloader. Stable versions live on the `main` branch, BETA versions on the `beta` branch (installed only with `fix.sh`).

## 1.3.0-beta2 – 2026-11-09 (BETA)

- **Settings export and import** (Settings → Backups → Export and import):
  - **Export settings** downloads a JSON file with disks, categories, Plex servers, download options, preview options, language and theme. The username, password and session keys are never included; the TMDB key only when “include the TMDB key” is ticked.
  - **Import settings…** checks the file and first shows what would change, section by section (disks with a check whether their folders exist on this device, categories, Plex servers, download options, preview & posters, interface). Only the ticked sections are applied; a restore point is created first, so the import can be undone.
  - Invalid values in the file (relative paths, unknown options, numbers out of range, unsafe host names) are ignored or limited.
- **“+ SD card (not recommended)”** in Settings → Disks: adds a disk with the mount point `/` and folders in the home folder (`~/Plex/Movies`…) for every category, and offers to create missing folders. ⓘ explains why the SD card is not recommended.
- After the first tests:
  - **“Create” next to an empty category folder** in Settings → Disks: a small yellow button opens a helper with the proposed path (next to the other folders of that disk, e.g. `/plex_media/Plex/Red`); the folder name can be changed (e.g. `reddot`), the folder is created and linked to the category – then Save.
  - Import: disks from another device (none of them mounted here) are unticked by default.
  - **Update paths** fixes paths copied from another device: `/plex_media_1024/Plex 1T/Home Video` (path on the Plex Pi) becomes `/mnt/plex_1024/Plex 1T/Home Video` when that folder exists under this mount point. Folder names a category uses on other disks (e.g. `Home Video`, `reddot`) are also searched for.
  - **Setup wizard – categories on the disk step:**
    - when a disk has no category folders yet, the folders are suggested inside its `Plex` folder (e.g. `/mnt/disk/Plex/Movies`, `…/TV Shows`) and marked “will be created”,
    - gear next to a category: rename it and change its folder and type (e.g. Kids → Concerts); folders that do not exist yet get the new name,
    - ✕: the category is not used on this disk (↺ brings it back with a suggested folder); “+ Add category” adds a new one,
    - every such change ticks and highlights “Create missing folders when finishing”; when folders are missing and the box is unticked, it is highlighted too,
    - two categories with the same name or the same folder on one disk are reported before continuing.

## 1.3.0-beta1 – 2026-11-09 (BETA)

- **Disk tiles (download page and File manager):** drag a tile to change the order of the disks (also with the gear: move left / right, handy on phones); the order is the same on both pages and in Settings. The gear in the top-left corner of a tile also renames the disk (max. 16 characters). Tiles are laid out in rows of three.
- **Edition: up to 3 tags.** “+ Add another tag” adds a second and third edition field (suggestions without the tags already chosen). Plex allows one edition per movie, so the tags are joined into one name, e.g. `{edition-Remastered Blu-ray}` (max. 32 characters, counter shown).
- The setup wizard no longer asks for disk button names – it uses short default names (the share name or the folder name) that can be changed later with the gear or in Settings → Disks.
- **Setup wizard:** shown after the first login of a new installation (existing installations are not affected) and available again in Settings → Account → Run setup wizard. Steps: language, theme, where the library is stored, disks and folders, Plex server, TMDB key, summary.
  - Three installation types: external disks (recommended), library on the SD card (not recommended, folders in the home folder) and Plex on another device (network share).
  - Mounted disks and network shares are detected; category folders are found automatically; every folder is checked for write permission and free space; missing folders can be created.
  - Network share: step-by-step commands to mount an SMB share (also after restarts via `/etc/fstab`) with copy buttons.
  - Nothing is saved until Finish; the previous settings are kept as a restore point.
  - **“Skip – set up disks later”** in the disks step: the wizard can be finished without a disk (on a new installation the example paths are removed; when the wizard is run again, the current disks stay). The download page and the File manager then show where to add a disk, and Settings can be saved without disks.
  - `setup.sh` on a new installation no longer lists the example folders as missing – it says that disks are set in the wizard.
  - After the first tests: ⓘ explaining “Create missing folders when finishing”; a note (with ⓘ) that downloads are slower when the library is on another device; network shares get the share name as the button name; missing folders are suggested next to the ones found (e.g. `Plex 1T/Kids`); note that category and folder names can be changed in Settings → Categories.
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
