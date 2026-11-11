# Plex Downloader – instrukcja {#top}

Ta instrukcja prowadzi krok po kroku od czystego Raspberry Pi do działającej biblioteki Plex z menedżerem pobierania. Przykładowe adresy i nazwy (`192.168.1.10`, `pi`, `SSD 1TB`) zamień na swoje.

## 1. Jak to działa {#intro}

**Plex Media Server** odtwarza filmy i seriale na telewizorze, telefonie i komputerze. **Plex Downloader** to panel w przeglądarce, który:

- pobiera pliki z bezpośrednich linków (kilka połączeń naraz, wznawianie po restarcie),
- od razu nadaje im nazwy zgodne z zasadami Plexa (`Tytuł (Rok)/Tytuł (Rok).mkv`, `Serial/Season 01/Serial - S01E02.mkv`),
- ma **Menedżer plików**: przenoszenie między dyskami z weryfikacją SHA-256, zmianę nazw i plakatów, usuwanie.

### Trzy sposoby instalacji {#scenarios}

| Sposób | Dla kogo | Uwagi |
|---|---|---|
| **Dyski zewnętrzne** (zalecany) | Plex i Downloader na jednym Raspberry Pi, biblioteka na dysku SSD/HDD lub pendrivie | najszybszy i najprostszy |
| **Karta SD** (niezalecany) | szybki test bez dysków | karta jest mała, wolna i zużywa się przy dużych zapisach |
| **Dwa urządzenia** | Plex na jednym komputerze, Downloader na drugim (np. Pi Zero 2 W) | biblioteka udostępniona przez SMB; pobieranie wolniejsze |

**Wymagania:** Raspberry Pi z Raspberry Pi OS (32 lub 64 bit), dostęp przez SSH, połączenie z internetem. Najlepiej z oryginalnym zasilaczem – słaby zasilacz to najczęstsza przyczyna zawieszania się maliny.

## 2. Instalacja Plex Media Server {#plex}

