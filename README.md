# Plex Downloader

Lekki menedżer pobierania dla Raspberry Pi. Wklejasz bezpośredni link do pliku wideo, wybierasz dysk, a aplikacja pobiera go wielowątkowo (aria2c) i zapisuje w strukturze, którą Plex od razu rozpoznaje.

- **Filmy:** `…/Movies/Tytuł (YYYY)/Tytuł (YYYY).mkv`
- **Seriale:** `…/TV Shows/Serial/Season 01/Serial - S01E02.mkv`
- **Dla dzieci i własne kategorie:** `…/Kids/Tytuł (YYYY)/…`, `…/Concerts/…` itd.

## Funkcje

- Logowanie (login i hasło), sesja „zapamiętaj mnie” na 30 dni, wylogowanie.
- Automatyczne rozpoznanie nazwy, roku, sezonu i odcinka z nazwy pliku w linku, z możliwością edycji.
- Rozszerzenie wykrywane z linku lub nagłówków HTTP.
- Wybór dysku z podglądem wolnego miejsca. Dysk niezamontowany jest blokowany, więc pobieranie nie zapełni karty SD.
- Sprawdzenie przed startem, czy plik zmieści się na dysku.
- Pobieranie segmentowe, domyślnie 6 połączeń na plik (`aria2c -x6 -s6 -k1M`).
- Postęp, prędkość, czas do końca, liczba połączeń i statusy: Oczekuje, Pobieranie, Wstrzymano, Finalizowanie, Zakończono, Błąd.
- Wstrzymywanie i wznawianie. Zerwane transfery aria2 wznawia sama (HTTP Range).
- Po restarcie Pi lub usługi przerwane pobierania wznawiają się automatycznie.
- Atomowość: plik pobiera się do ukrytego folderu `.plexdl-tmp` na tym samym dysku, obok `Movies`, czyli poza biblioteką Plexa. Po zakończeniu jest przenoszony do biblioteki jedną operacją `rename`. Anulowanie lub błąd usuwa pliki tymczasowe, a folder docelowy nie zostaje utworzony.
- Ustawienia w przeglądarce: dyski (etykiety i ścieżki), liczba połączeń, równoległe pobrania, limit prędkości, zmiana hasła, sprawdzanie aktualizacji.
- **Podgląd filmu lub serialu (TMDB):** po wklejeniu linku pojawia się karta z polskim tytułem, plakatem, oceną, czasem trwania, gatunkami, reżyserem, obsadą i opisem. Dla seriali pokazuje też nazwę odcinka. Karta ma linki do IMDb, Filmwebu i TMDB oraz przycisk „Nie ten film?” z innymi trafieniami. Dane są tylko poglądowe i nic nie trafia do plików, bo Plex pobiera własne metadane.
- **Kategorie (1.2):** Filmy, Seriale, Dla dzieci oraz dowolne własne kategorie typu „film” albo „serial”. Każdy dysk ma osobny folder dla każdej kategorii, a foldery mogą mieć dowolne nazwy.
- **Opcje zaawansowane nazewnictwa Plex (1.2):** edycja `{edition-Director's Cut}` (Plex Pass), wersja pliku `- 1080p` (kilka wersji w jednym folderze) oraz ID `{tmdb-…}` dla trafnego dopasowania. Edycja jest wykrywana z nazwy pliku, np. `Directors.Cut`.
- **Menedżer plików (1.2):** dwie kolumny z okładkami. Przeciągnij i upuść, żeby przenieść filmy między folderami i dyskami. Ten sam dysk to natychmiastowe przeniesienie, inny dysk to kopia, weryfikacja SHA-256 i dopiero wtedy usunięcie oryginału. Kosz usuwa cały folder filmu po potwierdzeniu.
- **Okładki (1.2):** zapisywane w folderze filmu jako `Tytuł (Rok).thumb.png` (z TMDB). Można je pobrać ponownie, usunąć z dysku albo wyłączyć.
- **Serwery Plex w nagłówku (1.2):** automatyczne wykrywanie w sieci (GDM) i status online/offline, także dla serwerów dodanych ręcznie.
- **Kopie zapasowe ustawień (1.2):** punkt przywracania po każdej zmianie, przechowywany 30 dni (ostatni zawsze zostaje). Przywrócenie nie zmienia loginu ani hasła.
- **Pływające okno ustawień z zakładkami (1.2)** i podpowiedzi ⓘ przy opcjach.
- Przyciski **Google** i **Zwiastun (YouTube)** w karcie filmu.
- Działa na telefonie.

## Wymagania

- Raspberry Pi OS (32- lub 64-bit), Python 3.7 lub nowszy.
- Dyski zamontowane na stałe (`/etc/fstab`), z prawem zapisu dla użytkownika, który uruchamia usługę (zwykle `pi`).

## Instalacja

```bash
cd ~
git clone https://github.com/pwmeess/plex-downloader.git
cd plex-downloader
chmod +x setup.sh update.sh
./setup.sh
```

Skrypt wykonuje kolejno:

1. instaluje `aria2`, `python3-venv` i `git`,
2. tworzy środowisko `venv/` i instaluje zależności z `requirements.txt`,
3. tworzy `config.json` i pyta o login i hasło,
4. sprawdza, czy foldery bibliotek istnieją i czy można w nich zapisywać,
5. rejestruje i uruchamia usługę `plex-downloader` (autostart po restarcie).

