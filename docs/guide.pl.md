# Domowy serwer filmów i seriali — instrukcja krok po kroku {#top}

Kompletny przewodnik od czystej karty SD i nowego dysku ze sklepu aż po gotową bibliotekę Plex z wygodnym panelem pobierania w przeglądarce. {.lead}

**Spis treści — kolejność działania** {.toc-title}

| Etap | Zakres prac |
|---|---|
| Wstęp | Jak to działa, trzy sposoby instalacji, wymagania i 4 zasady pracy z terminalem |
| Etap 0 | Przygotowanie karty SD (Raspberry Pi Imager) i pierwsze uruchomienie |
| Etap 1 | Połączenie z Raspberry Pi (SSH) i logowanie bez hasła |
| Etap 2 | Przygotowanie dysku na bibliotekę (nowy ze sklepu, z danymi z Windows/Mac, montowanie na stałe) |
| Etap 3 | Instalacja Plex Downloadera, Plex Media Server i kreator konfiguracji |
| Etap 4 | Dwa urządzenia (Plex na jednym Pi, Downloader na drugim) |
| Etap 5 | Codzienna praca w panelu (pobieranie, gdzie obejrzeć, menedżer plików, edycja i plakaty) |
| Etap 6 | Dostęp z telefonu i komputera poza domem (VPN Tailscale) |
| Etap 7 | Aktualizacje, diagnostyka, narzędzie naprawcze fix.sh i bezpieczeństwo |
| Dodatki | Gdy coś nie działa (FAQ) i słowniczek pojęć |

## Wstęp: jak to działa i co będzie potrzebne {#intro data-stage="WSTĘP"}

Zestaw składa się z dwóch współpracujących programów uruchomionych na Raspberry Pi:

- **Plex Media Server** — Twoje domowe centrum rozrywki. Kataloguje filmy i seriale, pobiera opisy i plakaty, odtwarza wideo na telewizorze, telefonie i komputerze.
- **Plex Downloader** — panel otwierany w zwykłej przeglądarce. Pobiera pliki wideo z bezpośrednich linków (wiele połączeń naraz, wznawianie po restarcie), sam nadaje im nazwy zgodne z wymaganiami Plexa (np. `Tytuł (Rok)/Tytuł (Rok).mkv` albo `Serial/Season 01/Serial S01E02.mkv`) i pozwala zarządzać plikami oraz plakatami.

### Trzy sposoby instalacji {#scenarios}

| Sposób instalacji | Dla kogo | Charakterystyka |
|---|---|---|
| **1. Dyski zewnętrzne** (zalecany) | Plex i Downloader na jednym Raspberry Pi, filmy na dysku SSD/HDD lub pendrivie | Najszybszy, najprostszy i najbardziej niezawodny wariant. |
| **2. Karta SD** (niezalecany) | Szybki test bez podłączania dysku | Karta ma małą pojemność, jest wolna i szybko się zużywa przy zapisie dużych plików. |
| **3. Dwa urządzenia** | Plex na mocniejszym Pi, Downloader na osobnym (np. Pi Zero 2 W) | Biblioteka współdzielona przez sieć (SMB); pobieranie wolniejsze przez podwójny ruch w sieci. |

Te same trzy warianty zobaczysz później w kreatorze konfiguracji, w kroku **Instalacja**.

**Wymagania:** Raspberry Pi (zalecane Pi 4 lub Pi 5; Pi Zero 2 W wystarczy do wariantu 3), karta microSD min. 16 GB, połączenie z routerem (najlepiej kablem) i **oryginalny zasilacz**. Zbyt słaby zasilacz albo ładowarka od telefonu to najczęstsza przyczyna zawieszania się Raspberry Pi i błędów zapisu na dysku USB.

