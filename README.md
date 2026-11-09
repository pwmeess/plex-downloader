# Plex Downloader

🇬🇧 **English** · 🇵🇱 [Polski](README.pl.md)

A lightweight download manager for the Raspberry Pi. Paste a direct link to a video file, choose a disk, and the app downloads it with multiple connections (aria2c) into a folder structure that Plex recognises straight away.

- **Movies:** `…/Movies/Title (YYYY)/Title (YYYY).mkv`
- **TV shows:** `…/TV Shows/Show/Season 01/Show - S01E02.mkv`
- **Kids and custom categories:** `…/Kids/Title (YYYY)/…`, `…/Concerts/…` and so on

Changelog: [CHANGELOG.md](CHANGELOG.md) · Roadmap: [ROADMAP.md](ROADMAP.md)

## Features

- Login with username and password, "remember me" for 30 days, log out.
- Title, year, season and episode recognised from the file name in the link (editable).
- File extension taken from the link or from the HTTP headers.
- Disk picker with free space. A disk that is not mounted is blocked, so a download cannot fill the SD card.
- Checks before starting that the file fits on the disk.
- Segmented downloads, 6 connections per file by default (`aria2c -x6 -s6 -k1M`).
- Progress, speed, time left, number of connections and states: Queued, Downloading, Paused, Finalizing, Done, Error.
- Pause and resume. aria2 resumes broken transfers by itself (HTTP Range).
- Interrupted downloads resume automatically after a reboot or a service restart.
- Atomic: a file is downloaded into the hidden `.plexdl-tmp` folder on the same disk, next to `Movies` (outside the Plex library), and moved into the library with a single `rename` when it is complete. Cancelling or an error removes the temporary files and no target folder is created.
- **Movie and TV preview (TMDB):** after pasting a link you get a card with the title, poster, rating, runtime, genres, director, cast and plot, plus links to IMDb, Filmweb, TMDB, Google and the YouTube trailer. Nothing from it is written to the files – Plex fetches its own metadata.
- **Categories:** Movies, TV Shows, Kids and any custom category of type movie, TV show or "other (keep name)". Each disk has its own folder for each category; folder names are up to you.
- **Advanced Plex naming:** edition `{edition-Director's Cut}` (Plex Pass), file version `- 1080p` (several versions in one folder) and `{tmdb-…}` ID for exact matching.
- **File manager:** two columns with posters. Drag and drop movies between folders and disks. Same disk = instant move; another disk = copy → SHA-256 verification → only then the original is removed. Move a whole TV show, one season or selected episodes.
- **Two-stage progress (1.2.6):** "copying X of Y" and "verifying X of Y" with the real file size, and one time-left estimate for both stages.
- **"Skip SHA-256 verification after moving" (1.2.6):** option in the move confirmation (off by default). About twice as fast; only file sizes are compared before the original is deleted.
- **Posters:** saved in the movie folder as `Title (Year).thumb.jpg` (from TMDB). TMDB lookups can be switched off per category (e.g. home videos).
- **Plex servers in the header:** automatic discovery on the network (GDM) and online/offline status, also for servers added manually.
- **Settings backups:** a restore point after every change, kept for 30 days (the latest is always kept). Restoring never changes the username or password.
- **Settings export and import (1.3.0-beta2):** a JSON file without the username, password and keys (TMDB key optional); on import you see what changes and choose the sections to apply.
- **Languages and themes:** English (default) and Polish, dark or light theme (Settings → Account). Translations live in `locales/<code>.json`, so a new language is a new file.
- **Activity log:** `logs/plexdl.log` with downloads, moves (from → to) and deletions; **LOG** viewer in Settings → Account with Clear and Export. 1 MB limit, then `bcup01.log`, `bcup02.log`…
- **Hidden TMDB key (1.2.6):** the key field is masked like a password, with "Show key" on demand; the panel does not send the key to the browser until you ask for it.
- **Terminal commands** with a copy button in Settings → Account.
- **Setup wizard (1.3.0-beta1):** first-run guide for disks and folders, Plex server and TMDB key; can be run again from Settings.
- Works on phones.

## Requirements

- Raspberry Pi OS (32- or 64-bit), Python 3.7 or newer.
- Disks mounted permanently (`/etc/fstab`) and writable for the user running the service (usually `pi`).

## Installation

```bash
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd plex-downloader
chmod +x setup.sh update.sh fix.sh
./setup.sh
```

The script:

1. asks for the language (1 – English, default; 2 – Polski),
2. installs `aria2`, `python3-venv` and `git`,
3. creates the `venv/` environment and installs `requirements.txt`,
4. creates `config.json` and asks for a username and password,
5. checks that the library folders exist and are writable,
6. registers and starts the `plex-downloader` service (starts automatically after a reboot).

At the end it prints the address, e.g. **http://192.168.1.10:8800**. `setup.sh` always installs the latest **stable** version.

**Setup wizard (1.3, BETA):** after the first login a wizard guides you through language, theme, where the library is stored (external disks – recommended, SD card – not recommended, or Plex on another device), disks and folders (found automatically, missing ones created), the Plex server and the TMDB key. You can run it again from **Settings → Account → Run setup wizard**.

## Updating

```bash
cd ~/plex-downloader
./update.sh
```

The header of the Settings window shows whether a newer stable version is available.

## Stable and BETA versions

- **Stable** (branch `main`): installed by `setup.sh` and updated by `update.sh`. The panel only announces stable versions.
- **BETA** (branch `beta`): new, less tested features (for example the VPN preview). Installed and updated only with `fix.sh` (option 4). Before the first switch to BETA, `fix.sh` saves your settings; leaving BETA (option 5) returns to stable, removes the experimental settings and restores the saved ones.

