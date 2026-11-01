# Plex Downloader

Lekki menedżer pobierania dla Raspberry Pi. Wklejasz bezpośredni link do pliku wideo, wybierasz dysk, a aplikacja pobiera go wielowątkowo (aria2c) i zapisuje w strukturze, którą Plex od razu rozpoznaje.

- **Filmy:** `…/Movies/Tytuł (YYYY)/Tytuł (YYYY).mkv`
- **Seriale:** `…/TV Shows/Serial/Season 01/Serial - S01E02.mkv`

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

## Domyślne dyski (`config.example.json`)

| Przycisk | Filmy | Seriale |
|---|---|---|
| Pendrive 256GB | `/plex_media/Plex/Movies` | `/plex_media/Plex/TV Shows` |
| Dysk SSD 512GB | `/plex_media_512/Plex 512/Movies` | `/plex_media_512/Plex 512/TV Shows` |
| Dysk SSD 1024GB | `/plex_media_1024/Plex 1T/Movies` | `/plex_media_1024/Plex 1T/TV Shows` |

Ścieżki zmienisz w **Ustawieniach** albo w `config.json`.

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
| `naming.py` | rozpoznawanie tytułu, roku i odcinka; nazewnictwo Plexa |
| `config.py` | odczyt i zapis `config.json` |
| `templates/`, `static/` | interfejs |
| `setup.sh`, `update.sh` | instalacja i aktualizacja |

`config.json` (hasło, klucze) i `plexdl.db` (lista pobrań) nie trafiają do repozytorium (`.gitignore`).

## Bezpieczeństwo

Aplikacja jest przeznaczona do sieci domowej. Nie wystawiaj portu 8800 do internetu. Do zdalnego dostępu użyj VPN, np. Tailscale lub WireGuard.
