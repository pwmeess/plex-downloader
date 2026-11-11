# Plex Downloader – guide {#top}

This guide takes you step by step from a clean Raspberry Pi to a working Plex library with a download manager. Replace the example addresses and names (`192.168.1.10`, `pi`, `SSD 1TB`) with your own.

## 1. How it works {#intro}

**Plex Media Server** plays movies and TV shows on your TV, phone and computer. **Plex Downloader** is a panel in the browser that:

- downloads files from direct links (several connections at once, resumes after a restart),
- names them straight away the way Plex expects (`Title (Year)/Title (Year).mkv`, `Show/Season 01/Show - S01E02.mkv`),
- has a **File manager**: moves between disks with SHA-256 verification, renames, changes posters, deletes.

### Three ways to set it up {#scenarios}

| Setup | For whom | Notes |
|---|---|---|
| **External disks** (recommended) | Plex and Downloader on one Raspberry Pi, library on an SSD/HDD or USB stick | fastest and simplest |
| **SD card** (not recommended) | a quick test without disks | the card is small, slow and wears out with large writes |
| **Two devices** | Plex on one computer, Downloader on another (e.g. a Pi Zero 2 W) | library shared over SMB; downloads are slower |

**You need:** a Raspberry Pi with Raspberry Pi OS (32 or 64-bit), SSH access and an internet connection. Use the official power supply – a weak power supply is the most common reason for a Pi that freezes.

## 2. Installing Plex Media Server {#plex}

