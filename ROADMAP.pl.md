# Plex Downloader – plan rozwoju (To-Do)

🇬🇧 [English](ROADMAP.md) · 🇵🇱 **Polski** · Historia zmian: [CHANGELOG.md](CHANGELOG.md)

Ostatnia aktualizacja: 11 listopada 2026 · stabilna: **1.3.0** · BETA: **1.4.0-beta2**

## Stałe zasady (sprawdzać przy każdej wersji)

- **Języki:** angielski domyślny (także README, CHANGELOG i ten plan – z wersją polską obok), polski w `locales/pl.json`. Każdy nowy tekst w interfejsie od razu dostaje tłumaczenie.
- **Opisy:** w interfejsie tylko krótkie etykiety. Dłuższe wyjaśnienia trafiają do podpowiedzi ⓘ (chmurki).
- **Skrypty:** `setup.sh` i `fix.sh` zaczynają od wyboru języka (1 English domyślny, 2 Polski). `update.sh` jest tylko po angielsku.
- **Bezpieczeństwo danych:** żaden skrypt ani funkcja nie usuwa filmów ani seriali bez wyraźnego potwierdzenia w panelu. Przywrócenie kopii ustawień nie zmienia loginu ani hasła.
- **Trzy scenariusze instalacji** (każdą nową funkcję, kreator i instrukcję sprawdzać pod każdym z nich):
  1. **Zalecany:** Plex i Downloader na jednym Pi, biblioteka na dyskach zewnętrznych (SSD, pendrive).
  2. **Testowy (niezalecany):** jedno Pi bez dysków, biblioteka na karcie SD, opcjonalnie udostępniona przez SMB.
  3. **Dwa urządzenia:** Plex na jednym komputerze, Downloader z Menedżerem plików na drugim, oba ze stałym IP. Biblioteka jest dostępna dla obu, np. jako udział sieciowy SMB lub NFS zamontowany na stałe.
- **Numeracja w 1.3:** kroki BETA to `1.3.0-beta1`, `-beta2`… aż do stabilnej 1.3.0; potem wraca zwykła reguła (BETA dwa oczka przed stabilną).
- **Dwie linie wydań:** stabilna w gałęzi `main` (setup.sh, update.sh, panel ogłasza tylko ją) i BETA w gałęzi `beta` (tylko przez `fix.sh`). Nowe funkcje trafiają najpierw do BETA, po sprawdzeniu do stabilnej. Każde wydanie dostaje tag `vX.Y.Z` (BETA: `vX.Y.Z-beta`). Numeracja: BETA jest o dwa oczka przed stabilną (np. stabilna 1.2.6 → BETA 1.2.8-beta).
- **Przed wydaniem:** testy automatyczne, zrzuty ekranu w wersjach EN/PL i w motywie ciemnym/jasnym, aktualizacja README i tego pliku.

## Wydane wersje

