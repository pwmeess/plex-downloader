# Home movie and TV server — step-by-step guide {#top}

A complete guide from a blank SD card and a new drive straight from the shop to a finished Plex library with a convenient download panel in your browser. {.lead}

**Contents — in the order you do things** {.toc-title}

| Stage | What you do |
|---|---|
| Intro | How it works, three ways to install, requirements and 4 rules for the terminal |
| Stage 0 | Preparing the SD card (Raspberry Pi Imager) and first start |
| Stage 1 | Connecting to the Raspberry Pi (SSH) and logging in without a password |
| Stage 2 | Preparing the drive for your library (new from the shop, with data from Windows/Mac, permanent mounting) |
| Stage 3 | Installing Plex Downloader, Plex Media Server and the setup wizard |
| Stage 4 | Two devices (Plex on one Pi, Downloader on another) |
| Stage 5 | Everyday use of the panel (downloads, where to watch, File manager, editing and posters) |
| Stage 6 | Access from your phone and computer away from home (Tailscale VPN) |
| Stage 7 | Updates, diagnostics, the fix.sh repair tool and security |
| Extras | When something does not work (FAQ) and a glossary |

## Intro: how it works and what you need {#intro data-stage="INTRO"}

The setup consists of two programs that work together on a Raspberry Pi:

- **Plex Media Server** — your home entertainment centre. It catalogues movies and TV shows, fetches descriptions and posters, and plays video on your TV, phone and computer.
- **Plex Downloader** — a panel you open in an ordinary web browser. It downloads video files from direct links (several connections at once, resumes after a restart), names them the way Plex expects (e.g. `Title (Year)/Title (Year).mkv` or `Show/Season 01/Show S01E02.mkv`) and lets you manage files and posters.

### Three ways to install {#scenarios}

| Installation | For whom | What to expect |
|---|---|---|
| **1. External drives** (recommended) | Plex and Downloader on one Raspberry Pi, movies on an SSD/HDD or USB stick | The fastest, simplest and most reliable option. |
| **2. SD card** (not recommended) | A quick test without a drive | The card is small, slow and wears out quickly when writing large files. |
| **3. Two devices** | Plex on a stronger Pi, Downloader on a separate one (e.g. Pi Zero 2 W) | The library is shared over the network (SMB); downloads are slower because data crosses the network twice. |

You will see the same three options later in the setup wizard, in the **Installation** step.

**Requirements:** a Raspberry Pi (Pi 4 or Pi 5 recommended; a Pi Zero 2 W is enough for option 3), a microSD card of at least 16 GB, a connection to your router (preferably a cable) and **the official power supply**. A weak power supply or a phone charger is the most common reason why a Raspberry Pi freezes or fails to write to a USB drive.