> [!INFO] **Zanim wpiszesz pierwszą komendę — 4 zasady pracy z terminalem**
>
> 1. **Nazwa użytkownika (`pi`):** w całym poradniku zakładamy, że Twoje konto na Raspberry Pi nazywa się `pi`. Jeśli przy przygotowaniu karty (Etap 0) wpisałeś inną nazwę, np. `janek`, wpisuj ją wszędzie tam, gdzie w przykładach widzisz `pi`.
> 2. **Niewidzialne hasło:** gdy terminal prosi o hasło (`password:`), wpisujesz je „na ślepo” — na ekranie nie pojawiają się kropki ani gwiazdki. Wpisz hasło i naciśnij **Enter**.
> 3. **Wklejanie komend:** w niektórych terminalach **Ctrl+V** nie działa. Na Macu użyj **Cmd+V**, w Windows kliknij **prawym przyciskiem myszy** w oknie terminala (albo Ctrl+V w nowym Terminalu Windows), w Linuksie **Ctrl+Shift+V**. Komendy wklejaj **całymi blokami** — każda linia to osobne polecenie (linia zakończona `\` ciągnie się w następnej). Najwygodniej kopiować z poradnika w panelu (**Ustawienia → Konto → Instrukcja (HTML / PDF)**): każdy blok ma tam przycisk **Kopiuj**.
> 4. **Zapisywanie w edytorze `nano`:** po tekście poruszasz się strzałkami. Zapis i wyjście: **Ctrl+O** (litera O), **Enter**, potem **Ctrl+X**.

## Przygotowanie karty SD i pierwsze uruchomienie {#sd-card data-stage="ETAP 0"}

Raspberry Pi nie ma dysku systemowego — system działa z karty microSD. Kartę przygotowujesz na swoim komputerze darmowym programem **Raspberry Pi Imager**.

**Krok 1:** pobierz i zainstaluj Raspberry Pi Imager ze strony **raspberrypi.com/software** (Windows, macOS, Linux). Włóż kartę microSD do komputera (przez czytnik albo przejściówkę).

**Krok 2:** w programie wybierz kolejno:

| Pole w Imagerze | Co wybrać |
|---|---|
| Urządzenie (Device) | Twój model, np. Raspberry Pi 4 |
| System (OS) | **Raspberry Pi OS Lite (64-bit)** — wersja bez pulpitu, najlżejsza. Dla najstarszego Pi Zero W (pierwsza generacja) wybierz wersję **32-bit**. |
| Nośnik (Storage) | Twoja karta microSD — sprawdź pojemność, żeby nie wybrać innego dysku! |

**Krok 3: ustawienia (najważniejszy krok).** Gdy Imager zapyta, czy zastosować własne ustawienia (*Customisation / Edytuj ustawienia*), wybierz **tak** i uzupełnij:

| Ustawienie | Co wpisać | Po co |
|---|---|---|
| Nazwa hosta (hostname) | `raspberrypi` | Pod tą nazwą znajdziesz Pi w sieci (`raspberrypi.local`). |
| Nazwa użytkownika i hasło | `pi` + Twoje hasło | Tymi danymi zalogujesz się przez SSH. Zapisz je! |
| Wi-Fi (opcjonalnie) | nazwa sieci, hasło, kraj **PL** | Tylko jeśli Pi nie będzie podłączone kablem. |
| Strefa czasowa i klawiatura | `Europe/Warsaw`, `pl` | Poprawne godziny w logach. |
| Usługi → **SSH** | **Włącz** (logowanie hasłem) | **Bez tego nie połączysz się z Pi w Etapie 1.** |

**Krok 4:** zapisz kartę (*Write / Zapisz*) i poczekaj na weryfikację. Włóż kartę do Raspberry Pi, podłącz kabel sieciowy (jeśli używasz) i na końcu **zasilacz**. Pierwsze uruchomienie trwa 2–3 minuty (system powiększa się na całą kartę) — dioda zielona przestaje intensywnie migać, gdy skończy.

> [!TIP] **Stały adres IP.** W panelu routera znajdź listę podłączonych urządzeń, odszukaj `raspberrypi` i ustaw dla niego **rezerwację adresu DHCP** (opcja bywa nazwana *Rezerwacja adresu*, *Address Reservation* lub *Static DHCP*). Dzięki temu adres panelu nie zmieni się po zaniku prądu. W przykładach używamy adresu `192.168.1.10`.

## Połączenie z Raspberry Pi przez SSH {#ssh data-stage="ETAP 1"}

Zamiast podłączać monitor i klawiaturę do Raspberry Pi, sterujesz nim zdalnie z własnego komputera przez bezpieczne połączenie tekstowe **SSH**. Wszystkie komendy z tego poradnika wpisujesz właśnie w takim połączeniu.

### 1.1. Pierwsze logowanie {#ssh-first}

Otwórz na swoim komputerze program **Terminal** (macOS: Cmd+Spacja → wpisz „Terminal”; Linux) albo **PowerShell** (Windows 10/11: menu Start → wpisz „PowerShell”) i wpisz:

```bash
ssh pi@raspberrypi.local
```

Jeśli komputer nie znajdzie nazwy `raspberrypi.local`, użyj adresu IP z listy urządzeń w panelu routera:

```bash
ssh pi@192.168.1.10
```

Przy pierwszym połączeniu pojawi się pytanie `Are you sure you want to continue connecting (yes/no)?` — wpisz pełne słowo `yes` i naciśnij **Enter**. Następnie podaj hasło ustawione w Etapie 0. Gdy zobaczysz znak zachęty `pi@raspberrypi:~ $`, jesteś zalogowany. Adres IP sprawdzisz w każdej chwili poleceniem `hostname -I`.

### 1.2. Wygodne logowanie bez hasła (klucze SSH) {#ssh-keys}

Podczas konfiguracji połączysz się z Raspberry Pi wiele razy. Klucze SSH sprawiają, że zalogujesz się krótką komendą `ssh plex`, bez adresu i hasła. **Poniższe polecenia wykonaj na swoim komputerze** (nie na Raspberry Pi — jeśli jesteś zalogowany na Pi, wpisz `exit`).

**Krok 1: wygeneruj parę kluczy** (Windows, macOS, Linux):

```bash
ssh-keygen -t ed25519
```

Naciśnij **Enter** trzy razy — zaakceptujesz domyślne miejsce pliku i brak dodatkowego hasła do klucza. Jeśli program zapyta `Overwrite (y/n)?`, masz już klucz — wpisz `n` i przejdź do kroku 2.

**Krok 2A: wyślij klucz na Raspberry Pi — macOS i Linux:**

```bash
ssh-copy-id pi@192.168.1.10
```

**Krok 2B: wyślij klucz na Raspberry Pi — Windows (PowerShell):**

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@192.168.1.10 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

W obu przypadkach podajesz hasło do Raspberry Pi ostatni raz.

**Krok 3: krótki skrót `ssh plex` (opcjonalnie, bardzo wygodne).** Otwórz plik konfiguracyjny SSH na swoim komputerze — macOS/Linux: `nano ~/.ssh/config`, Windows (PowerShell): `notepad $env:USERPROFILE\.ssh\config` (zgódź się na utworzenie pliku) — i wpisz **trzy linie**:

```text
Host plex
    HostName 192.168.1.10
    User pi
```

Zapisz plik. Od teraz `ssh plex` od razu otwiera konsolę Raspberry Pi.

## Przygotowanie dysku na filmy i seriale {#disk data-stage="ETAP 2"}

Zanim zainstalujesz Plexa i Downloader, przygotuj miejsce na pliki. W Linuksie dysk nie dostaje litery (jak `D:` w Windowsie) — jest „podpinany” pod wybrany folder, np. `/mnt/ssd1`. Taki folder nazywamy **punktem montowania**. Wybierz scenariusz pasujący do Twojego dysku:

| Twój dysk | Co robisz |
|---|---|
| Nowy, prosto ze sklepu (albo chcesz go wyczyścić) i będzie podłączony **tylko do Raspberry Pi** | Scenariusz A — formatowanie na `ext4` w terminalu (zalecane) |
| Nowy, ale chcesz go czasem podłączyć **do komputera** z Windows lub Mac | Scenariusz C — formatowanie na `exFAT` na komputerze |
| Masz już na nim **filmy** z Windows (NTFS) lub Maca/pendrive'a (exFAT) | Scenariusz B — bez formatowania |

Potem, w każdym scenariuszu: **2.4 montowanie na stałe** i **2.5 foldery biblioteki**.

### 2.1. Scenariusz A: nowy dysk tylko dla Raspberry Pi (ext4) {#new-disk}

Nowe dyski mają fabrycznie format dla Windowsa lub Maca. Jeśli dysk będzie pracował wyłącznie z Raspberry Pi, najlepszy jest natywny format Linuksa — **ext4**: najszybszy, nie obciąża procesora, nie ma problemów z uprawnieniami.

> [!WARN] **Uwaga: poniższe polecenia trwale kasują wszystkie dane z wybranego dysku!** Upewnij się, że wskazujesz właściwy dysk USB, a nie kartę systemową.

**Krok 1:** podłącz dysk do portu USB (najlepiej **niebieskiego USB 3.0**) i sprawdź, jak system go nazwał:

```bash
lsblk -o NAME,SIZE,MODEL,FSTYPE
```

Przykładowy wynik:

```text
NAME          SIZE MODEL              FSTYPE
sda         931.5G Samsung_SSD_T7
└─sda1      931.5G                    exfat
mmcblk0      29.7G
├─mmcblk0p1   512M                    vfat
└─mmcblk0p2  29.2G                    ext4
```

`mmcblk0` to karta systemowa — **jej nie dotykaj**. Twój dysk USB to niemal zawsze `sda` (albo `sdb`, jeśli podpięte są dwa dyski) — poznasz go po pojemności w kolumnie `SIZE` (dysk 1 TB pokazuje się jako ok. `931.5G`) i po nazwie modelu.

**Krok 2:** odmontuj dysk (system mógł go podpiąć automatycznie), utwórz nową tablicę partycji i sformatuj całość jako `ext4`. Przykład zakłada dysk `sda` — jeśli u Ciebie to `sdb`, zamień literę **we wszystkich trzech liniach**:

```bash
sudo umount /dev/sda1
sudo parted -s /dev/sda mklabel gpt mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L PLEX_DYSK /dev/sda1
```

Co robi każda linia:

- `umount /dev/sda1` — odłącza partycję, jeśli system ją zamontował (komunikat `not mounted` jest normalny — zignoruj go),
- `parted … mklabel gpt` — tworzy nową, pustą tablicę partycji GPT; `mkpart primary ext4 0% 100%` — jedna partycja na cały dysk,
- `mkfs.ext4 -L PLEX_DYSK /dev/sda1` — formatuje partycję i nadaje jej etykietę `PLEX_DYSK`.

Formatowanie dużego dysku trwa od kilku sekund do kilku minut — poczekaj, aż wróci znak zachęty `pi@raspberrypi:~ $`.

### 2.2. Scenariusz B: dysk, na którym masz już filmy (NTFS / exFAT) {#existing-disk}

Jeśli masz dysk z kolekcją filmów z komputera Windows (format `ntfs`) albo z Maca lub pendrive (format `exfat`), **nie formatuj go**. Raspberry Pi czyta i zapisuje oba formaty bez utraty danych — wystarczy odpowiedni wpis w kroku 2.4.

> [!WARN] **Dyski z Windowsa:** zanim odłączysz dysk od komputera z Windows, użyj **„Bezpieczne usuwanie sprzętu”**. Dysk wyjęty „na siłę” albo z komputera z włączonym *Szybkim uruchamianiem* Linux zamontuje **tylko do odczytu** — panel nie będzie mógł zapisywać filmów. Naprawa: podłącz dysk z powrotem do Windowsa, uruchom w nim sprawdzanie dysku (Właściwości → Narzędzia → Sprawdź) i odłącz go bezpiecznie.

### 2.3. Scenariusz C: formatowanie na komputerze (bez terminala, exFAT) {#format-gui}

Jeśli wolisz okienka albo dysk ma czasem trafiać do komputera, sformatuj go na **exFAT** — ten format czytają Windows, macOS i Raspberry Pi. Wszystkie dane z dysku zostaną usunięte.

**Windows 10/11:**

1. Podłącz dysk, otwórz **Eksplorator plików** → **Ten komputer**.
2. Kliknij dysk **prawym przyciskiem** → **Formatuj…**
3. System plików: **exFAT**, rozmiar jednostki alokacji: **domyślny**, etykieta woluminu: np. `PLEX_DYSK`, zaznacz **Szybkie formatowanie** → **Rozpocznij**.

**macOS:**

1. Podłącz dysk i otwórz **Narzędzie dyskowe** (Cmd+Spacja → wpisz „Narzędzie dyskowe”; albo Finder → Programy → Narzędzia).
2. W menu **Widok** wybierz **Pokaż wszystkie urządzenia** — bez tego zobaczysz tylko partycję, a nie cały dysk.
3. Na liście po lewej zaznacz **cały dysk** (najwyższą pozycję z nazwą producenta), kliknij **Wymaż**.
4. Nazwa: np. `PLEX_DYSK`, Format: **ExFAT**, Schemat: **Mapa partycji GUID** → **Wymaż**.

Potem podłącz dysk do Raspberry Pi i przejdź do kroku 2.4 (wariant 3 — exFAT).

### 2.4. Montowanie dysku na stałe (plik /etc/fstab) {#fstab}

Bez wpisu w pliku `/etc/fstab` Raspberry Pi po każdym restarcie „zapomni” o dysku, a Plex pokaże brak plików.

**Krok 1: odczytaj identyfikator partycji (UUID) i jej format (FSTYPE):**

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID
```

Znajdź swoją partycję (np. `sda1`) i skopiuj ciąg z kolumny `UUID` — dla dysku ext4 wygląda np. tak: `a1b2c3d4-e5f6-7890-1234-567890abcdef`, dla NTFS/exFAT jest krótszy, np. `4A8C-19F2`. Zapamiętaj wpis z kolumny `FSTYPE` (`ext4`, `ntfs` albo `exfat`).

**Krok 2: utwórz folder — punkt montowania:**

```bash
sudo mkdir -p /mnt/ssd1
```

**Krok 3: dopisz dysk do pliku /etc/fstab.** Otwórz plik w edytorze:

```bash
sudo nano /etc/fstab
```

Zejdź strzałkami **na sam dół** pliku (pod istniejące linie — **nie zmieniaj ich**) i wklej **tylko jedną** z poniższych linii, pasującą do `FSTYPE` Twojego dysku. Zamień `TWÓJ_UUID` na kod z kroku 1.

**Wariant 1 — dysk Linux (FSTYPE = `ext4`):**

```text
UUID=TWÓJ_UUID  /mnt/ssd1  ext4  defaults,nofail  0  2
```

**Wariant 2 — dysk z Windowsa (FSTYPE = `ntfs`):**

```text
UUID=TWÓJ_UUID  /mnt/ssd1  ntfs3  defaults,nofail,uid=pi,gid=pi,umask=002  0  0
```

**Wariant 3 — dysk z Maca lub pendrive (FSTYPE = `exfat`):**

```text
UUID=TWÓJ_UUID  /mnt/ssd1  exfat  defaults,nofail,uid=pi,gid=pi,umask=002  0  0
```

Zapisz plik: **Ctrl+O**, **Enter**, **Ctrl+X**.

**Co oznaczają kolejne pola linii:**

| Pole | Przykład | Znaczenie |
|---|---|---|
| 1. co montujemy | `UUID=…` | Konkretna partycja rozpoznana po identyfikatorze — działa nawet po przełożeniu kabla do innego gniazda USB. |
| 2. gdzie | `/mnt/ssd1` | Punkt montowania z kroku 2. |
| 3. format | `ext4` / `ntfs3` / `exfat` | Sterownik systemu plików (dla NTFS sterownik nazywa się `ntfs3`). |
| 4. opcje | `defaults,nofail` | `defaults` — standardowe ustawienia; **`nofail`** — jeśli dysk będzie odłączony, Raspberry Pi i tak normalnie się uruchomi (bez tego zatrzyma się na ekranie awaryjnym!). |
| | `uid=pi,gid=pi,umask=002` | Tylko NTFS/exFAT: te formaty nie znają uprawnień Linuksa, więc wszystkie pliki „należą” do użytkownika `pi`; `umask=002` — inni (np. Plex) mogą czytać. |
| 5. kopia (dump) | `0` | Stare narzędzie kopii — zawsze 0. |
| 6. sprawdzanie | `2` / `0` | `2` — sprawdzaj dysk ext4 przy starcie; `0` — nie sprawdzaj (NTFS/exFAT). |

**Krok 4: sprawdź montowanie bez restartu:**

```bash
sudo systemctl daemon-reload
sudo mount -a
df -h /mnt/ssd1
```

Jeśli nie pojawił się błąd, a w tabeli widzisz pojemność dysku zamontowanego w `/mnt/ssd1` — działa.

**Krok 5: test prawdziwy — restart:**

```bash
sudo reboot
```

Po minucie zaloguj się ponownie (`ssh plex` albo `ssh pi@192.168.1.10`) i wpisz `df -h /mnt/ssd1` — dysk powinien być na miejscu bez żadnych komend.

> [!TIP] **Najczęstsze błędy przy `mount -a`:**
>
> - `unknown filesystem type 'ntfs3'` — starszy system bez sterownika `ntfs3`. Zainstaluj alternatywny sterownik `sudo apt install -y ntfs-3g` i w swojej linii fstab zamień `ntfs3` na `ntfs-3g`.
> - `unknown filesystem type 'exfat'` — zainstaluj obsługę exFAT: `sudo apt install -y exfat-fuse exfatprogs`.
> - `wrong fs type, bad option` — zwykle literówka w linii fstab (sprawdź przecinki i brak spacji w opcjach) albo wybrałeś wariant niepasujący do `FSTYPE`.
> - Dysk NTFS montuje się tylko do odczytu — patrz ostrzeżenie w scenariuszu B.

### 2.5. Foldery biblioteki i uprawnienia {#folders}

Plex działa w systemie jako osobny użytkownik `plex` (musi móc **czytać** filmy), a Plex Downloader działa jako Ty — `pi` (musi móc **zapisywać i usuwać**). Utwórz foldery biblioteki i nadaj prawa:

```bash
mkdir -p "/mnt/ssd1/Plex/Movies" "/mnt/ssd1/Plex/TV Shows" "/mnt/ssd1/Plex/Kids"
sudo chown -R pi:pi /mnt/ssd1/Plex
sudo chmod -R 755 /mnt/ssd1/Plex
```

- `mkdir -p` — tworzy foldery (cudzysłów jest potrzebny, bo nazwa `TV Shows` ma spację),
- `chown -R pi:pi` — właścicielem folderów zostaje użytkownik `pi`,
- `chmod -R 755` — właściciel może wszystko, pozostali (w tym Plex) mogą czytać.

> [!INFO] Na dyskach **NTFS/exFAT** komendy `chown` i `chmod` mogą zgłosić błąd albo nic nie zmienić — to normalne, uprawnienia ustawiły już opcje `uid=pi,gid=pi,umask=002` z pliku fstab. Pierwszą linię (`mkdir`) wykonaj zawsze.

### Wariant testowy: biblioteka na karcie SD {#plex-sd}

**Niezalecany na co dzień.** Karta SD jest mała, wolniejsza od dysku i szybciej się zużywa. Gdy zapełni się całkowicie, cały system może przestać działać — zostaw na niej zawsze kilka GB wolnego miejsca. Foldery tworzysz wtedy w katalogu domowym:

```bash
mkdir -p ~/Plex/Movies "$HOME/Plex/TV Shows" ~/Plex/Kids
chmod o+x ~
```

Druga linia pozwala Plexowi „przejść” przez Twój katalog domowy do folderu `Plex` (bez prawa do oglądania innych plików). W kreatorze wybierzesz wariant **„Biblioteka na karcie SD”**.

## Instalacja Plex Downloadera i Plex Media Server {#install data-stage="ETAP 3"}

Mając przygotowany dysk, instalujesz najpierw Plex Downloader. Zawiera on menu naprawcze `fix.sh`, które jednym wyborem zainstaluje też serwer Plex.

### 3.1. Instalacja Plex Downloadera {#downloader-install}

W konsoli Raspberry Pi wklej cały blok:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd ~/plex-downloader
chmod +x setup.sh update.sh fix.sh
./setup.sh
```

- `apt install -y git` — program do pobierania kodu z GitHuba (w Raspberry Pi OS Lite nie ma go fabrycznie),
- `git clone …` — pobiera Plex Downloader do folderu `~/plex-downloader`,
- `chmod +x` — pozwala uruchamiać skrypty,
- `./setup.sh` — instalator (uruchamiasz go **bez** `sudo` — sam poprosi o hasło, gdy będzie potrzebne).

Instalator przeprowadzi Cię przez 5 kroków:

1. **Zapyta o język** — wpisz `2` (polski) i naciśnij **Enter**.
2. **Zainstaluje narzędzia systemowe** (`aria2`, Python, `ffmpeg`). Na Pi Zero może to potrwać 5–15 minut — **nie przerywaj, nawet jeśli przez dłuższą chwilę na ekranie nic się nie zmienia**.
3. **Przygotuje środowisko Pythona.** Przy słabym Wi-Fi komunikaty `Retrying…` są normalne. Gdyby instalacja przerwała się z braku sieci, **wklej polecenie** (całe, razem z przejściem do folderu programu):

   ```bash
   cd ~/plex-downloader && ./setup.sh
   ```

   **Instalacja ruszy ponownie — nie stracisz postępu:** to, co już zostało zainstalowane, zostaje, a instalator dokończy resztę.
4. **Poprosi o utworzenie konta administratora panelu** — podaj **nową** nazwę użytkownika i **nowe hasło** do panelu w przeglądarce (hasło min. 6 znaków, wpisujesz je dwa razy). To konto tylko do panelu — nie musi być takie samo jak login do Raspberry Pi. Sam **Enter** przy nazwie użytkownika przyjmie podpowiedź `admin`. **Pamiętaj:** hasło wpisujesz „na ślepo” — **na ekranie nie pojawiają się żadne kropki ani gwiazdki**. Zapisz je.
5. **Uruchomi usługę w tle i wyświetli adres panelu**, np. `http://192.168.1.10:8800` — zwróć uwagę na port **8800** (nie 8080). Ten adres wpiszesz w przeglądarce w kroku 3.3.

### 3.2. Instalacja Plex Media Server {#plex-install}

**Metoda zalecana — menu `fix.sh`:**

```bash
cd ~/plex-downloader && ./fix.sh
```

W menu wybierz **7 Moduły dodatkowe → Plex Media Server → Zainstaluj**. Skrypt sam doda oficjalne repozytorium Plexa, zainstaluje serwer i poda jego adres.

**Metoda alternatywna — ręcznie (cały blok):**

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

**Pierwsza konfiguracja Plexa (w przeglądarce na komputerze):**

1. Otwórz `http://192.168.1.10:32400/web` (adres Twojego Raspberry Pi + port **32400** + `/web`).
2. Zaloguj się na konto Plex albo załóż je za darmo (e-mail, Google lub Apple). Plex Pass (płatny) **nie jest potrzebny**.
3. Nadaj serwerowi nazwę, np. `Plex w domu`, i przejdź dalej.
4. Kliknij **Dodaj bibliotekę** i dla każdej biblioteki wybierz typ, nazwę i folder (**Przeglądaj w poszukiwaniu folderu** → wskaż folder → **Dodaj**):

| Typ biblioteki | Nazwa (dowolna) | Folder |
|---|---|---|
| Filmy | Filmy | `/mnt/ssd1/Plex/Movies` |
| Programy TV | Seriale | `/mnt/ssd1/Plex/TV Shows` |
| Filmy | Dla dzieci | `/mnt/ssd1/Plex/Kids` |

5. Kliknij **Dodaj bibliotekę** — Plex zacznie skanować foldery. Puste foldery to nic złego: filmy pojawią się po pierwszym pobraniu.

### 3.3. Pierwsze uruchomienie panelu i kreator konfiguracji {#wizard}

Otwórz w przeglądarce `http://192.168.1.10:8800` i zaloguj się **nazwą i hasłem administratora panelu**, które ustaliłeś w kroku 3.1 (punkt 4) — nie hasłem do Raspberry Pi ani do Plexa. Przy pierwszym uruchomieniu otworzy się **kreator konfiguracji** (później uruchomisz go ponownie w **Ustawienia → Konto → Uruchom kreator**). Każdy krok ma link „Instrukcja instalacji ↗” do właściwego rozdziału tego poradnika.

1. **Język** i **Motyw** — wybierz wygląd panelu. Jeśli przenosisz konfigurację z innego urządzenia, kliknij **Mam plik ustawień – wczytaj** i wskaż zapisany plik JSON.
2. **Instalacja** — wybierz **Dyski zewnętrzne**, **Karta SD (niezalecane)** albo **Plex na innym urządzeniu** (patrz Trzy sposoby instalacji).
3. **Dyski i foldery** {#wizard-disks} — kreator skanuje zamontowane dyski (czyta wyłącznie **nazwy** folderów, nigdy zawartość plików) i sam przypisuje foldery takie jak `Movies`, `Filmy`, `TV Shows`, `Seriale`, `Kids` czy `Bajki`. Nietypowe foldery obok biblioteki (np. `Movies02`) pojawią się jako przyciski **+ Movies02** — kliknięcie doda je jako nową kategorię. Brakujący folder możesz utworzyć żółtym przyciskiem **Utwórz** albo opcją **Utwórz brakujące foldery przy zakończeniu** (domyślnie wyłączona).
4. **Serwer Plex** — serwery w domowej sieci wykrywane są automatycznie. Adres podajesz ręcznie tylko wtedy, gdy serwer jest w innej podsieci albo za VPN.
5. **Klucz TMDB** {#tmdb} (opcjonalny, darmowy) — pozwala pobierać plakaty, oceny i opisy filmów. Jak go zdobyć — krok po kroku w ramce pod tą listą. Wklej **API Key** albo **API Read Access Token** — kreator od razu sprawdzi jego poprawność. Opcję **Samodzielnie generuj miniatury z kadrów filmu** zostaw na początek wyłączoną: na Raspberry Pi trwa to kilkanaście sekund na film, a pojedynczy kadr zawsze wybierzesz ręcznie w oknie edycji.
6. **Podsumowanie → Zakończ** — zapisuje ustawienia i tworzy punkt przywracania.

> [!INFO] **Darmowy klucz TMDB — krok po kroku** {#tmdb-key}
>
> 1. Wejdź na **themoviedb.org** i kliknij **Dołącz do TMDB** (*Join TMDB*). Podaj nazwę użytkownika, hasło i e-mail, potem kliknij link w e-mailu potwierdzającym.
> 2. Zaloguj się, kliknij **swój awatar** (prawy górny róg) → **Ustawienia** (*Settings*) → w menu po lewej **API**.
> 3. Kliknij **Utwórz** / *Create* (albo „Click here to request an API key”), wybierz typ **Developer** i zaakceptuj warunki.
> 4. Wypełnij krótki formularz: rodzaj użycia **osobisty** (*Personal*), nazwa aplikacji np. `Plex Downloader`, adres URL np. `http://localhost`, krótki opis np. „domowy serwer filmów”. Dane adresowe są wymagane przez formularz.
> 5. Po zatwierdzeniu zobaczysz **Klucz API** (*API Key*, 32 znaki) i dłuższy **API Read Access Token** — skopiuj **jeden z nich** i wklej w kreatorze albo w **Ustawienia → Podgląd i plakaty**.
>
> Klucz jest prywatny — nie udostępniaj go nikomu.

## Konfiguracja na dwa urządzenia (opcjonalnie) {#two-devices data-stage="ETAP 4"}

Ten etap dotyczy sytuacji, gdy masz dwa urządzenia: np. **Pi 4 z dyskami i Plexem** (`192.168.1.10`) oraz **Pi Zero 2 W z Plex Downloaderem** (`192.168.1.20`), który zapisuje pobrane pliki na dysk pierwszego przez sieć domową.

> [!INFO] W tym układzie pobieranie jest wolniejsze — każdy megabajt przechodzi przez sieć dwa razy (z internetu do Pi Zero, a potem przez Wi-Fi do Pi z Plexem).

**Krok 1 (router):** przypisz obu Raspberry Pi stałe adresy IP (rezerwacja DHCP — patrz Etap 0).

### 4.1. Na Pi z Plexem: udostępnienie dysku (Samba) {#samba}

Zainstaluj serwer plików Samba: `cd ~/plex-downloader && ./fix.sh` → **7 Moduły dodatkowe → Samba → Zainstaluj** (albo `sudo apt install -y samba`). Otwórz plik konfiguracyjny:

```bash
sudo nano /etc/samba/smb.conf
```

Zejdź na sam koniec pliku i dopisz sekcję (każde ustawienie w osobnej linii):

```ini
[Plex SSD1]
   path = /mnt/ssd1/Plex
   valid users = pi
   read only = no
   force user = pi
```

- `[Plex SSD1]` — nazwa udziału widoczna w sieci,
- `path` — folder, który udostępniasz,
- `valid users = pi` — dostęp tylko dla użytkownika znającego hasło (biblioteka nie jest dostępna dla gości),
- `read only = no` — można zapisywać,
- `force user = pi` — pliki zapisane przez sieć należą do `pi`.

Zapisz plik (**Ctrl+O**, **Enter**, **Ctrl+X**), ustaw hasło sieciowe Samby i zrestartuj usługę:

```bash
sudo smbpasswd -a pi
sudo systemctl restart smbd
```

`smbpasswd` zapyta dwa razy o nowe hasło Samby (może być inne niż hasło logowania do Pi — zapamiętaj je).

### 4.2. Na Pi z Downloaderem: podpięcie udziału {#cifs}

Zainstaluj obsługę udziałów sieciowych i utwórz punkt montowania (albo `cd ~/plex-downloader && ./fix.sh` → **7 → Klient SMB – montowanie udziałów (cifs-utils)**):

```bash
sudo apt update
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/ssd1
```

Utwórz plik z hasłem do udziału:

```bash
nano ~/.smbcredentials
```

Wpisz **dwie linie** (z hasłem ustawionym przed chwilą w `smbpasswd`):

```text
username=pi
password=TWOJE_HASLO_SAMBY
```

Zapisz plik i zabezpiecz go tak, by nikt inny w systemie nie mógł go odczytać:

```bash
chmod 600 ~/.smbcredentials
```

> [!WARN] Hasło wpisuj **bezpośrednio w edytorze `nano`**. Jeśli hasło zawiera np. ukośnik `\`, polecenia typu `echo` zniekształcą je i montowanie skończy się błędem `Permission denied`.

Dopisz udział na stałe do `/etc/fstab` na Pi z Downloaderem (`sudo nano /etc/fstab`). **To jest jedna linia** — w poradniku może się zawijać, ale w pliku musi być w jednym wierszu. Spację w nazwie udziału `Plex SSD1` zapisujemy jako `\040`:

```text
//192.168.1.10/Plex\040SSD1  /mnt/ssd1  cifs  credentials=/home/pi/.smbcredentials,uid=pi,gid=pi,iocharset=utf8,vers=3.0,_netdev,nofail  0  0
```

| Element | Znaczenie |
|---|---|
| `//192.168.1.10/Plex\040SSD1` | Adres Pi z Plexem i nazwa udziału |
| `/mnt/ssd1` | Gdzie udział będzie widoczny na Pi z Downloaderem |
| `credentials=…` | Plik z loginem i hasłem (krok wyżej) |
| `uid=pi,gid=pi` | Pliki należą do `pi` — Downloader może je zapisywać |
| `iocharset=utf8` | Polskie znaki w nazwach plików |
| `vers=3.0` | Wersja protokołu SMB |
| `_netdev,nofail` | Montuj po starcie sieci; brak udziału nie blokuje uruchomienia |

Zapisz i sprawdź:

```bash
sudo systemctl daemon-reload
sudo mount -a
df -h /mnt/ssd1
```

### 4.3. Ścieżki w kreatorze {#paths}

Uruchom kreator w panelu Downloadera i wybierz **Plex na innym urządzeniu**. **Złota zasada:** w Plex Downloaderze wpisujesz zawsze ścieżki **tego urządzenia, na którym działa panel**. W naszym przykładzie udział jest zamontowany w `/mnt/ssd1`, więc filmy to `/mnt/ssd1/Movies`. W Plexie nic nie zmieniasz.

| | Pi z Plexem | Pi z Downloaderem |
|---|---|---|
| Punkt montowania | `/mnt/ssd1` (dysk) | `/mnt/ssd1` (udział sieciowy) |
| Folder filmów | `/mnt/ssd1/Plex/Movies` | `/mnt/ssd1/Movies` |

Jeśli przeniosłeś ustawienia (plik JSON) z drugiego urządzenia i ścieżki pokazują „Folder nie istnieje”, użyj **Ustawienia → Dyski → Aktualizuj ścieżki**.

### 4.4. Ta sama kategoria, różne nazwy folderów {#folder-names}

Kategoria to tylko przycisk w panelu — każdy dysk ma dla niej własny folder. Np. kategoria **Koncerty**: na jednym dysku `Concerts`, na drugim `Live`. Wpisz właściwą ścieżkę przy każdym dysku (albo kliknij żółte **Utwórz** przy pustym polu), a w Plexie dodaj **oba foldery do tej samej biblioteki** (biblioteka → Edytuj → Dodaj foldery).

## Codzienna praca z panelem {#downloader data-stage="ETAP 5"}

### Pobieranie filmów i seriali {#download}

Wklej **bezpośredni link do pliku wideo** w pole **Dodaj nowe pobieranie**. Bezpośredni link to adres, który od razu pobiera plik — zwykle kończy się na `.mkv`, `.mp4` albo `.avi` (np. link do pobrania z serwisu z plikami). Linki do stron z odtwarzaczem (YouTube, Netflix itp.) **nie zadziałają**. Panel sam rozpozna tytuł, rok, sezon i numer odcinka (każde pole możesz poprawić przed startem), pokaże kartę z opisem z TMDB i wolne miejsce na dyskach. Wybierz dysk i kategorię, kliknij **Pobierz plik**. Plik pobiera się najpierw do ukrytego folderu roboczego i dopiero po 100% trafia jednym ruchem do biblioteki — dzięki temu Plex nie próbuje odtwarzać niedokończonego pliku.

**Opcje zaawansowane:**

- **Wydanie** (np. `{edition-Director's Cut}`, do 3 tagów) — odróżnia w Plexie wersję reżyserską od kinowej (wyświetlanie wydań wymaga Plex Pass),
- **Wersja pliku** (np. `1080p`, `4K`) — kilka wersji jakościowych tego samego filmu w jednym folderze,
- **TMDB ID** (np. `{tmdb-19995}`) — wymusza w Plexie dokładne dopasowanie, przydatne przy filmach o identycznych tytułach.

### Gdzie obejrzeć — dostępność w serwisach streamingowych {#where-to-watch}

Zanim coś pobierzesz, sprawdź, czy film nie jest już w Twoim serwisie streamingowym. **Wpisz sam tytuł** w pole nazwy (np. `Milczenie owiec (1991)`) — link nie jest potrzebny. Po chwili karta podglądu pokaże w sekcji **Gdzie obejrzeć** logo serwisów w czterech grupach:

| Grupa | Znaczenie |
|---|---|
| **Abonament** | Film jest w ramach subskrypcji (np. Netflix, Prime Video) — bez dodatkowej opłaty, jeśli masz ten serwis. |
| **Za darmo** | Bezpłatnie, czasem z reklamami. |
| **Wypożyczenie** | Jednorazowa opłata za obejrzenie w określonym czasie. |
| **Kupno** | Film zostaje na Twoim koncie w danym serwisie. |

Kliknięcie logo otwiera stronę z ofertami dla tego tytułu. **Kraj** ustawiasz w **Ustawienia → Konto → Gdzie obejrzeć – kraj** (*Automatycznie* = według języka panelu: polski → Polska, angielski → USA). Dane pochodzą z TMDB, dostępność z JustWatch. Do tej funkcji potrzebny jest klucz TMDB (Etap 3).

### Menedżer plików {#file-manager}

Dwie kolumny z plakatami — porządkujesz kolekcję metodą „przeciągnij i upuść” albo przyciskiem **Przenieś**:

- **Ten sam dysk** (np. między kategoriami) — przeniesienie natychmiastowe.
- **Inny dysk** — kopia → weryfikacja sumy kontrolnej **SHA-256** (gwarancja, że plik nie uległ uszkodzeniu) → dopiero wtedy usunięcie oryginału. Opcja **Pomiń weryfikację SHA-256 po przeniesieniu** wyraźnie przyspiesza operację (porównywane są tylko rozmiary plików) — przydatna dla plików, które łatwo pobierzesz ponownie.
- **Seriale** przeniesiesz w całości, wybranym sezonem albo wybranymi odcinkami. Odcinki trafiają do folderu serialu na dysku docelowym — jeśli już tam jest, dołączają do niego (z zachowaniem folderów `Season XX`).
- Kolejność dysków zmienisz, przeciągając kafelki; **zębatka** na kafelku zmienia wyświetlaną nazwę dysku.

### Edycja nazw, dodatków i plakatów {#edit}

Ikona **długopisu** na kafelku (nad koszem) otwiera okno edycji:

- **tytuł, rok, TMDB ID** (przycisk **Szukaj w TMDB**), **wydanie** i **pliki w folderze**,
- każdy plik ma **rodzaj**: *Film (wersja)* albo dodatek Plexa — *Zwiastun, Za kulisami, Scena usunięta, Wywiad, Inny dodatek*. Dodatek dostaje nazwę typu `Opis-trailer.mp4`, dzięki czemu Plex pokaże go w sekcji Dodatki, a nie jako duplikat filmu,
- sama zmiana plakatu nie zmienia nazw plików; przy zmianie nazw przycisk **Zmień** pokazuje listę zmian i pyta o potwierdzenie.

**Plakaty:** **Własny obrazek…** (JPG, PNG, WebP), **Kadr z filmu** (6 kadrów do wyboru; **Generuj inne** losuje nowe; **Wskaż czas** pokazuje kadry wokół podanego momentu `g:mm:ss`, a **+10 s** przesuwa go o 10 sekund) albo **pobierz plakat z TMDB**. Ręcznie wybrane plakaty nie są nadpisywane przy zbiorczym odświeżaniu.

### Kopie zapasowe i dziennik aktywności {#backups}

- **Punkty przywracania:** po każdej zmianie ustawień panel tworzy kopię przechowywaną 30 dni (**Ustawienia → Kopie zapasowe**); najnowsza jest zawsze zachowana.
- **Eksport / import JSON:** **Eksportuj ustawienia** zapisuje dyski, kategorie, serwery i opcje (bez loginu, hasła i kluczy sesji; klucz TMDB tylko na życzenie). **Importuj ustawienia…** pokazuje, co się zmieni, i pozwala wybrać sekcje. Sekcja dysków jest zaznaczona tylko wtedy, gdy dyski z pliku są podłączone w tym urządzeniu — po przeniesieniu na inne urządzenie użyj **Ustawienia → Dyski → Aktualizuj ścieżki**.
- **Dziennik aktywności:** **Ustawienia → Konto → LOG** — historia pobrań, przeniesień, zmian nazw i usunięć, z przyciskami **Wyczyść** i **Eksportuj .log**.

## Bezpieczny dostęp spoza domu (VPN Tailscale) {#vpn data-stage="ETAP 6"}

Panelu **nie wystawiaj** do internetu przez przekierowanie portów na routerze. Aby dodawać filmy z telefonu w sieci komórkowej, z pracy czy z hotelu, połącz swoje urządzenia prywatną, szyfrowaną siecią **Tailscale** (darmowy plan do użytku domowego, logowanie kontem Google, Apple, Microsoft lub GitHub — zawsze na stronie Tailscale; panel nigdy nie widzi tego logowania).

### 6.1. Instalacja Tailscale na Raspberry Pi {#vpn-install}

1. W terminalu uruchom menu naprawcze: `cd ~/plex-downloader && ./fix.sh`
2. Wybierz **7 Moduły dodatkowe → Tailscale VPN (zalecany) → Zainstaluj**. Skrypt zainstaluje Tailscale i pozwoli panelowi samodzielnie logować się do Tailscale.
3. Pytanie o logowanie na końcu możesz pominąć — wygodniej zalogujesz się z przeglądarki.

> [!TIP] **Błędy `404 Not Found` lub `File has unexpected size`** przy instalacji (np. pakietu `iptables`) oznaczają awarię serwera lustrzanego Raspbiana, nie Tailscale. `fix.sh` zaproponuje wtedy pobieranie z głównego archiwum — wybierz **Tak**. Jeśli Tailscale był zainstalowany wcześniej inaczej, wybierz w tym samym menu **Zaktualizuj** — panel dostanie uprawnienie do logowania.

### 6.2. Logowanie i telefon {#vpn-login}

1. W domu otwórz panel → **Ustawienia → VPN** → **Zaloguj**.
2. Pojawi się link i kod QR. Otwórz link na komputerze albo zeskanuj kod telefonem, zaloguj się i zatwierdź dodanie Raspberry Pi. Po kilku sekundach zakładka pokaże **Połączono z Tailscale**, a plakietka **VPN** w nagłówku zrobi się zielona.
3. **Ważne:** w konsoli **login.tailscale.com/admin** → **Machines** → menu **…** przy Raspberry Pi → **Disable key expiry**. Inaczej Tailscale co ok. 180 dni poprosi o ponowne zalogowanie Raspberry Pi.
4. Zainstaluj aplikację **Tailscale** na telefonie (App Store / Google Play) lub komputerze i zaloguj się na **to samo konto**. W zakładce VPN, w sekcji **Otwórz panel przez VPN**, zeskanuj kod QR i dodaj stronę do ekranu początkowego telefonu.

Adres Raspberry Pi w VPN (np. `100.x.y.z` i nazwa `raspberrypi.tail1234.ts.net`) jest **stały**. Poza domem włączasz Tailscale w aplikacji i otwierasz zapisany skrót; w domu VPN nie jest potrzebny.

### 6.3. Certyfikat HTTPS (kłódka w przeglądarce) {#vpn-https}

Ruch w Tailscale jest zawsze szyfrowany, ale przy adresie `http://` przeglądarka pokazuje „Niezabezpieczona”. W **Ustawienia → VPN** kliknij **Włącz HTTPS** (za pierwszym razem pojawi się **Zezwól na HTTPS w Tailscale** — zatwierdź certyfikaty na swoim koncie i kliknij Włącz HTTPS ponownie). Panel będzie dostępny pod adresem `https://raspberrypi.tail1234.ts.net`, bez numeru portu. Pierwsze otwarcie trwa kilkanaście sekund (pobieranie certyfikatu).

> [!WARN] Nie włączaj **Tailscale Funnel** — wystawia stronę dla całego internetu, a nie tylko dla Twoich urządzeń. Panel nigdy go nie włącza i ostrzeże na czerwono, gdyby był włączony.

### 6.4. Kontrola dostępu, autostart i WireGuard {#vpn-access}

- **Gdzie dostępny jest panel:** **Sieć domowa + VPN** (domyślnie) albo **Tylko sieć domowa** — wtedy panel przez VPN jest zablokowany, a Tailscale działa dalej np. dla SSH i Plexa. Z powrotem przełączysz tylko z domu.
- **Wersja Tailscale** ma znaczek **aktualna** / **nieaktualna** (czerwony **pilna aktualizacja** = poprawka bezpieczeństwa). Aktualizacja: `fix.sh` → 7 → Tailscale → **Zaktualizuj**.
- **Wyloguj / zmień konto** — Raspberry Pi opuszcza sieć Tailscale; potem **Zaloguj** daje nowy link.
- **Autostart:** `cd ~/plex-downloader && ./fix.sh` → 7 → Tailscale → **Autostart: włączony → wyłącz** (nie wystartuje po restarcie). Rozłączenie na chwilę: `sudo tailscale down`, z powrotem: `sudo tailscale up` albo **Połącz** w panelu.
- **WireGuard** — dla osób z własnym serwerem WireGuard (wymaga przekierowania portu UDP 51820 na routerze i ręcznej konfiguracji `/etc/wireguard/wg0.conf`). Narzędzia: `cd ~/plex-downloader && ./fix.sh` → 7 → **WireGuard VPN**. Zakładka VPN pokazuje aktywne połączenia i adresy.

> [!INFO] Obsługę WireGuard sprawdzono wyłącznie w **testach syntetycznych** (symulowane polecenia systemowe, bez prawdziwego połączenia). Jeśli u Ciebie coś działa inaczej, zgłoś to na GitHubie (Issues).

## Aktualizacje, diagnostyka i ratunek (fix.sh) {#maintenance data-stage="ETAP 7"}

### Aktualizacja Plex Downloadera {#update}

Gdy w nagłówku okna **Ustawienia** pojawi się informacja o nowej wersji, zaloguj się przez SSH i uruchom aktualizację (filmy i ustawienia są bezpieczne):

```bash
cd ~/plex-downloader && ./update.sh
```

### Menu naprawcze fix.sh {#fix}

W razie problemów z panelem lub usługami dodatkowymi uruchom:

```bash
cd ~/plex-downloader && ./fix.sh
```

| Opcja w menu | Do czego służy |
|---|---|
| 1 Aktualizacja | Najnowsza wersja panelu (jak `./update.sh`). |
| 2 Reinstalacja | Odbudowuje środowisko Pythona i pliki programu; **zachowuje ustawienia**. |
| 3 Czysta reinstalacja | Ustawienia fabryczne panelu (wymaga wpisania `TAK`). Filmy na dysku nie są ruszane. |
| 4 / 5 Wersja BETA | Przejście na wersję testową lub powrót do stabilnej. |
| 6 Serwer | Status, uruchomienie, zatrzymanie, restart panelu. |
| 7 Moduły dodatkowe | Plex Media Server, Samba, klient SMB, ffmpeg, Tailscale, WireGuard: instalacja, aktualizacja, autostart wł./wył., odinstalowanie. |
| 8 Zainstaluj inną wersję | Powrót do starszego wydania (od 1.2.5) z automatyczną kopią ustawień w `.version-snapshots`. |
| 9 Odinstaluj | Usuwa usługę i pliki Plex Downloadera (filmy zostają nietknięte). |

### Diagnostyka Raspberry Pi (zasilanie, temperatura, dyski) {#diagnostics}

Jeśli Raspberry Pi działa wolno, gubi dysk USB albo zawiesza się przy pobieraniu, wpisz po kolei:

```bash
vcgencmd get_throttled
vcgencmd measure_temp
df -h
free -h
uptime
```

| Polecenie | Co pokazuje | Dobry wynik |
|---|---|---|
| `vcgencmd get_throttled` | Problemy z zasilaniem i przegrzewaniem | `throttled=0x0` — każda inna wartość: **za słaby zasilacz** lub przegrzanie |
| `vcgencmd measure_temp` | Temperatura procesora | poniżej ok. 70 °C (od 80 °C procesor zwalnia) |
| `df -h` | Wolne miejsce na karcie (`/`) i dyskach (`/mnt/ssd1`) | karta: kilka GB wolnego |
| `free -h` | Zużycie pamięci RAM | kolumna `available` większa niż kilkadziesiąt MB |
| `uptime` | Czas pracy od uruchomienia | długi — krótki oznacza niezauważony restart |

**Błędy z ostatniego uruchomienia:**

```bash
journalctl -u plex-downloader -n 50 --no-pager
dmesg -T | grep -iE "voltage|mmc|i/o error|cifs" | tail
```

Pierwsza linia: ostatnie 50 wpisów dziennika Plex Downloadera. Druga: błędy zasilania (`voltage`), karty SD (`mmc`), dysków USB (`i/o error`) i udziałów sieciowych (`cifs`).

**Logi zachowywane po restarcie.** Domyślnie Raspberry Pi OS często trzyma dziennik tylko w pamięci RAM — po zawieszeniu i restarcie nie widać, co się stało. Włącz zapis na kartę (działa w każdej wersji systemu):

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=persistent\n' \
  | sudo tee /etc/systemd/journald.conf.d/99-persistent.conf
sudo systemctl restart systemd-journald
```

Po kolejnym restarcie `journalctl -b -1` pokaże zdarzenia z chwili tuż przed awarią.

### Bezpieczeństwo w sieci domowej — checklista {#security}

- Nie przekierowuj na routerze portu `8800` (ani `32400` bez wyraźnej potrzeby) i nie umieszczaj Raspberry Pi w strefie DMZ — z zewnątrz używaj wyłącznie VPN (Etap 6).
- Silne hasła do panelu, konta systemowego i Samby; do terminala loguj się kluczami SSH (Etap 1).
- Regularnie aktualizuj system: `sudo apt update && sudo apt full-upgrade -y`.
- Pliki `config.json` (klucz TMDB) i `~/.smbcredentials` (hasło Samby) zawierają poufne dane — nigdy ich nie udostępniaj.

## Gdy coś nie działa — najczęstsze problemy {#faq data-stage="FAQ"}

| Objaw | Co sprawdzić |
|---|---|
| Panel się nie otwiera (`http://…:8800`) | Czy Raspberry Pi jest włączone i ma ten sam adres (`hostname -I`)? Stan usługi: `cd ~/plex-downloader && ./fix.sh` → **6 Serwer**. Dziennik: `journalctl -u plex-downloader -n 50 --no-pager`. |
| Nie mogę się połączyć przez SSH | Czy SSH było włączone w Raspberry Pi Imager (Etap 0)? Czy adres IP się nie zmienił? Spróbuj `ssh pi@raspberrypi.local`. |
| Po restarcie nie ma dysku | Czy linia w `/etc/fstab` ma `nofail` i poprawny UUID? Sprawdź `lsblk -o NAME,FSTYPE,UUID` i `sudo mount -a`. |
| Plex nie widzi nowego filmu | W Plexie: biblioteka → menu **…** → **Skanuj pliki biblioteki**. Sprawdź, czy film leży w folderze przypisanym do tej biblioteki. |
| Dysk tylko do odczytu (NTFS) | Dysk był odłączony od Windowsa bez „Bezpiecznego usuwania” — patrz Etap 2, scenariusz B. |
| Pobieranie stoi albo Pi się zawiesza | `vcgencmd get_throttled` — wynik inny niż `0x0` to prawie zawsze zasilacz. Wolne miejsce: `df -h`. |
| „Folder nie istnieje” w ustawieniach dysków | Dysk niepodłączony albo ścieżka z innego urządzenia — **Ustawienia → Dyski → Aktualizuj ścieżki**. |

## Słowniczek pojęć {#glossary data-stage="SŁOWNIK"}

| Pojęcie | Wyjaśnienie |
|---|---|
| **Terminal / konsola** | Okno, w którym wpisujesz polecenia tekstowe zamiast klikać. |
| **SSH** | Bezpieczne połączenie z innym komputerem przez sieć — terminal Raspberry Pi otwarty na Twoim komputerze. |
| **sudo** | Dopisek przed poleceniem: „wykonaj jako administrator”. Zapyta o hasło. |
| **Punkt montowania** | Folder (np. `/mnt/ssd1`), pod którym widać zawartość dysku — odpowiednik litery `D:` w Windowsie. |
| **UUID** | Unikalny identyfikator partycji dysku — po nim system rozpoznaje dysk w każdym gnieździe USB. |
| **fstab** | Plik `/etc/fstab` z listą dysków montowanych automatycznie przy starcie. |
| **ext4 / NTFS / exFAT** | Formaty dysku: Linux / Windows / uniwersalny (Windows, Mac, Linux). |
| **Samba (SMB)** | Udostępnianie folderów w sieci domowej (jak „udostępniony folder” w Windowsie). |
| **VPN (Tailscale)** | Prywatna, szyfrowana sieć Twoich urządzeń — dostęp do domu z dowolnego miejsca bez otwierania portów. |
| **TMDB** | The Movie Database — darmowa baza filmów, z której pochodzą plakaty i opisy. |