| Wersja | Najważniejsze zmiany |
|---|---|
| 1.0.0 | Pobieranie z bezpośrednich linków (aria2c, 6 połączeń), nazewnictwo Plex, 3 dyski, wznawianie po restarcie, logowanie, usługa systemd |
| 1.1.0 | Karta podglądu filmu i serialu z TMDB (plakat, ocena, obsada, linki IMDb/Filmweb) |
| 1.2.0 | Menedżer plików (2 kolumny, przeciąganie, kopia z weryfikacją SHA-256), kategorie, edycje i wersje Plex, status serwerów Plex, kopie ustawień, okno Ustawień, przyciski Google/YouTube |
| 1.2.1 | Język EN/PL, motyw ciemny i jasny, dziennik aktywności, przenoszenie sezonów i odcinków, „Aktualizuj ścieżki”, komendy terminala, `fix.sh` |
| 1.2.2 | Usuwanie zaznaczonych kopii ustawień, zwijane komendy, poprawka podpowiedzi |
| 1.2.5 (stabilna) | 1.2.2 bez zapowiedzi VPN; podział na wersje stabilne i BETA, sprawdzanie aktualizacji tylko dla stabilnej, nowe menu `fix.sh` |
| 1.2.6-beta | 1.2.2 z zapowiedziami VPN i tym samym podziałem wersji |
| 1.2.6 (stabilna) | Postęp przenoszenia w dwóch etapach, „Pomiń weryfikację SHA-256”, ukryty klucz TMDB, poprawki wyglądu (telefon, ⓘ), neutralny adres w komendzie `ssh`, test tłumaczeń, dokumentacja po angielsku |
| 1.2.8-beta | 1.2.6 + zapowiedzi VPN; baza do prac nad 1.3 |
| 1.2.7 (stabilna) | Optymalizacja rozpoznawania tytułów na podstawie wklejonego linka; ostrzeżenie, gdy link otwiera stronę WWW zamiast pliku |
| 1.2.9-beta | 1.2.7 + zapowiedzi VPN, `fix.sh` w oknie z podmenu Serwer |
| 1.3.0-beta1 | Kreator konfiguracji (trzy sposoby instalacji, wykrywanie dysków i folderów, komendy do udziału sieciowego) |
| 1.3.0-beta2 | Eksport i import ustawień z podglądem zmian, szablon dysku „Karta SD (niezalecane)” |
| 1.3.0-beta3 | Instrukcje EN/PL (w aplikacji + PDF); Menedżer plików: edycja nazwy Plex, rodzaje plików (wersje / dodatki) i plakaty (własny obrazek, kadr z filmu, TMDB); `fix.sh` Moduły dodatkowe; poprawki kreatora po testach na Pi Zero |
| 1.3.0-beta4 | `fix.sh` → Zainstaluj inną wersję; kreator startuje też po przełączeniu świeżej instalacji stabilnej na BETA |
| 1.3.0 (stabilna) | Wszystko z 1.3.0-beta1…beta4 bez zapowiedzi VPN: kreator, eksport / import ustawień, edycja nazw i plakatów (własny obrazek, kadr z filmu, TMDB), dodatki Plexa, instrukcje EN/PL, `fix.sh` Moduły dodatkowe i Zainstaluj inną wersję |
| 1.4.0-beta0 | 1.3.0 + zapowiedź VPN; baza dla 1.4 (bez nowych funkcji) |
| 1.4.0-beta1 | Działająca zakładka VPN (status Tailscale, adres, kod QR, logowanie z panelu, urządzenia) i plakietka VPN w nagłówku |
| 1.4.0-beta2 | HTTPS w VPN, tylko sieć domowa / + VPN, wylogowanie / zmiana konta, status WireGuard; `fix.sh` autostart wł./wył. i główne archiwum Raspbiana |

## Do poprawy

Wszystkie poprawki z poprzedniej listy weszły do 1.2.6 / 1.2.8-beta (szczegóły w [CHANGELOG.md](CHANGELOG.md)). Zostało:
- [x] **Tagi wersji na GitHubie:** tagi `v1.2.5` … `v1.4.0-beta0` są na GitHubie; wydania opublikowane dla 1.3.0 (stabilna) i 1.4.0-beta0 (pre-release).

## Strona demo (Netlify)

- [x] Demo (najpierw 1.2.5, potem 1.2.6, teraz **1.3.0**): prawdziwy interfejs z symulacją w przeglądarce, EN/PL, okno powitalne, dane max 24 h, wylogowanie czyści wszystko, linki zewnętrzne zablokowane, zmyślone nazwy, IP i klucze, generowane okładki.
- [x] Opublikowane pod https://plexdownloader.netlify.app, link w README.
- [ ] Źródła demo (`demo.js`, skrypt budujący) w repozytorium, w folderze `demo/`, żeby po każdym wydaniu stabilnym dało się je odświeżyć jednym poleceniem.
- [x] Od 1.3: link do instrukcji w oknie powitalnym prowadzi do instrukcji EN/PL (HTML i PDF).

## 1.3 – kreator pierwszego uruchomienia, instrukcje, wybór wersji

**Kreator pierwszego uruchomienia**
- [x] Kolejne kroki: język → motyw → sposób instalacji → dyski i foldery → serwer Plex → klucz TMDB (opcjonalny) → podsumowanie (konto tworzy `setup.sh`).
- [x] Wybór sposobu instalacji (odpowiada trzem scenariuszom):
  - [x] „Dyski zewnętrzne (zalecane)”: skanowanie podłączonych dysków (`lsblk`/`df`), propozycja folderów `Movies`, `TV Shows`, `Kids`.
  - [x] „Biblioteka na karcie SD (niezalecana)”: punkt montowania `/`, foldery w `~/Plex/…` tworzone automatycznie, ostrzeżenie o pojemności, zużyciu karty i prędkości (w ⓘ).
  - [x] „Plex na innym urządzeniu”: adres IP serwera Plex, sprawdzenie połączenia, wskazanie zamontowanego udziału sieciowego, test zapisu. Uwaga w ⓘ, że Plex i Downloader muszą widzieć te same pliki (ścieżki mogą się różnić).