> [!INFO] **Before you type your first command — 4 rules for the terminal**
>
> 1. **User name (`pi`):** throughout this guide we assume your Raspberry Pi account is called `pi`. If you chose another name when preparing the card (Stage 0), e.g. `john`, type it wherever the examples say `pi`.
> 2. **Invisible password:** when the terminal asks for a password (`password:`), you type it “blind” — no dots or asterisks appear. Type the password and press **Enter**.
> 3. **Pasting commands:** **Ctrl+V** does not work in some terminals. On a Mac use **Cmd+V**, on Windows **right-click** inside the terminal window (or Ctrl+V in the new Windows Terminal), on Linux **Ctrl+Shift+V**. Paste commands **as whole blocks** — every line is a separate command (a line ending with `\` continues on the next one). It is easiest to copy from the guide in the panel (**Settings → Account → Guide (HTML / PDF)**): every block there has a **Copy** button.
> 4. **Saving in the `nano` editor:** move around with the arrow keys. To save and exit: **Ctrl+O** (the letter O), **Enter**, then **Ctrl+X**.

## Preparing the SD card and first start {#sd-card data-stage="STAGE 0"}

A Raspberry Pi has no system drive — the system runs from a microSD card. You prepare the card on your own computer with the free **Raspberry Pi Imager**.

**Step 1:** download and install Raspberry Pi Imager from **raspberrypi.com/software** (Windows, macOS, Linux). Put the microSD card into your computer (card reader or adapter).

**Step 2:** in the program choose:

| Imager field | What to choose |
|---|---|
| Device | Your model, e.g. Raspberry Pi 4 |
| OS | **Raspberry Pi OS Lite (64-bit)** — the version without a desktop, the lightest one. For the oldest Pi Zero W (first generation) choose the **32-bit** version. |
| Storage | Your microSD card — check the capacity so you do not pick another drive! |

**Step 3: settings (the most important step).** When Imager asks whether to apply your own settings (*Customisation / Edit settings*), choose **yes** and fill in:

| Setting | What to enter | Why |
|---|---|---|
| Hostname | `raspberrypi` | The Pi can be found on the network under this name (`raspberrypi.local`). |
| User name and password | `pi` + your password | You will log in over SSH with these. Write them down! |
| Wi-Fi (optional) | network name, password, your country | Only if the Pi will not use a network cable. |
| Time zone and keyboard | your time zone and layout | Correct times in the logs. |
| Services → **SSH** | **Enable** (password authentication) | **Without this you cannot connect to the Pi in Stage 1.** |

**Step 4:** write the card (*Write*) and wait for the verification. Put the card into the Raspberry Pi, connect the network cable (if you use one) and the **power supply** last. The first start takes 2–3 minutes (the system expands to the whole card) — the green LED stops flickering heavily when it is done.

> [!TIP] **A fixed IP address.** In your router's admin page find the list of connected devices, look for `raspberrypi` and set a **DHCP reservation** for it (the option may be called *Address Reservation* or *Static DHCP*). The panel's address will then not change after a power cut. The examples use the address `192.168.1.10`.

## Connecting to the Raspberry Pi over SSH {#ssh data-stage="STAGE 1"}

Instead of connecting a monitor and keyboard to the Raspberry Pi, you control it remotely from your own computer through a secure text connection — **SSH**. All commands in this guide are typed in such a connection.

### 1.1. First login {#ssh-first}

Open **Terminal** on your computer (macOS: Cmd+Space → type “Terminal”; Linux) or **PowerShell** (Windows 10/11: Start menu → type “PowerShell”) and type:

```bash
ssh pi@raspberrypi.local
```

If your computer cannot find the name `raspberrypi.local`, use the IP address from the device list in your router:

```bash
ssh pi@192.168.1.10
```

The first time you will be asked `Are you sure you want to continue connecting (yes/no)?` — type the full word `yes` and press **Enter**. Then enter the password you set in Stage 0. When you see the prompt `pi@raspberrypi:~ $`, you are logged in. You can check the IP address at any time with `hostname -I`.

### 1.2. Logging in without a password (SSH keys) {#ssh-keys}

During setup you will connect to the Raspberry Pi many times. SSH keys let you log in with a short `ssh plex`, without the address or password. **Run the commands below on your own computer** (not on the Raspberry Pi — if you are logged in to the Pi, type `exit`).

**Step 1: create a key pair** (Windows, macOS, Linux):

```bash
ssh-keygen -t ed25519
```

Press **Enter** three times — this accepts the default file location and no extra passphrase. If it asks `Overwrite (y/n)?`, you already have a key — type `n` and go to step 2.

**Step 2A: send the key to the Raspberry Pi — macOS and Linux:**

```bash
ssh-copy-id pi@192.168.1.10
```

**Step 2B: send the key to the Raspberry Pi — Windows (PowerShell):**

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@192.168.1.10 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Either way you enter the Raspberry Pi password for the last time.

**Step 3: a short `ssh plex` (optional, very handy).** Open the SSH config file on your computer — macOS/Linux: `nano ~/.ssh/config`, Windows (PowerShell): `notepad $env:USERPROFILE\.ssh\config` (agree to create the file) — and type **three lines**:

```text
Host plex
    HostName 192.168.1.10
    User pi
```

Save the file. From now on `ssh plex` opens the Raspberry Pi console straight away.

## Preparing the drive for movies and TV shows {#disk data-stage="STAGE 2"}

Before installing Plex and Downloader, prepare the space for your files. On Linux a drive does not get a letter (like `D:` on Windows) — it is attached to a folder of your choice, e.g. `/mnt/ssd1`. That folder is called the **mount point**. Choose the scenario that matches your drive:

| Your drive | What you do |
|---|---|
| New from the shop (or you want to wipe it) and it will be connected **only to the Raspberry Pi** | Scenario A — format as `ext4` in the terminal (recommended) |
| New, but you want to plug it into a **computer** with Windows or Mac sometimes | Scenario C — format as `exFAT` on the computer |
| It already has **movies** from Windows (NTFS) or a Mac/USB stick (exFAT) | Scenario B — no formatting |

Then, in every scenario: **2.4 permanent mounting** and **2.5 library folders**.

### 2.1. Scenario A: a new drive only for the Raspberry Pi (ext4) {#new-disk}

New drives come formatted for Windows or Mac. If the drive will work only with the Raspberry Pi, the native Linux format — **ext4** — is best: fastest, lightest on the processor, no permission problems.

> [!WARN] **Warning: the commands below permanently erase all data on the selected drive!** Make sure you choose the right USB drive and not the system card.

**Step 1:** connect the drive to a USB port (preferably a **blue USB 3.0** one) and check what the system called it:

```bash
lsblk -o NAME,SIZE,MODEL,FSTYPE
```

Example output:

```text
NAME          SIZE MODEL              FSTYPE
sda         931.5G Samsung_SSD_T7
└─sda1      931.5G                    exfat
mmcblk0      29.7G
├─mmcblk0p1   512M                    vfat
└─mmcblk0p2  29.2G                    ext4
```

`mmcblk0` is the system card — **do not touch it**. Your USB drive is almost always `sda` (or `sdb` if two drives are connected) — recognise it by the capacity in the `SIZE` column (a 1 TB drive shows as about `931.5G`) and by the model name.

**Step 2:** unmount the drive (the system may have mounted it automatically), create a new partition table and format the whole drive as `ext4`. The example assumes the drive is `sda` — if yours is `sdb`, change the letter **in all three lines**:

```bash
sudo umount /dev/sda1
sudo parted -s /dev/sda mklabel gpt mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L PLEX_DISK /dev/sda1
```

What each line does:

- `umount /dev/sda1` — detaches the partition if the system mounted it (the message `not mounted` is normal — ignore it),
- `parted … mklabel gpt` — creates a new, empty GPT partition table; `mkpart primary ext4 0% 100%` — one partition over the whole drive,
- `mkfs.ext4 -L PLEX_DISK /dev/sda1` — formats the partition and labels it `PLEX_DISK`.

Formatting a large drive takes from a few seconds to a few minutes — wait until the prompt `pi@raspberrypi:~ $` returns.

### 2.2. Scenario B: a drive that already has movies (NTFS / exFAT) {#existing-disk}

If you have a drive with movies from a Windows computer (format `ntfs`) or from a Mac or USB stick (format `exfat`), **do not format it**. The Raspberry Pi reads and writes both formats without losing data — it only needs the right entry in step 2.4.

> [!WARN] **Drives from Windows:** before unplugging the drive from a Windows computer, use **“Safely Remove Hardware”**. A drive pulled out without it, or from a computer with *Fast Startup* turned on, is mounted by Linux **read-only** — the panel cannot save movies to it. Fix: plug the drive back into Windows, run the disk check there (Properties → Tools → Check) and remove it safely.

### 2.3. Scenario C: formatting on your computer (no terminal, exFAT) {#format-gui}

If you prefer windows to the terminal, or the drive will sometimes go into a computer, format it as **exFAT** — Windows, macOS and the Raspberry Pi all read it. All data on the drive will be erased.

**Windows 10/11:**

1. Connect the drive and open **File Explorer** → **This PC**.
2. **Right-click** the drive → **Format…**
3. File system: **exFAT**, allocation unit size: **default**, volume label: e.g. `PLEX_DISK`, tick **Quick Format** → **Start**.

**macOS:**

1. Connect the drive and open **Disk Utility** (Cmd+Space → type “Disk Utility”; or Finder → Applications → Utilities).
2. In the **View** menu choose **Show All Devices** — without it you only see the partition, not the whole drive.
3. In the list on the left select **the whole drive** (the top entry with the maker's name), click **Erase**.
4. Name: e.g. `PLEX_DISK`, Format: **ExFAT**, Scheme: **GUID Partition Map** → **Erase**.

Then connect the drive to the Raspberry Pi and go to step 2.4 (variant 3 — exFAT).

### 2.4. Mounting the drive permanently (/etc/fstab) {#fstab}

Without an entry in `/etc/fstab` the Raspberry Pi “forgets” the drive after every restart and Plex reports missing files.

**Step 1: read the partition's identifier (UUID) and its format (FSTYPE):**

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID
```

Find your partition (e.g. `sda1`) and copy the text from the `UUID` column — for an ext4 drive it looks like `a1b2c3d4-e5f6-7890-1234-567890abcdef`, for NTFS/exFAT it is shorter, e.g. `4A8C-19F2`. Note the `FSTYPE` value (`ext4`, `ntfs` or `exfat`).

**Step 2: create the folder — the mount point:**

```bash
sudo mkdir -p /mnt/ssd1
```

**Step 3: add the drive to /etc/fstab.** Open the file in the editor:

```bash
sudo nano /etc/fstab
```

Move with the arrow keys **to the very end** of the file (below the existing lines — **do not change them**) and paste **only one** of the lines below, matching your drive's `FSTYPE`. Replace `YOUR_UUID` with the code from step 1.

**Variant 1 — Linux drive (FSTYPE = `ext4`):**

```text
UUID=YOUR_UUID  /mnt/ssd1  ext4  defaults,nofail  0  2
```

**Variant 2 — drive from Windows (FSTYPE = `ntfs`):**

```text
UUID=YOUR_UUID  /mnt/ssd1  ntfs3  defaults,nofail,uid=pi,gid=pi,umask=002  0  0
```

**Variant 3 — drive from a Mac or USB stick (FSTYPE = `exfat`):**

```text
UUID=YOUR_UUID  /mnt/ssd1  exfat  defaults,nofail,uid=pi,gid=pi,umask=002  0  0
```

Save the file: **Ctrl+O**, **Enter**, **Ctrl+X**.

**What the fields of the line mean:**

| Field | Example | Meaning |
|---|---|---|
| 1. what | `UUID=…` | The exact partition, recognised by its identifier — works even after moving the cable to another USB port. |
| 2. where | `/mnt/ssd1` | The mount point from step 2. |
| 3. format | `ext4` / `ntfs3` / `exfat` | The file system driver (for NTFS the driver is called `ntfs3`). |
| 4. options | `defaults,nofail` | `defaults` — standard settings; **`nofail`** — if the drive is unplugged, the Raspberry Pi still starts normally (without it, it stops on an emergency screen!). |
| | `uid=pi,gid=pi,umask=002` | NTFS/exFAT only: these formats have no Linux permissions, so all files “belong” to the user `pi`; `umask=002` — others (e.g. Plex) can read. |
| 5. dump | `0` | An old backup tool — always 0. |
| 6. check | `2` / `0` | `2` — check the ext4 drive at start; `0` — do not check (NTFS/exFAT). |

**Step 4: test the mounting without a restart:**

```bash
sudo systemctl daemon-reload
sudo mount -a
df -h /mnt/ssd1
```

If there is no error and the table shows your drive's capacity mounted at `/mnt/ssd1` — it works.

**Step 5: the real test — a restart:**

```bash
sudo reboot
```

After a minute log in again (`ssh plex` or `ssh pi@192.168.1.10`) and type `df -h /mnt/ssd1` — the drive should be there without any commands.

> [!TIP] **Common errors with `mount -a`:**
>
> - `unknown filesystem type 'ntfs3'` — an older system without the `ntfs3` driver. Install the alternative driver `sudo apt install -y ntfs-3g` and change `ntfs3` to `ntfs-3g` in your fstab line.
> - `unknown filesystem type 'exfat'` — install exFAT support: `sudo apt install -y exfat-fuse exfatprogs`.
> - `wrong fs type, bad option` — usually a typo in the fstab line (check the commas and that there are no spaces in the options) or a variant that does not match `FSTYPE`.
> - An NTFS drive mounts read-only — see the warning in scenario B.

### 2.5. Library folders and permissions {#folders}

Plex runs on the system as a separate user `plex` (it must be able to **read** movies), while Plex Downloader runs as you — `pi` (it must be able to **write and delete**). Create the library folders and set the permissions:

```bash
mkdir -p "/mnt/ssd1/Plex/Movies" "/mnt/ssd1/Plex/TV Shows" "/mnt/ssd1/Plex/Kids"
sudo chown -R pi:pi /mnt/ssd1/Plex
sudo chmod -R 755 /mnt/ssd1/Plex
```

- `mkdir -p` — creates the folders (the quotes are needed because `TV Shows` contains a space),
- `chown -R pi:pi` — the user `pi` becomes the owner of the folders,
- `chmod -R 755` — the owner can do everything, everyone else (including Plex) can read.

> [!INFO] On **NTFS/exFAT** drives `chown` and `chmod` may report an error or change nothing — that is normal, the permissions are already set by the `uid=pi,gid=pi,umask=002` options in fstab. Always run the first line (`mkdir`).

### Test option: the library on the SD card {#plex-sd}

**Not recommended for everyday use.** The SD card is small, slower than a drive and wears out faster. When it fills up completely, the whole system may stop working — always leave a few GB free. The folders then go into your home folder:

```bash
mkdir -p ~/Plex/Movies "$HOME/Plex/TV Shows" ~/Plex/Kids
chmod o+x ~
```

The second line lets Plex “pass through” your home folder to the `Plex` folder (without the right to see your other files). In the wizard choose **Library on the SD card**.

## Installing Plex Downloader and Plex Media Server {#install data-stage="STAGE 3"}

With the drive ready, install Plex Downloader first. It includes the repair menu `fix.sh`, which can also install the Plex server with one choice.

### 3.1. Installing Plex Downloader {#downloader-install}

Paste the whole block into the Raspberry Pi console:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd ~/plex-downloader
chmod +x setup.sh update.sh fix.sh
./setup.sh
```

- `apt install -y git` — the program that downloads code from GitHub (not included in Raspberry Pi OS Lite),
- `git clone …` — downloads Plex Downloader into the folder `~/plex-downloader`,
- `chmod +x` — allows the scripts to run,
- `./setup.sh` — the installer (run it **without** `sudo` — it asks for the password itself when needed).

The installer takes you through 5 steps:

1. **It asks for the language** — press **Enter** for English (or type `2` for Polish).
2. **It installs system tools** (`aria2`, Python, `ffmpeg`). On a Pi Zero this can take 5–15 minutes — **do not interrupt it, even if nothing changes on the screen for a long while**.
3. **It prepares the Python environment.** On weak Wi-Fi, `Retrying…` messages are normal. If the installation stops because the network dropped, **paste this command** (the whole of it, including going to the program folder):

   ```bash
   cd ~/plex-downloader && ./setup.sh
   ```

   **The installation starts again — you do not lose your progress:** whatever is already installed stays, and the installer finishes the rest.
4. **It asks you to create the panel administrator account** — enter a **new** user name and a **new password** for the panel in the browser (password at least 6 characters, typed twice). This account is only for the panel — it does not have to match the Raspberry Pi login. Pressing **Enter** at the user name accepts the suggestion `admin`. **Remember:** you type the password “blind” — **no dots or asterisks appear on the screen**. Write it down.
5. **It starts the service in the background and shows the panel address**, e.g. `http://192.168.1.10:8800` — note the port **8800** (not 8080). You will type this address into your browser in step 3.3.

### 3.2. Installing Plex Media Server {#plex-install}

**Recommended — the `fix.sh` menu:**

```bash
cd ~/plex-downloader && ./fix.sh
```

In the menu choose **7 Additional modules → Plex Media Server → Install**. The script adds the official Plex repository, installs the server and shows its address.

**Alternative — by hand (the whole block):**

```bash
sudo apt update
sudo apt install -y curl gnupg
curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/plex.gpg
echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://downloads.plex.tv/repo/deb public main" \
  | sudo tee /etc/apt/sources.list.d/plexmediaserver.list
sudo apt update
sudo apt install -y plexmediaserver
```

**First Plex setup (in the browser on your computer):**

1. Open `http://192.168.1.10:32400/web` (your Raspberry Pi's address + port **32400** + `/web`).
2. Sign in to a Plex account or create one for free (e-mail, Google or Apple). Plex Pass (paid) is **not needed**.
3. Give the server a name, e.g. `Home Plex`, and continue.
4. Click **Add Library** and for each library choose the type, name and folder (**Browse for media folder** → choose the folder → **Add**):

| Library type | Name (any) | Folder |
|---|---|---|
| Movies | Movies | `/mnt/ssd1/Plex/Movies` |
| TV Shows | TV Shows | `/mnt/ssd1/Plex/TV Shows` |
| Movies | Kids | `/mnt/ssd1/Plex/Kids` |

5. Click **Add Library** — Plex starts scanning the folders. Empty folders are fine: movies appear after the first download.

### 3.3. First start of the panel and the setup wizard {#wizard}

Open `http://192.168.1.10:8800` in your browser and log in with the **panel administrator name and password** you chose in step 3.1 (point 4) — not the Raspberry Pi or Plex password. On the first start the **setup wizard** opens (later you can run it again in **Settings → Account → Run setup wizard**). Every step has an “Installation guide ↗” link to the matching chapter of this guide.

1. **Language** and **Theme** — choose how the panel looks. If you are moving your configuration from another device, click **I have a settings file – load it** and choose the saved JSON file.
2. **Installation** — choose **External disks**, **SD card (not recommended)** or **Plex on another device** (see Three ways to install).
3. **Disks and folders** {#wizard-disks} — the wizard scans mounted drives (it reads only folder **names**, never file contents) and assigns folders such as `Movies`, `Films`, `TV Shows`, `Series`, `Kids` or `Cartoons` by itself. Unusual folders next to your library (e.g. `Movies02`) appear as **+ Movies02** buttons — a click adds them as a new category. You can create a missing folder with the yellow **Create** button or with **Create missing folders when finishing** (off by default).
4. **Plex server** — servers on your home network are found automatically. Enter an address by hand only when the server is in another subnet or behind a VPN.
5. **TMDB key** {#tmdb} (optional, free) — lets the panel fetch posters, ratings and descriptions. How to get one — step by step in the box below this list. Paste the **API Key** or the **API Read Access Token** — the wizard checks it at once. Leave **Generate posters myself from video frames** off at first: on a Raspberry Pi it takes 10–20 seconds per movie, and you can always pick a frame by hand in the Edit window.
6. **Summary → Finish** — saves the settings and creates a restore point.

> [!INFO] **A free TMDB key — step by step** {#tmdb-key}
>
> 1. Go to **themoviedb.org** and click **Join TMDB**. Enter a user name, password and e-mail, then click the link in the confirmation e-mail.
> 2. Log in, click **your avatar** (top right) → **Settings** → **API** in the menu on the left.
> 3. Click **Create** (or “Click here to request an API key”), choose **Developer** and accept the terms.
> 4. Fill in the short form: type of use **Personal**, application name e.g. `Plex Downloader`, URL e.g. `http://localhost`, a short summary e.g. “home movie server”. The form also asks for your address details.
> 5. After submitting you see the **API Key** (32 characters) and the longer **API Read Access Token** — copy **one of them** and paste it into the wizard or into **Settings → Preview & posters**.
>
> The key is private — do not share it with anyone.

## Setup on two devices (optional) {#two-devices data-stage="STAGE 4"}

This stage is for two devices: e.g. a **Pi 4 with drives and Plex** (`192.168.1.10`) and a **Pi Zero 2 W with Plex Downloader** (`192.168.1.20`), which saves downloads to the first one's drive over your home network.

> [!INFO] In this setup downloads are slower — every megabyte crosses the network twice (from the internet to the Pi Zero, then over Wi-Fi to the Pi with Plex).

**Step 1 (router):** give both Raspberry Pis fixed IP addresses (DHCP reservation — see Stage 0).

### 4.1. On the Pi with Plex: sharing the drive (Samba) {#samba}

Install the Samba file server: `cd ~/plex-downloader && ./fix.sh` → **7 Additional modules → Samba → Install** (or `sudo apt install -y samba`). Open its configuration file:

```bash
sudo nano /etc/samba/smb.conf
```

Go to the very end of the file and add the section (each setting on its own line):

```ini
[Plex SSD1]
   path = /mnt/ssd1/Plex
   valid users = pi
   read only = no
   force user = pi
```

- `[Plex SSD1]` — the share name visible on the network,
- `path` — the folder you share,
- `valid users = pi` — access only for the user who knows the password (no guest access),
- `read only = no` — writing is allowed,
- `force user = pi` — files saved over the network belong to `pi`.

Save the file (**Ctrl+O**, **Enter**, **Ctrl+X**), set the Samba network password and restart the service:

```bash
sudo smbpasswd -a pi
sudo systemctl restart smbd
```

`smbpasswd` asks twice for a new Samba password (it can differ from the Pi login password — remember it).

### 4.2. On the Pi with Downloader: mounting the share {#cifs}

Install support for network shares and create the mount point (or `cd ~/plex-downloader && ./fix.sh` → **7 → SMB client – mount shares (cifs-utils)**):

```bash
sudo apt update
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/ssd1
```

Create the file with the share password:

```bash
nano ~/.smbcredentials
```

Type **two lines** (with the password you just set with `smbpasswd`):

```text
username=pi
password=YOUR_SAMBA_PASSWORD
```

Save the file and protect it so no one else on the system can read it:

```bash
chmod 600 ~/.smbcredentials
```

> [!WARN] Type the password **directly in the `nano` editor**. If the password contains e.g. a backslash `\`, commands such as `echo` change it and mounting fails with `Permission denied`.

Add the share permanently to `/etc/fstab` on the Pi with Downloader (`sudo nano /etc/fstab`). **This is one line** — it may wrap in this guide, but in the file it must be a single line. The space in the share name `Plex SSD1` is written as `\040`:

```text
//192.168.1.10/Plex\040SSD1  /mnt/ssd1  cifs  credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0,_netdev,nofail  0  0
```

| Part | Meaning |
|---|---|
| `//192.168.1.10/Plex\040SSD1` | The address of the Pi with Plex and the share name |
| `/mnt/ssd1` | Where the share appears on the Pi with Downloader |
| `credentials=…` | The file with the user name and password (step above) |
| `uid=pi,gid=pi` | Files belong to `pi` — Downloader can write them |
| `iocharset=utf8` | Accented and other special characters in file names |
| `vers=3.0` | The SMB protocol version |
| `_netdev,nofail` | Mount after the network is up; a missing share does not block the start |

Save and check:

```bash
sudo systemctl daemon-reload
sudo mount -a
df -h /mnt/ssd1
```

### 4.3. Paths in the wizard {#paths}

Run the wizard in the Downloader panel and choose **Plex on another device**. **The golden rule:** in Plex Downloader you always enter the paths of **the device the panel runs on**. In our example the share is mounted at `/mnt/ssd1`, so movies are in `/mnt/ssd1/Movies`. You change nothing in Plex.

| | Pi with Plex | Pi with Downloader |
|---|---|---|
| Mount point | `/mnt/ssd1` (drive) | `/mnt/ssd1` (network share) |
| Movies folder | `/mnt/ssd1/Plex/Movies` | `/mnt/ssd1/Movies` |

If you moved the settings (JSON file) from the other device and paths show “Folder does not exist”, use **Settings → Disks → Update paths**.

### 4.4. One category, different folder names {#folder-names}

A category is only a button in the panel — each drive has its own folder for it. For example the category **Concerts**: `Concerts` on one drive, `Live` on another. Enter the right path for each drive (or click the yellow **Create** next to an empty field), and in Plex add **both folders to the same library** (library → Edit → Add folders).

## Everyday use of the panel {#downloader data-stage="STAGE 5"}

### Downloading movies and TV shows {#download}

Paste a **direct link to a video file** into **Add a new download**. A direct link is an address that downloads the file straight away — it usually ends with `.mkv`, `.mp4` or `.avi` (e.g. a download link from a file hosting service). Links to pages with a player (YouTube, Netflix etc.) **do not work**. The panel recognises the title, year, season and episode (you can correct every field before starting), shows a card with the TMDB description and the free space on your drives. Choose the drive and category, click **Download file**. The file first downloads into a hidden work folder and moves to the library in one go only at 100% — so Plex never tries to play an unfinished file.

**Advanced options:**

- **Edition** (e.g. `{edition-Director's Cut}`, up to 3 tags) — tells the director's cut from the cinema version in Plex (showing editions needs Plex Pass),
- **File version** (e.g. `1080p`, `4K`) — several quality versions of the same movie in one folder,
- **TMDB ID** (e.g. `{tmdb-19995}`) — forces an exact match in Plex, useful for movies with identical titles.

### Where to watch — availability on streaming services {#where-to-watch}

Before you download something, check whether the movie is already on your streaming service. **Type just the title** into the name field (e.g. `The Silence of the Lambs (1991)`) — no link needed. After a moment the preview card shows the services' logos in the **Where to watch** section, in four groups:

| Group | Meaning |
|---|---|
| **Subscription** | Included in a subscription (e.g. Netflix, Prime Video) — no extra cost if you have that service. |
| **Free** | Free of charge, sometimes with ads. |
| **Rent** | A one-off payment to watch within a set time. |
| **Buy** | The movie stays in your account on that service. |

Clicking a logo opens the offers page for the title. Set the **country** in **Settings → Account → Where to watch – country** (*Automatic* = by the panel language: Polish → Poland, English → United States). Data comes from TMDB, availability from JustWatch. This feature needs a TMDB key (Stage 3).

### File manager {#file-manager}

Two columns with posters — organise your collection by drag and drop or with the **Move** button:

- **Same drive** (e.g. between categories) — the move is instant.
- **Another drive** — copy → **SHA-256** checksum verification (a guarantee the file is not damaged) → only then the original is removed. **Skip SHA-256 verification after moving** makes this noticeably faster (only the file sizes are compared) — useful for files you can easily download again.
- **TV shows** can be moved whole, by season or as selected episodes. Episodes go into the show's folder on the target drive — if it is already there, they join it (keeping the `Season XX` folders).
- Change the order of drives by dragging their tiles; the **gear** on a tile changes the drive's display name.

### Editing names, extras and posters {#edit}

The **pen** icon on a tile (above the bin) opens the Edit window:

- **title, year, TMDB ID** (**Find in TMDB** button), **edition** and **files in the folder**,
- each file has a **kind**: *Movie (version)* or a Plex extra — *Trailer, Behind the scenes, Deleted scene, Interview, Other extra*. An extra gets a name like `Description-trailer.mp4`, so Plex shows it under Extras instead of as a duplicate movie,
- changing only the poster does not rename files; when names change, the **Change** button shows the list of changes and asks for confirmation.

**Posters:** **Own image…** (JPG, PNG, WebP), **Frame from the video** (6 frames to choose from; **Generate others** picks new ones; **Pick a time** shows frames around a moment `h:mm:ss`, and **+10 s** moves it by 10 seconds) or **download the poster from TMDB**. Posters chosen by hand are not overwritten when posters are refreshed in bulk.

### Backups and activity log {#backups}

- **Restore points:** after every settings change the panel creates a copy kept for 30 days (**Settings → Backups**); the newest one is always kept.
- **JSON export / import:** **Export settings** saves drives, categories, servers and options (without the user name, password and session keys; the TMDB key only if you ask). **Import settings…** shows what will change and lets you choose the sections. The drives section is ticked only when the drives from the file are connected to this device — after moving to another device use **Settings → Disks → Update paths**.
- **Activity log:** **Settings → Account → LOG** — the history of downloads, moves, renames and deletions, with the **Clear** and **Export .log** buttons.

## Secure access from outside your home (Tailscale VPN) {#vpn data-stage="STAGE 6"}

**Do not expose** the panel to the internet by forwarding ports on your router. To add movies from your phone on mobile data, from work or a hotel, connect your devices with a private, encrypted **Tailscale** network (free plan for home use, log in with a Google, Apple, Microsoft or GitHub account — always on the Tailscale website; the panel never sees that login).

### 6.1. Installing Tailscale on the Raspberry Pi {#vpn-install}

1. In the terminal start the repair menu: `cd ~/plex-downloader && ./fix.sh`
2. Choose **7 Additional modules → Tailscale VPN (recommended) → Install**. The script installs Tailscale and allows the panel to log in to Tailscale itself.
3. You can skip the login question at the end — it is easier to log in from the browser.

> [!TIP] **`404 Not Found` or `File has unexpected size` errors** during installation (e.g. for the `iptables` package) mean a Raspbian mirror server is broken, not Tailscale. `fix.sh` then offers to download from the main archive — choose **Yes**. If Tailscale was installed earlier in another way, choose **Update** in the same menu — the panel then gets the permission to log in.

### 6.2. Logging in and your phone {#vpn-login}

1. At home open the panel → **Settings → VPN** → **Log in**.
2. A link and a QR code appear. Open the link on your computer or scan the code with your phone, log in and approve adding the Raspberry Pi. After a few seconds the tab shows **Connected to Tailscale** and the **VPN** badge in the header turns green.
3. **Important:** in the console **login.tailscale.com/admin** → **Machines** → the **…** menu next to the Raspberry Pi → **Disable key expiry**. Otherwise Tailscale asks to log the Raspberry Pi in again about every 180 days.
4. Install the **Tailscale** app on your phone (App Store / Google Play) or computer and log in to **the same account**. In the VPN tab, section **Open the panel over VPN**, scan the QR code and add the page to your phone's home screen.

The Raspberry Pi's VPN address (e.g. `100.x.y.z` and the name `raspberrypi.tail1234.ts.net`) is **permanent**. Away from home switch Tailscale on in the app and open the saved shortcut; at home you do not need the VPN.

### 6.3. HTTPS certificate (padlock in the browser) {#vpn-https}

Tailscale traffic is always encrypted, but with an `http://` address the browser shows “Not secure”. In **Settings → VPN** click **Switch HTTPS on** (the first time **Allow HTTPS in Tailscale** appears — allow certificates for your account and click Switch HTTPS on again). The panel is then available at `https://raspberrypi.tail1234.ts.net`, without a port number. The first opening takes 10–20 seconds (the certificate is fetched).

> [!WARN] Do not turn on **Tailscale Funnel** — it publishes the page to the whole internet, not only to your devices. The panel never turns it on and shows a red warning if it is on.

### 6.4. Access control, autostart and WireGuard {#vpn-access}

- **Where the panel is available:** **Home network + VPN** (default) or **Home network only** — then the panel is blocked over VPN, while Tailscale keeps working e.g. for SSH and Plex. You can switch back only from home.
- **Tailscale version** has an **up to date** / **out of date** tag (a red **security update** = an urgent security fix). Update: `fix.sh` → 7 → Tailscale → **Update**.
- **Log out / change account** — the Raspberry Pi leaves the Tailscale network; then **Log in** gives a new link.
- **Autostart:** `cd ~/plex-downloader && ./fix.sh` → 7 → Tailscale → **Autostart: on → turn off** (it does not start after a restart). To disconnect for a while: `sudo tailscale down`, back: `sudo tailscale up` or **Connect** in the panel.
- **WireGuard** — for people with their own WireGuard server (needs UDP port 51820 forwarded on the router and a hand-made `/etc/wireguard/wg0.conf`). Tools: `cd ~/plex-downloader && ./fix.sh` → 7 → **WireGuard VPN**. The VPN tab shows active connections and addresses.

> [!INFO] WireGuard support has been checked only in **synthetic tests** (simulated system commands, no real connection). If something works differently for you, please report it on GitHub (Issues).

## Updates, diagnostics and rescue (fix.sh) {#maintenance data-stage="STAGE 7"}

### Updating Plex Downloader {#update}

When the header of the **Settings** window announces a new version, log in over SSH and run the update (your movies and settings are safe):

```bash
cd ~/plex-downloader && ./update.sh
```

### The fix.sh repair menu {#fix}

If the panel or an extra service misbehaves, run:

```bash
cd ~/plex-downloader && ./fix.sh
```

| Menu option | What it does |
|---|---|
| 1 Update | The newest panel version (like `./update.sh`). |
| 2 Reinstall | Rebuilds the Python environment and program files; **keeps the settings**. |
| 3 Clean reinstall | Factory settings for the panel (you must type `YES`). Movies on the drives are not touched. |
| 4 / 5 BETA version | Switch to the test version or back to the stable one. |
| 6 Server | Status, start, stop, restart of the panel. |
| 7 Additional modules | Plex Media Server, Samba, SMB client, ffmpeg, Tailscale, WireGuard: install, update, autostart on / off, uninstall. |
| 8 Install another version | Back to an older release (from 1.2.5) with an automatic copy of the settings in `.version-snapshots`. |
| 9 Uninstall | Removes the Plex Downloader service and files (movies stay untouched). |

### Raspberry Pi diagnostics (power, temperature, drives) {#diagnostics}

If the Raspberry Pi is slow, loses the USB drive or freezes during downloads, type these one by one:

```bash
vcgencmd get_throttled
vcgencmd measure_temp
df -h
free -h
uptime
```

| Command | What it shows | Good result |
|---|---|---|
| `vcgencmd get_throttled` | Power and overheating problems | `throttled=0x0` — any other value: **weak power supply** or overheating |
| `vcgencmd measure_temp` | Processor temperature | below about 70 °C (from 80 °C the processor slows down) |
| `df -h` | Free space on the card (`/`) and drives (`/mnt/ssd1`) | card: a few GB free |
| `free -h` | Memory (RAM) use | `available` column above a few tens of MB |
| `uptime` | Time since start | long — a short time means an unnoticed restart |

**Errors since the last start:**

```bash
journalctl -u plex-downloader -n 50 --no-pager
dmesg -T | grep -iE "voltage|mmc|i/o error|cifs" | tail
```

The first line: the last 50 entries of the Plex Downloader log. The second: power errors (`voltage`), SD card (`mmc`), USB drives (`i/o error`) and network shares (`cifs`).

**Keeping logs after a restart.** Raspberry Pi OS often keeps the log only in memory — after a freeze and restart you cannot see what happened. Turn on saving to the card (works on every system version):

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=persistent\n' \
  | sudo tee /etc/systemd/journald.conf.d/99-persistent.conf
sudo systemctl restart systemd-journald
```

After the next restart `journalctl -b -1` shows the events from just before the failure.

### Home network security — checklist {#security}

- Do not forward port `8800` on your router (nor `32400` without a clear need) and do not put the Raspberry Pi in a DMZ — from outside use only the VPN (Stage 6).
- Strong passwords for the panel, the system account and Samba; log in to the terminal with SSH keys (Stage 1).
- Update the system regularly: `sudo apt update && sudo apt full-upgrade -y`.
- The files `config.json` (TMDB key) and `~/.smbcredentials` (Samba password) contain confidential data — never share them.

## When something does not work — common problems {#faq data-stage="FAQ"}

| Symptom | What to check |
|---|---|
| The panel does not open (`http://…:8800`) | Is the Raspberry Pi on and does it have the same address (`hostname -I`)? Service status: `cd ~/plex-downloader && ./fix.sh` → **6 Server**. Log: `journalctl -u plex-downloader -n 50 --no-pager`. |
| I cannot connect over SSH | Was SSH enabled in Raspberry Pi Imager (Stage 0)? Has the IP address changed? Try `ssh pi@raspberrypi.local`. |
| The drive is gone after a restart | Does the `/etc/fstab` line have `nofail` and the right UUID? Check `lsblk -o NAME,FSTYPE,UUID` and `sudo mount -a`. |
| Plex does not see a new movie | In Plex: library → **…** menu → **Scan Library Files**. Check that the movie is in a folder assigned to that library. |
| Drive is read-only (NTFS) | The drive was unplugged from Windows without “Safely Remove” — see Stage 2, scenario B. |
| Downloads stall or the Pi freezes | `vcgencmd get_throttled` — anything other than `0x0` is almost always the power supply. Free space: `df -h`. |
| “Folder does not exist” in the disk settings | The drive is not connected or the path comes from another device — **Settings → Disks → Update paths**. |

## Glossary {#glossary data-stage="GLOSSARY"}

| Term | Meaning |
|---|---|
| **Terminal / console** | A window where you type text commands instead of clicking. |
| **SSH** | A secure connection to another computer over the network — the Raspberry Pi's terminal opened on your computer. |
| **sudo** | Put before a command: “run as administrator”. It asks for the password. |
| **Mount point** | A folder (e.g. `/mnt/ssd1`) where the drive's contents appear — like the letter `D:` on Windows. |
| **UUID** | A unique identifier of a drive partition — the system recognises the drive by it in any USB port. |
| **fstab** | The file `/etc/fstab` with the list of drives mounted automatically at start. |
| **ext4 / NTFS / exFAT** | Drive formats: Linux / Windows / universal (Windows, Mac, Linux). |
| **Samba (SMB)** | Sharing folders on your home network (like a “shared folder” on Windows). |
| **VPN (Tailscale)** | A private, encrypted network of your devices — reach home from anywhere without opening ports. |
| **TMDB** | The Movie Database — the free movie database the posters and descriptions come from. |