## Repair menu: `fix.sh`

```bash
cd ~/plex-downloader
./fix.sh
```

The menu opens in a window like `raspi-config` (arrow keys + Enter). On a very small screen, or with `./fix.sh --text`, it is shown as plain text with the same numbers. It asks for the language first, then shows:

1. **Update (check and install)** – checks GitHub and installs a new stable version,
2. **Reinstall (keep settings)** – fetches the code again and rebuilds the environment, settings stay,
3. **Clean reinstall** – deletes settings, backups, logs and the download list, then installs the stable version from scratch (confirm with YES),
4. **Install / update the latest BETA**,
5. **Leave BETA** – back to stable, experimental settings removed (no extra questions),
6. **Server** – check status (service, autostart, panel address, last log lines), stop the server (autostart stays on) or start it again without restarting the Pi, restart the server process,
7. **Uninstall** – removes the service from autostart, optionally also the app folder,
8. **Cancel**.

Movies and TV shows on the disks are never touched.

## Movie preview: TMDB key

1. Create a free account at https://www.themoviedb.org/signup.
2. Go to **Settings → API → Create → Developer**. "Personal use" is enough in the form.
3. Copy the **API Key** or the **API Read Access Token** – either works.
4. In Plex Downloader open **Settings → Preview & posters**, paste the key and click **Save**.

The key is stored only locally in `config.json`. Without a key the app works normally, just without the preview card.

## Your own disks

The default paths in `config.example.json` are the author's layout, so yours will most likely differ.

1. Check where your disks are mounted with `df -h`, e.g. `/mnt/disk1`.
2. In **Settings → Disks** enter for each disk:
   - **Button name**, e.g. "SSD 1TB",
   - **Subtitle**, e.g. the SMB share name (optional),
   - **Mount point**, e.g. `/mnt/disk1` (used to read free space),
   - **Folder** for each category – the Plex library paths, e.g. `/mnt/disk1/Movies`.
3. **Update paths** scans the disk and fills in folders that match the categories (e.g. `Movies`/`Filmy`, `Kids`/`Dla dzieci`). Found paths are marked green, missing ones red, and you can edit any of them. Click **Save**.
4. Add custom categories in the **Categories** tab: button name, type, default folder name and TMDB switch. Add a separate Plex library for each one.

Removing a disk from the list never deletes files – it only hides the button.

**Library on the SD card (not recommended, e.g. for testing):** use the mount point `/` and folders in your home directory, e.g. `/home/pi/Plex/Movies`. In BETA (1.3.0-beta2) the **+ SD card (not recommended)** button in Settings → Disks fills this in and can create the folders. Keep in mind the limited capacity, wear and speed of SD cards.

## Library on another computer (network share)

Plex can run on another computer (for example a second Raspberry Pi) while Plex Downloader runs here. Both must see the same files, so the library folder of the Plex computer is shared over SMB and mounted on this Raspberry Pi. Give both devices a fixed IP address in your router.

Run these commands on the Raspberry Pi with Plex Downloader (replace `192.168.1.10`, `SHARE`, `USER` and `PASSWORD`; `pi` is the user that runs the service):

```bash
sudo apt install -y cifs-utils                    # tools for SMB shares
sudo mkdir -p /mnt/plex                           # folder for the share
# save the share password in a file only you can read
printf 'username=USER\npassword=PASSWORD\n' > ~/.smbcredentials && chmod 600 ~/.smbcredentials
# mount now (test)
sudo mount -t cifs //192.168.1.10/SHARE /mnt/plex -o credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8
```

To mount the share automatically after every restart, add this line to `/etc/fstab` (`sudo nano /etc/fstab`):

```
//192.168.1.10/SHARE /mnt/plex cifs credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,_netdev,nofail 0 0
```

Then run `sudo mount -a` – if it shows no error, the share will be mounted after a restart too. In the setup wizard choose **Plex on another device** (the share appears in the list) or enter `/mnt/plex` as the mount point in **Settings → Disks**. The same commands are shown in the wizard with copy buttons.

## Useful commands

```bash
journalctl -u plex-downloader -f               # live logs
sudo systemctl restart plex-downloader         # restart
./venv/bin/python app.py --set-password        # reset username / password (then restart)
./venv/bin/python app.py --set-language en     # interface language (en, pl)
./fix.sh                                       # repair menu
```

## Files

| File | Role |
|---|---|
| `app.py` | web server (Flask + waitress), login, API |
| `downloader.py` | aria2c control over JSON-RPC, queue, finalizing, cleanup |
| `filemanager.py` | File manager: listing, verified moves, deleting, posters |
| `plexservers.py` | Plex server discovery and status |
| `movieinfo.py` | movie / TV preview from TMDB (display only) |
| `naming.py` | title, year and episode recognition; Plex naming |
| `i18n.py`, `locales/` | translations (en, pl) |
| `actlog.py` | activity log (`logs/`) |
| `config.py` | `config.json`, migration, restore points (`backups/`) |
| `templates/`, `static/` | user interface |
| `setup.sh`, `update.sh`, `fix.sh` | install, update, repair menu |

`config.json` (password, keys), `backups/`, `logs/` and `plexdl.db` (download list) are never committed (`.gitignore`).

## Security

The app is meant for a home network. Do not expose port 8800 to the internet. For remote access use a VPN such as Tailscale or WireGuard.