- [x] Sprawdzenie uprawnień do zapisu i wolnego miejsca na każdym folderze.
- [x] Tworzenie brakujących folderów na żądanie.
- [x] W każdym kroku linki do instrukcji: rozdział dla danego kroku otwiera się w nowym oknie (HTML, z pobieraniem PDF).
- [x] Ponowne uruchomienie kreatora z Ustawień.

**Ustawienia**
- [x] Eksport i import ustawień (plik JSON, bez hasła; przy imporcie podgląd zmian).
- [x] Gotowy szablon „Biblioteka na karcie SD (niezalecana)” w zakładce Dyski.

**Instrukcje (EN i PL, HTML w aplikacji + PDF)**
- [x] Instalacja serwera Plex na Raspberry Pi, w tym:
  - [x] wariant z dyskami zewnętrznymi (fstab, uprawnienia),
  - [x] wariant testowy z biblioteką na karcie SD (niezalecany): tworzenie folderu, udostępnienie przez SMB, ograniczenia.
- [x] Instalacja Plex Downloadera (`setup.sh`, pierwsze logowanie, kreator).
- [x] Konfiguracja na dwóch urządzeniach: stałe IP, udział SMB/NFS montowany w fstab, ręczne dodanie serwera Plex w Ustawieniach.
  - [x] Przykład (już w README): jeden dysk, dwie ścieżki (`/media/ssd1` na Pi z Plexem, `/mnt/ssd1` na Pi z Downloaderem), „Aktualizuj ścieżki” po imporcie, jedna kategoria z różnymi nazwami folderów na dwóch dyskach (`Concerts` / `Live`) i oba foldery w jednej bibliotece Plex, hasło ze znakiem `\` w `.smbcredentials`.
- [x] Obsługa: Menedżer plików, kopie ustawień, dziennik, `update.sh`, `fix.sh`, przywracanie ustawień fabrycznych.
- [x] Bezpieczeństwo sieci domowej (bez DMZ i przekierowania portu 8800, mocne hasła, Samba z `valid users`).

**Kolejne kroki wydań**
- [x] `1.3.0-beta1`: kreator pierwszego uruchomienia (podmenu serwera w `fix.sh` weszło już do 1.2.9-beta).
- [x] `1.3.0-beta2`: eksport i import ustawień, szablon „Karta SD”.
- [x] `1.3.0-beta3`: instrukcje EN/PL (HTML w aplikacji + PDF).
  - [x] Menedżer plików: edycja nazwy i plakatu (ikona długopisu na kafelku).
  - [x] Plakaty z kadrów filmu (ffmpeg): w oknie edycji i automatycznie (Ustawienia / kreator, domyślnie wyłączone).
  - [x] `fix.sh` → Moduły dodatkowe: Plex Media Server, Samba, klient SMB, ffmpeg, Tailscale, WireGuard (status, instalacja, aktualizacja, zatrzymaj / uruchom, restart, odinstalowanie).
- [x] `1.3.0-beta4`: „Zainstaluj inną wersję” w `fix.sh`; kreator startuje też po przełączeniu świeżej instalacji stabilnej na BETA.
- [x] `1.3.0`: wydanie stabilne.

**`fix.sh` – podmenu serwera**
- [x] Nowa opcja „Serwer” (w 1.2.9-beta): 1) sprawdź status (stan usługi, autostart, adres panelu, ostatnie wpisy logu), 2) wstrzymaj serwer – bez wpływu na autostart / uruchom ponownie (zależnie od stanu), 3) restart procesu serwera, 4) powrót.
- [x] Wygląd menu: okno `whiptail` w stylu `raspi-config` z tymi samymi numerami, zapasowe menu tekstowe (`--text`).

**Wybór wersji w `fix.sh` (zmiana sposobu wydawania w repozytorium)**
- [x] Linie stabilna (`main`) i BETA (`beta`), instalacja i wyjście z BETA w `fix.sh` (od 1.2.5 / 1.2.6-beta).
- [x] Każde wydanie od **1.2.5** ma tag git `vX.Y.Z`; od 1.3.0 każde dostaje też wydanie na GitHubie z listą zmian.
- [x] Plik `CHANGELOG.md` z historią wersji (od 1.2.6).
- [x] Nowa opcja 8 w `fix.sh`: „Zainstaluj inną wersję” – lista stabilnych wersji od 1.2.5 z krótkim opisem (`releases.txt`, działa bez tagów); kopia `config.json` i kopii zapasowych do `.version-snapshots`, przełączenie kodu, odbudowa środowiska i restart usługi.
- [x] Panel i `update.sh` wiedzą, że zainstalowana jest wersja przypięta (starsza). Dostępny jest powrót do najnowszej. (nagłówek `fix.sh` pokazuje „starsza wersja”, panel informuje o najnowszej stabilnej, `update.sh` / opcja 1 wracają).
- [x] Zgodność ustawień: nowsze wersje migrują `config.json` automatycznie, starsze zachowują nieznane klucze; przy cofnięciu ustawienia zostają, a kopia sprzed zmiany jest w `.version-snapshots`.

## 1.4 – dostęp zdalny przez VPN

Kolejne kroki: `1.4.0-beta0` (= 1.3.0 + zapowiedź VPN, gotowe) → `1.4.0-beta1` (działająca zakładka VPN, gotowe) → `1.4.0-beta2` (HTTPS, tylko sieć domowa / + VPN, status WireGuard, gotowe) → `1.4.0-beta3` (instrukcja) → `1.4.0`.

Zapowiedzi VPN (zakładka i przycisk w nagłówku) są widoczne tylko w BETA; w wersji stabilnej wrócą razem z działającą funkcją.

- [x] Instalacja Tailscale z linkiem do logowania (oraz WireGuard): `fix.sh` → Moduły dodatkowe (1.3.0-beta3, zamiast osobnego `setup-vpn.sh`).
- [x] Zakładka VPN: status i adres Tailscale, kod QR dla telefonu, logowanie z panelu, urządzenia w VPN, plakietka w nagłówku (1.4.0-beta1).
- [x] HTTPS w VPN z certyfikatem Tailscale (1.4.0-beta2).
- [x] Wybór „tylko sieć domowa” lub „sieć domowa + VPN”; status WireGuard; `fix.sh`: autostart wł./wył., główne archiwum Raspbiana przy awarii serwerów lustrzanych; wylogowanie / zmiana konta (1.4.0-beta2).
- [ ] Panel bez otwartych portów na routerze.
- [ ] Instrukcja EN/PL (Tailscale na Pi, telefonie i komputerze).

## 1.5 – dodawanie plików z komputera i z pendrive'a

Status: **jeszcze nie zrobione** (omawiane wcześniej, zaplanowane na tę wersję).
- [ ] Przeciągnięcie pliku z komputera do okna przeglądarki: wysyłanie w częściach ze wznawianiem, pasek postępu, wybór dysku i kategorii, nazwa zgodna z Plex.
- [ ] Wysyłanie kilku plików naraz (np. cały sezon z napisami).
- [ ] Import z pendrive'a podłączonego do Pi: wykrycie, lista plików, kopiowanie z weryfikacją SHA-256 do wybranej kategorii.
- [ ] Sprawdzenie wolnego miejsca przed wysłaniem.

## Pomysły do decyzji (bez przypisanej wersji)

Propozycje Claude, które warto rozważyć, ale nie zostały jeszcze zatwierdzone:
- [ ] Automatyczne odświeżenie biblioteki Plex po pobraniu lub przeniesieniu (wymaga tokenu Plex).
- [ ] Powiadomienie o zakończonym pobieraniu (np. Telegram lub e-mail).
- [ ] Harmonogram pobierania (np. tylko w nocy) i limit prędkości zależny od pory dnia.
- [ ] Stan dysków (SMART, temperatura) w zakładce Dyski.
- [ ] Wyszukiwanie i pobieranie napisów (np. OpenSubtitles).