If Plex is already running, go to [chapter 3](#downloader).

### The easy way: fix.sh {#plex-fix}

After installing Plex Downloader (chapter 3) run `./fix.sh` → **7 Additional modules** → **Plex Media Server** → **Install**. The script adds the official Plex repository and installs the server. At the end it shows `http://<pi-address>:32400/web` – open it in the browser and sign in with your Plex account.

### By hand {#plex-manual}

```bash
sudo apt install -y curl gnupg
curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | sudo gpg --dearmor -o /usr/share/keyrings/plex.gpg
echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://downloads.plex.tv/repo/deb public main" | sudo tee /etc/apt/sources.list.d/plexmediaserver.list
sudo apt update && sudo apt install -y plexmediaserver
```

### External disk: permanent mount {#plex-disks}

The disk has to be **mounted permanently** (also after a restart), otherwise Plex and Downloader will not find the library.

1. Find the disk name and UUID:
   ```bash
   lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT
   ```
2. Create a mount point, e.g. `/mnt/ssd1`:
   ```bash
   sudo mkdir -p /mnt/ssd1
   ```
3. Add a line to `/etc/fstab` (`sudo nano /etc/fstab`) with the UUID from step 1:
   ```
   UUID=1234-ABCD  /mnt/ssd1  ext4  defaults,nofail  0  2
   ```
   For a disk formatted as exFAT or NTFS write `exfat` or `ntfs3` instead of `ext4` and add `uid=pi,gid=pi`, e.g. `defaults,nofail,uid=pi,gid=pi`.
4. Mount it and check – no error means it will also be mounted after a restart:
   ```bash
   sudo mount -a && df -h /mnt/ssd1
   ```
5. Create the library folders (or let the wizard do it – chapter 3):
   ```bash
   mkdir -p "/mnt/ssd1/Plex/Movies" "/mnt/ssd1/Plex/TV Shows" "/mnt/ssd1/Plex/Kids"
   ```

**Permissions:** Plex runs as the user `plex`, Plex Downloader as you (e.g. `pi`). Plex must be able to read the folders, Downloader to write:

```bash
sudo chown -R pi:pi /mnt/ssd1/Plex
sudo chmod -R 755 /mnt/ssd1/Plex
```

In the Plex app add the libraries: **Movies** → `/mnt/ssd1/Plex/Movies`, **TV Shows** → `/mnt/ssd1/Plex/TV Shows` and so on.

### Test setup: library on the SD card {#plex-sd}

**Not recommended for everyday use.** The SD card is small, slower than a disk and wears out faster. If it fills up completely, the whole system may stop working – always keep a few GB free.

The library then lives in your home folder, e.g. `/home/pi/Plex/Movies`. The Plex Downloader wizard has a ready option **“Library on the SD card”**, and Settings → Disks has a **“+ SD card (not recommended)”** button. To copy files from your computer, share the `Plex` folder over SMB ([chapter 4](#samba)).

## 3. Installing Plex Downloader {#downloader}

Log in to the Raspberry Pi over SSH (e.g. `ssh pi@192.168.1.10`, details in [chapter 7](#ssh)) and run:

```bash
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd plex-downloader
chmod +x setup.sh update.sh fix.sh
./setup.sh
```

The script:

1. asks for the language (1 – English, 2 – Polski),
2. installs the system packages (aria2, Python, git) and ffmpeg – **on a Pi Zero this can take 5–15 minutes**,
3. creates the Python environment; on weak Wi-Fi `Retrying…` warnings are normal – if the download fails, run `./setup.sh` again, nothing is lost,
4. asks for a **username and password** for the panel (min. 6 characters),
5. starts the service and shows the panel address, e.g. **http://192.168.1.10:8800**.

> **The port is 8800**, not 8080.

### Setup wizard {#wizard}

The wizard opens after the first login. Run it again any time with **Settings → Account → Run setup wizard** – it then starts from scratch (only the categories and the saved TMDB key are kept). **Close without saving** leaves the current settings unchanged.

1. **Language and theme.** The first step also has **“I have a settings file – load it”** – handy for a second Raspberry Pi or after a reinstall ([chapter 5](#backup)). Without a file the wizard guides you through everything.
2. **Where the library is:** external disks, SD card or Plex on another device.
3. <a id="wizard-disks"></a>**Disks and folders**
   - The wizard checks the mounted disks (or network shares) and **ticks** the ones with library folders by itself. It reads only folder names – never their contents.
   - It recognises common names and variants: `Movies`, `Filmy`, `Cinema`, `TV Shows`, `Series`, `Kids`, `Home Video` = `Home Videos`… Music and photo folders are skipped.
   - Next to each category: **⚙** renames the category (e.g. “Kids” → “Concerts”), **✕** means “not on this disk”, **↺** brings it back with a suggested folder, **+ Add category** creates a new one.
   - Unusual folders next to the library (e.g. `Movies02`) are shown as **“+ Movies02”** buttons – a click adds them as a new category.
   - **Create missing folders when finishing** is off by default. Folders that do not exist and will not be created are left out.
   - **Next** only needs a Movies or TV Shows folder on any disk. **Skip – set up disks later** is for when there is no library yet.
4. **Plex server.** Servers in your home network are found automatically. Add a server by hand only when it is on another subnet or behind a VPN.
5. <a id="tmdb"></a>**TMDB key** (optional, free): create an account at themoviedb.org → Settings → API → create a key (“Personal use” is enough) and paste the **API Key** or the **API Read Access Token**. The wizard checks it right away: **✓ Key OK** / **✗ Invalid key**. With a key you get the movie preview card and posters in the File manager.
   - **Generate posters myself from video frames (needs ffmpeg)** – for home videos and titles TMDB does not know. Not recommended right away: about 10–15 s per movie on a Pi 4 / Pi 400, longer on a Pi Zero. A poster from a frame for a single movie can always be made in the Edit window ([chapter 5](#edit)).
6. **Summary → Finish.** The previous settings are kept as a restore point.

## 4. Two devices: Plex on one, Downloader on another {#two-devices}

Example: the **Plex Pi** (`192.168.1.10`) has the disks, the **Downloader Pi** (`192.168.1.20`, e.g. a Pi Zero 2 W) writes to them over the network.

1. **Fixed IP addresses.** Reserve fixed addresses for both devices in your router (DHCP reservation).
2. **Share the library on the Plex Pi** (Samba).
3. **Mount the share on the Downloader Pi** (cifs, permanently in fstab).
4. Run the wizard and choose **“Plex on another device”**.

> Downloads are slower in this setup: every byte travels over the network twice. Over 2.4 GHz Wi-Fi (Pi Zero 2 W) expect a few MB/s.

### Sharing folders (Samba) – on the Plex Pi {#samba}

`./fix.sh` → **7 Additional modules** → **Samba** → **Install**, or `sudo apt install -y samba`. Then add a share at the end of `/etc/samba/smb.conf` (`sudo nano /etc/samba/smb.conf`):

```
[Plex SSD1]
   path = /mnt/ssd1/Plex
   valid users = pi
   read only = no
   force user = pi
```

Set the Samba password for the user and restart the service:

```bash
sudo smbpasswd -a pi
sudo systemctl restart smbd
```

`valid users` lets only this user in – never share the library with everyone.

### Mounting the share – on the Downloader Pi {#cifs}

```bash
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/ssd1
nano ~/.smbcredentials
```

Put two lines into `~/.smbcredentials` and save (Ctrl+O, Enter, Ctrl+X):

```
username=pi
password=YOUR_SAMBA_PASSWORD
```

```bash
chmod 600 ~/.smbcredentials
sudo mount -t cifs "//192.168.1.10/Plex SSD1" /mnt/ssd1 -o credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0
```

> **Password with a `\`:** type it in `nano`, not with `echo` or `printf` – they change the backslash and mounting fails with `mount error(13): Permission denied`.

Permanently – add to `/etc/fstab` (a space in the share name is `\040`):

```
//192.168.1.10/Plex\040SSD1  /mnt/ssd1  cifs  credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0,_netdev,nofail  0  0
```

Check: `sudo mount -a && df -h /mnt/ssd1`. The wizard lists the share under “Network shares mounted on this Raspberry Pi”.

### One disk, two different paths {#paths}

Each device sees the shared disk under its own path:

| | Plex Pi | Downloader Pi |
|---|---|---|
| Mount point | `/mnt/ssd1` | `/mnt/ssd1` or e.g. `/mnt/plex_ssd` |
| “Concerts” folder | `/mnt/ssd1/Plex/Concerts` | `/mnt/plex_ssd/Concerts` |

In Plex Downloader always enter the paths **of the device the panel runs on**. A path copied from the other Pi shows “Folder does not exist” – **Settings → Disks → Update paths** then moves it onto the right mount point (the same after importing settings from another device). Nothing changes in Plex.

### One category, different folder names {#folder-names}

A category is just a button in the panel – every disk has its own folder for it. E.g. the **Concerts** category: `Concerts` on one disk, `Live` on another. Enter the right path for each disk (or click the yellow **Create** next to an empty field), and in Plex add **both folders to the same library** (library → Edit → Add folders).

## 5. Everyday use {#usage}

### Downloading {#download}

Paste a direct link to a video file. The panel recognises the title, year, season and episode (you can correct everything), shows the TMDB card and the free space on the disk. Choose the disk and category and click **Download**. The file goes to a hidden temporary folder first and into the library in one move only when it is complete.

Advanced options: **edition** (`{edition-Director's Cut}`, up to 3 tags, needs Plex Pass), **file version** (` - 1080p`, several versions in one folder) and **TMDB ID** (`{tmdb-19995}`, exact match in Plex).

### File manager {#files}

Two columns with posters. **Drag** a movie from one column to the other:

- same disk – instant move,
- another disk – copy → SHA-256 verification → only then the original is removed (**Skip SHA-256 verification** makes it about twice as fast and compares only the sizes).

TV shows can be moved whole, by season or by selected episodes. Change the order of the disks by dragging the tiles; the gear on a tile renames the disk.

### Edit name and poster {#edit}

The **pen** icon on a card (above the trash) opens the Edit window:

- **title, year, TMDB ID** (**Find in TMDB** button), **edition** and **files in the folder**,
- every file has a **type**: *Movie (version)* or a Plex extra – *Trailer, Behind the scenes, Deleted scene, Interview, Other extra*. An extra gets the name `Description-trailer.mp4` and Plex shows it under Extras, not as another version of the movie,
- file names change only after a field was edited – changing just the poster never renames anything,
- **Change** lists all changes and asks “Are you sure?”.

**Poster:** *Own image…* (JPG, PNG, WebP), *Frame from the video* (6 frames to choose from; **Generate others** picks new ones; **Pick a time** shows frames around a time `h:mm:ss`, **+10 s** moves 10 seconds on) or *download the poster from TMDB*. Posters chosen by hand are kept when posters are refreshed.

### Settings backups, export and import {#backup}

- Every change of the settings creates a **restore point** (Settings → Backups), kept for 30 days.
- **Export settings** saves a JSON file (disks, categories, servers, options) – without the username, password and session keys; the TMDB key only on request.
- **Import settings…** shows what will change and lets you choose the sections. Disks from another device are unticked by default.

### Activity log {#log}

Settings → Account → **LOG**: downloads, moves, deletions, renames. Clear and Export buttons.

## 6. Updating, repairing and diagnostics {#maintenance}

### Updating {#update}

```bash
cd ~/plex-downloader && ./update.sh
```

The header of the Settings window shows when a newer stable version is available.

### Repair menu fix.sh {#fix}

```bash
cd ~/plex-downloader && ./fix.sh
```

1. **Update** – installs a new stable version,
2. **Reinstall** – rebuilds the environment, settings stay,
3. **Clean reinstall** – factory settings (confirm with YES),
4. **Install / update BETA**,
5. **Leave BETA**,
6. **Server** – status, stop / start, restart,
7. **Additional modules** – Plex Media Server, Samba, SMB client, ffmpeg, Tailscale VPN (recommended), WireGuard VPN: status, install, update, stop until the next restart, restart, uninstall,
8. **Uninstall**,
9. **Cancel**.

Your movies and TV shows are never touched.

### Raspberry Pi diagnostics {#diagnostics}

```bash
uptime                          # how long it has been running without a restart
vcgencmd get_throttled          # 0x0 = power supply and temperature OK
vcgencmd measure_temp           # temperature (trouble from about 80 °C)
free -h                         # memory
df -h                           # space on the card and disks
journalctl -u plex-downloader -n 50 --no-pager     # Plex Downloader log
dmesg -T | grep -iE "voltage|mmc|i/o error|cifs" | tail
```

To keep the log after a restart (useful when the Pi freezes):

```bash
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald
```

Then `journalctl -b -1` shows the entries from before the last restart. A `get_throttled` result other than `0x0` usually means the power supply is too weak.

## 7. Easier SSH login (keys) {#ssh}

On your computer (macOS, Linux, Windows 10/11 – Terminal or PowerShell):

```bash
ssh-keygen -t ed25519            # Enter, Enter (key passphrase optional)
ssh-copy-id pi@192.168.1.10      # you type the Pi password once
ssh-copy-id pi@192.168.1.20
```

On Windows instead of `ssh-copy-id`:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@192.168.1.10 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Shortcuts – the file `~/.ssh/config` on your computer:

```
Host plex
    HostName 192.168.1.10
    User pi
Host zero
    HostName 192.168.1.20
    User pi
```

From now on `ssh plex` or `ssh zero` is enough. Stop a command with **Ctrl+C**, end the session with `exit`.

## 8. Security in your home network {#security}

- **Do not forward port 8800** (or 32400 without a reason) on your router and do not put the Raspberry Pi in a DMZ – the panel is meant for your home network.
- For access from outside use a **VPN**: `./fix.sh` → 7 → **Tailscale** (recommended, no open ports) or WireGuard.
- Use **strong passwords**: for the panel, for your Raspberry Pi account and for Samba. Better still, log in with SSH keys ([chapter 7](#ssh)).
- In Samba use `valid users` – never share folders with guests.
- Keep the system up to date: `sudo apt update && sudo apt full-upgrade`, and Plex Downloader with `./update.sh`.
- The TMDB key and passwords are stored only locally (`config.json`, `~/.smbcredentials`) – never send these files to anyone.