Na koniec wyświetla adres, np. **http://192.168.1.10:8800**.

## Aktualizacja

```bash
cd ~/plex-downloader
./update.sh
```

Możesz też zrobić to ręcznie: `git pull && sudo systemctl restart plex-downloader`.
W Ustawieniach jest przycisk **Sprawdź aktualizacje**, który pokazuje, czy na GitHubie są nowe zmiany.

## Podgląd filmów: klucz TMDB

1. Załóż darmowe konto na https://www.themoviedb.org/signup.
2. Przejdź do **Ustawienia → API → Utwórz → Developer**. W formularzu wystarczy wpisać użytek prywatny.
3. Skopiuj **API Key** albo **API Read Access Token**. Działa każdy z nich.
4. W Plex Downloaderze wejdź w **Ustawienia → Podgląd filmów (TMDB)**, wklej klucz i kliknij **Zapisz**.

Klucz jest zapisywany wyłącznie lokalnie w `config.json`. Bez klucza aplikacja działa normalnie, tylko bez karty podglądu.

## Domyślne dyski (`config.example.json`)

| Przycisk | Filmy | Seriale | Dla dzieci |
|---|---|---|---|
| Pendrive 256GB | `/plex_media/Plex/Movies` | `/plex_media/Plex/TV Shows` | `/plex_media/Plex/Kids` |
| Dysk SSD 512GB | `/plex_media_512/Plex 512/Movies` | `/plex_media_512/Plex 512/TV Shows` | `/plex_media_512/Plex 512/Kids` |
| Dysk SSD 1024GB | `/plex_media_1024/Plex 1T/Movies` | `/plex_media_1024/Plex 1T/TV Shows` | `/plex_media_1024/Plex 1T/Kids` |

Aktualizacja z wersji 1.0/1.1 przenosi starą konfigurację automatycznie. Jeśli obok folderu `Movies` istnieje folder `Kids`, zostaje od razu przypisany do kategorii „Dla dzieci”.

Ścieżki zmienisz w **Ustawieniach** albo w `config.json`.

## Własne dyski (inna instalacja niż autora)

Aplikacja **nie wykrywa dysków automatycznie**. Domyślne ścieżki to konfiguracja autora, więc u Ciebie najpewniej będą inne.

1. Sprawdź, gdzie są zamontowane Twoje dyski, poleceniem `df -h`. Zobaczysz np. `/mnt/dysk1`.
2. W panelu wejdź w **Ustawienia → Dyski docelowe** i dla każdego dysku wpisz:
   - **Nazwa przycisku**, np. „SSD 1TB”,
   - **Podpis**, np. nazwę udziału SMB (opcjonalnie),
   - **Punkt montowania**, np. `/mnt/dysk1` (służy do odczytu wolnego miejsca),
   - **Folder filmów** i **Folder seriali**, czyli ścieżki z bibliotek Plexa, np. `/mnt/dysk1/Movies`.
3. Dysk dodajesz przyciskiem **+ Dodaj dysk**, a usuwasz ikoną kosza. Przycisk **Uzupełnij foldery** dopisuje brakujące ścieżki według domyślnych nazw kategorii (np. `…/Plex 1T/Kids`). Na koniec kliknij **Zapisz**.
4. Własne kategorie dodasz w zakładce **Kategorie**: nazwa przycisku, typ (film/serial) i domyślna nazwa folderu. W Plexie dodaj dla nich osobne biblioteki.

Usunięcie dysku z listy nie kasuje żadnych plików, tylko chowa przycisk.

Jeśli biblioteka leży na karcie SD (bez osobnego dysku), odznacz **„Pobieraj tylko na zamontowany dysk”**.

## Przydatne polecenia

```bash
journalctl -u plex-downloader -f               # logi na żywo
sudo systemctl restart plex-downloader         # restart
./venv/bin/python app.py --set-password        # reset loginu / hasła (potem restart)
```

## Pliki

| Plik | Rola |
|---|---|
| `app.py` | serwer WWW (Flask + waitress), logowanie, API |
| `downloader.py` | sterowanie aria2c przez JSON-RPC, kolejka, finalizacja, sprzątanie |
| `filemanager.py` | Menedżer plików: lista, przenoszenie z weryfikacją, usuwanie, okładki |
| `plexservers.py` | wykrywanie i status serwerów Plex w sieci |
| `movieinfo.py` | podgląd filmu lub serialu z TMDB (tylko do wyświetlenia) |
| `naming.py` | rozpoznawanie tytułu, roku i odcinka; nazewnictwo Plexa |
| `config.py` | odczyt i zapis `config.json`, migracja, punkty przywracania (`backups/`) |
| `templates/`, `static/` | interfejs |
| `setup.sh`, `update.sh` | instalacja i aktualizacja |

`config.json` (hasło, klucze), `backups/` i `plexdl.db` (lista pobrań) nie trafiają do repozytorium (`.gitignore`).

## Bezpieczeństwo

Aplikacja jest przeznaczona do sieci domowej. Nie wystawiaj portu 8800 do internetu. Do zdalnego dostępu użyj VPN, np. Tailscale lub WireGuard.