Jeśli Plex już działa, przejdź do [rozdziału 3](#downloader).

### Najprościej: przez fix.sh {#plex-fix}

Po zainstalowaniu Plex Downloadera (rozdział 3) uruchom `./fix.sh` → **7 Moduły dodatkowe** → **Plex Media Server** → **Zainstaluj**. Skrypt doda oficjalne repozytorium Plex i zainstaluje serwer. Na końcu pokaże adres `http://<adres-pi>:32400/web` – otwórz go w przeglądarce i zaloguj się kontem Plex.

### Ręcznie {#plex-manual}

```bash
sudo apt install -y curl gnupg
curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | sudo gpg --dearmor -o /usr/share/keyrings/plex.gpg
echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://downloads.plex.tv/repo/deb public main" | sudo tee /etc/apt/sources.list.d/plexmediaserver.list
sudo apt update && sudo apt install -y plexmediaserver
```

### Dysk zewnętrzny: stałe montowanie {#plex-disks}

Dysk musi być **zamontowany na stałe** (także po restarcie), inaczej Plex i Downloader nie znajdą biblioteki.

1. Sprawdź nazwę i UUID dysku:
   ```bash
   lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT
   ```
2. Utwórz punkt montowania, np. `/mnt/ssd1`:
   ```bash
   sudo mkdir -p /mnt/ssd1
   ```
3. Dopisz linię do `/etc/fstab` (`sudo nano /etc/fstab`), podając UUID z punktu 1:
   ```
   UUID=1234-ABCD  /mnt/ssd1  ext4  defaults,nofail  0  2
   ```
   Dla dysku sformatowanego w exFAT lub NTFS zamiast `ext4` wpisz `exfat` lub `ntfs3` i dodaj `uid=pi,gid=pi`, np. `defaults,nofail,uid=pi,gid=pi`.
4. Zamontuj i sprawdź – brak błędu oznacza, że dysk zamontuje się też po restarcie:
   ```bash
   sudo mount -a && df -h /mnt/ssd1
   ```
5. Utwórz foldery biblioteki (albo zrobi to kreator – rozdział 3):
   ```bash
   mkdir -p "/mnt/ssd1/Plex/Movies" "/mnt/ssd1/Plex/TV Shows" "/mnt/ssd1/Plex/Kids"
   ```

**Uprawnienia:** Plex działa jako użytkownik `plex`, a Plex Downloader jako Ty (np. `pi`). Plex musi móc czytać foldery, Downloader – zapisywać:

```bash
sudo chown -R pi:pi /mnt/ssd1/Plex
sudo chmod -R 755 /mnt/ssd1/Plex
```

W aplikacji Plex dodaj biblioteki: **Filmy** → `/mnt/ssd1/Plex/Movies`, **Seriale** → `/mnt/ssd1/Plex/TV Shows` itd.

### Wariant testowy: biblioteka na karcie SD {#plex-sd}

**Niezalecany na co dzień.** Karta SD jest mała, wolniejsza od dysku i szybciej się zużywa. Gdy zapełni się całkowicie, cały system może przestać działać – zostaw na niej zawsze kilka GB wolnego miejsca.

Biblioteka leży wtedy w katalogu domowym, np. `/home/pi/Plex/Movies`. Kreator Plex Downloadera ma do tego gotowy wariant **„Biblioteka na karcie SD”**, a w Ustawienia → Dyski jest przycisk **„+ Karta SD (niezalecane)”**. Jeśli chcesz kopiować pliki z komputera, udostępnij folder `Plex` przez SMB ([rozdział 4](#samba)).

## 3. Instalacja Plex Downloadera {#downloader}

Zaloguj się na Raspberry Pi przez SSH (np. `ssh pi@192.168.1.10`, szczegóły w [rozdziale 7](#ssh)) i wpisz:

```bash
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd plex-downloader
chmod +x setup.sh update.sh fix.sh
./setup.sh
```

Skrypt:

1. pyta o język (1 – English, 2 – Polski),
2. instaluje pakiety systemowe (aria2, Python, git) oraz ffmpeg – **na Pi Zero to może potrwać 5–15 minut**,
3. tworzy środowisko Pythona; przy słabym Wi-Fi ostrzeżenia `Retrying…` są normalne – jeśli pobieranie się nie uda, uruchom `./setup.sh` ponownie, nic nie przepada,
4. pyta o **nazwę użytkownika i hasło** do panelu (min. 6 znaków),
5. uruchamia usługę i podaje adres panelu, np. **http://192.168.1.10:8800**.

> **Port to 8800**, nie 8080.

### Kreator konfiguracji {#wizard}

Po pierwszym zalogowaniu otwiera się kreator. Można go uruchomić ponownie w **Ustawienia → Konto → Uruchom kreator** – zaczyna wtedy od zera (zachowuje tylko kategorie i zapisany klucz TMDB). **Zamknij bez zapisywania** zostawia obecne ustawienia bez zmian.

1. **Język i motyw.** Na pierwszym kroku jest też przycisk **„Mam plik ustawień – wczytaj”** – przydaje się przy drugim Raspberry Pi albo po ponownej instalacji ([rozdział 5](#backup)). Bez pliku kreator przeprowadzi Cię przez wszystko po kolei.
2. **Gdzie jest biblioteka:** dyski zewnętrzne, karta SD albo Plex na innym urządzeniu.
3. <a id="wizard-disks"></a>**Dyski i foldery**
   - Kreator sprawdza zamontowane dyski (lub udziały sieciowe) i **sam zaznacza** te, na których znalazł foldery biblioteki. Czyta tylko nazwy folderów – nigdy ich zawartość.
   - Rozpoznaje typowe nazwy i odmiany: `Movies`, `Filmy`, `Cinema`, `TV Shows`, `Seriale`, `Kids`, `Bajki`, `Home Video` = `Home Videos`… Foldery z muzyką i zdjęciami pomija.
   - Przy każdej kategorii: **⚙** zmienia nazwę kategorii (np. „Dla dzieci” → „Koncerty”), **✕** oznacza „nie na tym dysku”, **↺** przywraca kategorię z podpowiedzianym folderem, **+ Dodaj kategorię** tworzy nową.
   - Nietypowe foldery obok biblioteki (np. `Movies02`) pojawiają się jako przyciski **„+ Movies02”** – kliknięcie dodaje je jako nową kategorię.
   - **Utwórz brakujące foldery przy zakończeniu** jest domyślnie wyłączone. Foldery, których nie ma i które nie zostaną utworzone, są pomijane.
   - **Dalej** wystarczy, gdy na którymkolwiek dysku jest folder Filmy albo Seriale. **Pomiń – skonfiguruję dyski później** służy do sytuacji, gdy nie ma jeszcze żadnej biblioteki.
4. **Serwer Plex.** Serwery w sieci domowej są wykrywane automatycznie. Ręcznie dodaj tylko serwer w innej podsieci lub za VPN.
5. <a id="tmdb"></a>**Klucz TMDB** (opcjonalny, darmowy): załóż konto na themoviedb.org → Ustawienia → API → utwórz klucz (wystarczy „Personal use”) i wklej **API Key** albo **API Read Access Token**. Kreator od razu go sprawdza: **✓ Klucz poprawny** / **✗ Nieprawidłowy klucz**. Z kluczem masz kartę podglądu filmu i plakaty w Menedżerze plików.
   - **Samodzielnie generuj miniatury z kadrów filmu (wymaga ffmpeg)** – dla nagrań domowych i tytułów, których nie ma w TMDB. Nie zalecamy włączania od razu: na Pi 4 / Pi 400 to ok. 10–15 s na film, na Pi Zero dłużej. Pojedynczy plakat z kadru zrobisz zawsze w oknie edycji filmu ([rozdział 5](#edit)).
6. **Podsumowanie → Zakończ.** Poprzednie ustawienia zostają jako punkt przywracania.

## 4. Dwa urządzenia: Plex na jednym, Downloader na drugim {#two-devices}

Przykład: **Pi z Plexem** (`192.168.1.10`) ma podłączone dyski, **Pi z Downloaderem** (`192.168.1.20`, np. Pi Zero 2 W) zapisuje na nie przez sieć.

1. **Stałe adresy IP.** W routerze przypisz obu urządzeniom stałe adresy (rezerwacja DHCP).
2. **Udostępnij bibliotekę na Pi z Plexem** (Samba).
3. **Zamontuj udział na Pi z Downloaderem** (cifs, na stałe w fstab).
4. Uruchom kreator i wybierz **„Plex na innym urządzeniu”**.

> Pobieranie jest w tym układzie wolniejsze: każdy bajt przechodzi przez sieć dwa razy. Przez Wi-Fi 2,4 GHz (Pi Zero 2 W) licz się z kilkoma MB/s.

### Udostępnienie folderów (Samba) – na Pi z Plexem {#samba}

`./fix.sh` → **7 Moduły dodatkowe** → **Samba** → **Zainstaluj**, albo `sudo apt install -y samba`. Potem dopisz udział na końcu `/etc/samba/smb.conf` (`sudo nano /etc/samba/smb.conf`):

```
[Plex SSD1]
   path = /mnt/ssd1/Plex
   valid users = pi
   read only = no
   force user = pi
```

Ustaw hasło Samby dla użytkownika i uruchom ponownie usługę:

```bash
sudo smbpasswd -a pi
sudo systemctl restart smbd
```

`valid users` sprawia, że do udziału wejdzie tylko ten użytkownik – nie udostępniaj biblioteki „dla wszystkich”.

### Montowanie udziału – na Pi z Downloaderem {#cifs}

```bash
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/ssd1
nano ~/.smbcredentials
```

W pliku `~/.smbcredentials` wpisz dwie linie i zapisz (Ctrl+O, Enter, Ctrl+X):

```
username=pi
password=TWOJE_HASLO_SAMBY
```

```bash
chmod 600 ~/.smbcredentials
sudo mount -t cifs "//192.168.1.10/Plex SSD1" /mnt/ssd1 -o credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0
```

> **Hasło ze znakiem `\`:** wpisuj je w `nano`, nie przez `echo` ani `printf` – te polecenia zmieniają ukośnik wsteczny i montowanie kończy się błędem `mount error(13): Permission denied`.

Na stałe – dopisz do `/etc/fstab` (spacja w nazwie udziału to `\040`):

```
//192.168.1.10/Plex\040SSD1  /mnt/ssd1  cifs  credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0,_netdev,nofail  0  0
```

Sprawdź: `sudo mount -a && df -h /mnt/ssd1`. W kreatorze udział pojawi się na liście „Udziały sieciowe zamontowane na tym Raspberry Pi”.

### Ten sam dysk, dwie różne ścieżki {#paths}

Każde urządzenie widzi wspólny dysk pod własną ścieżką:

| | Pi z Plexem | Pi z Downloaderem |
|---|---|---|
| Punkt montowania | `/mnt/ssd1` | `/mnt/ssd1` lub np. `/mnt/plex_ssd` |
| Folder „Koncerty” | `/mnt/ssd1/Plex/Concerts` | `/mnt/plex_ssd/Concerts` |

W Plex Downloaderze zawsze wpisuj ścieżki **urządzenia, na którym działa panel**. Ścieżka przepisana z drugiego Pi pokaże „Folder nie istnieje” – wtedy **Ustawienia → Dyski → Aktualizuj ścieżki** przeniesie ją na właściwy punkt montowania (to samo po imporcie ustawień z drugiego urządzenia). W Plexie nic nie zmieniasz.

### Ta sama kategoria, różne nazwy folderów {#folder-names}

Kategoria to tylko przycisk w panelu – każdy dysk ma dla niej własny folder. Np. kategoria **Koncerty**: na jednym dysku `Concerts`, na drugim `Live`. Wpisz właściwą ścieżkę przy każdym dysku (albo kliknij żółte **Utwórz** przy pustym polu), a w Plexie dodaj **oba foldery do tej samej biblioteki** (biblioteka → Edytuj → Dodaj foldery).

## 5. Codzienna praca {#usage}

### Pobieranie {#download}

Wklej bezpośredni link do pliku wideo. Panel rozpozna tytuł, rok, sezon i odcinek (wszystko możesz poprawić), pokaże kartę z TMDB i wolne miejsce na dysku. Wybierz dysk i kategorię, kliknij **Pobierz**. Plik trafia najpierw do ukrytego folderu tymczasowego i dopiero po pobraniu – jednym ruchem – do biblioteki.

Opcje zaawansowane: **wydanie** (`{edition-Director's Cut}`, do 3 tagów, wymaga Plex Pass), **wersja pliku** (` - 1080p`, kilka wersji w jednym folderze) i **TMDB ID** (`{tmdb-19995}`, dokładne dopasowanie w Plexie).

### Menedżer plików {#files}

Dwie kolumny z plakatami. **Przeciągnij** film z jednej kolumny do drugiej:

- ten sam dysk – przeniesienie natychmiastowe,
- inny dysk – kopia → weryfikacja SHA-256 → dopiero wtedy usunięcie oryginału (opcja **Pomiń weryfikację SHA-256** przyspiesza to dwukrotnie, porównując tylko rozmiary).

Seriale przeniesiesz w całości, sezonami albo wybrane odcinki. Kolejność dysków zmienisz, przeciągając kafelki; zębatka na kafelku zmienia nazwę dysku.

### Edycja nazwy i plakatu {#edit}

Ikona **długopisu** na kafelku (nad koszem) otwiera okno edycji:

- **tytuł, rok, TMDB ID** (przycisk **Szukaj w TMDB**), **wydanie** i **pliki w folderze**,
- każdy plik ma **rodzaj**: *Film (wersja)* albo dodatek Plexa – *Zwiastun, Za kulisami, Scena usunięta, Wywiad, Inny dodatek*. Dodatek dostaje nazwę `Opis-trailer.mp4` i Plex pokaże go w Dodatkach, a nie jako drugą wersję filmu,
- nazwy plików zmieniają się dopiero po edycji pól – sama zmiana plakatu niczego nie przemianowuje,
- **Zmień** pokazuje listę zmian i pyta „Czy na pewno?”.

**Plakat:** *Własny obrazek…* (JPG, PNG, WebP), *Kadr z filmu* (6 kadrów do wyboru; **Generuj inne** losuje nowe; **Wskaż czas** pokazuje kadry wokół podanego czasu `h:mm:ss`, a **+10 s** przesuwa o 10 sekund) albo *pobierz plakat z TMDB*. Plakaty wybrane ręcznie nie są nadpisywane przy odświeżaniu plakatów.

### Kopie ustawień, eksport i import {#backup}

- Po każdej zmianie ustawień powstaje **punkt przywracania** (Ustawienia → Kopie zapasowe), przechowywany 30 dni.
- **Eksportuj ustawienia** zapisuje plik JSON (dyski, kategorie, serwery, opcje) – bez loginu, hasła i kluczy sesji; klucz TMDB tylko na życzenie.
- **Importuj ustawienia…** pokazuje, co się zmieni, i pozwala wybrać sekcje. Dyski z innego urządzenia są domyślnie odznaczone.

### Dziennik zdarzeń {#log}

Ustawienia → Konto → **LOG**: pobrania, przeniesienia, usunięcia, zmiany nazw. Przyciski Wyczyść i Eksportuj.

## 6. Aktualizacja, naprawa i diagnostyka {#maintenance}

### Aktualizacja {#update}

```bash
cd ~/plex-downloader && ./update.sh
```

Nagłówek okna Ustawień pokazuje, czy jest nowsza wersja stabilna.

### Menu naprawy fix.sh {#fix}

```bash
cd ~/plex-downloader && ./fix.sh
```

1. **Aktualizacja** – instaluje nową wersję stabilną,
2. **Reinstalacja** – odbudowuje środowisko, ustawienia zostają,
3. **Czysta reinstalacja** – ustawienia fabryczne (potwierdzenie słowem TAK),
4. **Zainstaluj / zaktualizuj BETA**,
5. **Wyjście z BETA**,
6. **Serwer** – status, wstrzymanie / uruchomienie, restart,
7. **Moduły dodatkowe** – Plex Media Server, Samba, klient SMB, ffmpeg, Tailscale VPN (zalecany), WireGuard VPN: status, instalacja, aktualizacja, zatrzymanie do restartu, restart, odinstalowanie,
8. **Odinstaluj**,
9. **Anuluj**.

Twoje filmy i seriale nigdy nie są ruszane.

### Diagnostyka Raspberry Pi {#diagnostics}

```bash
uptime                          # jak długo działa bez restartu
vcgencmd get_throttled          # 0x0 = zasilanie i temperatura w porządku
vcgencmd measure_temp           # temperatura (problem od ok. 80 °C)
free -h                         # pamięć
df -h                           # miejsce na karcie i dyskach
journalctl -u plex-downloader -n 50 --no-pager     # log Plex Downloadera
dmesg -T | grep -iE "voltage|mmc|i/o error|cifs" | tail
```

Żeby log przetrwał restart (przydatne przy zawieszeniach):

```bash
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald
```

Potem `journalctl -b -1` pokaże wpisy sprzed ostatniego restartu. Wynik `get_throttled` inny niż `0x0` najczęściej oznacza za słaby zasilacz.

## 7. Wygodne logowanie przez SSH (klucze) {#ssh}

Na komputerze (macOS, Linux, Windows 10/11 – Terminal lub PowerShell):

```bash
ssh-keygen -t ed25519            # Enter, Enter (hasło klucza opcjonalne)
ssh-copy-id pi@192.168.1.10      # raz wpisujesz hasło do Pi
ssh-copy-id pi@192.168.1.20
```

Na Windowsie zamiast `ssh-copy-id`:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@192.168.1.10 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Skróty – plik `~/.ssh/config` na komputerze:

```
Host plex
    HostName 192.168.1.10
    User pi
Host zero
    HostName 192.168.1.20
    User pi
```

Od teraz wystarczy `ssh plex` albo `ssh zero`. Polecenie przerywasz **Ctrl+C**, sesję kończysz `exit`.

## 8. Bezpieczeństwo w sieci domowej {#security}

- **Nie przekierowuj portu 8800** (ani 32400 bez potrzeby) na routerze i nie ustawiaj Raspberry Pi w strefie DMZ – panel jest przeznaczony do sieci domowej.
- Do dostępu spoza domu użyj **VPN**: `./fix.sh` → 7 → **Tailscale** (zalecany, bez otwierania portów) albo WireGuard.
- Ustaw **mocne hasła**: do panelu, do konta na Raspberry Pi i do Samby. Najlepiej loguj się kluczami SSH ([rozdział 7](#ssh)).
- W Sambie używaj `valid users` – nie udostępniaj folderów gościom.
- Aktualizuj system: `sudo apt update && sudo apt full-upgrade`, a Plex Downloader – `./update.sh`.
- Klucz TMDB i hasła są zapisane tylko lokalnie (`config.json`, `~/.smbcredentials`) – nie wysyłaj tych plików nikomu.
