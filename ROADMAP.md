# Plex Downloader – plan rozwoju (To-Do)

Ostatnia aktualizacja: 2 listopada 2026 · bieżąca wersja: **1.2.2**

## Stałe zasady (sprawdzać przy każdej wersji)

- **Języki:** angielski domyślny, polski w `locales/pl.json`. Każdy nowy tekst w interfejsie od razu dostaje tłumaczenie.
- **Opisy:** w interfejsie tylko krótkie etykiety. Dłuższe wyjaśnienia trafiają do podpowiedzi ⓘ (chmurki).
- **Skrypty:** `setup.sh` i `fix.sh` zaczynają od wyboru języka (1 English domyślny, 2 Polski). `update.sh` jest tylko po angielsku.
- **Bezpieczeństwo danych:** żaden skrypt ani funkcja nie usuwa filmów ani seriali bez wyraźnego potwierdzenia w panelu. Przywrócenie kopii ustawień nie zmienia loginu ani hasła.
- **Trzy scenariusze instalacji** (każdą nową funkcję, kreator i instrukcję sprawdzać pod każdym z nich):
  1. **Zalecany:** Plex i Downloader na jednym Pi, biblioteka na dyskach zewnętrznych (SSD, pendrive).
  2. **Testowy (niezalecany):** jedno Pi bez dysków, biblioteka na karcie SD, opcjonalnie udostępniona przez SMB.
  3. **Dwa urządzenia:** Plex na jednym komputerze, Downloader z Menedżerem plików na drugim, oba ze stałym IP. Biblioteka jest dostępna dla obu, np. jako udział sieciowy SMB lub NFS zamontowany na stałe.
- **Przed wydaniem:** testy automatyczne, zrzuty ekranu w wersjach EN/PL i w motywie ciemnym/jasnym, aktualizacja README i tego pliku.

## Wydane wersje

| Wersja | Najważniejsze zmiany |
|---|---|
| 1.0.0 | Pobieranie z bezpośrednich linków (aria2c, 6 połączeń), nazewnictwo Plex, 3 dyski, wznawianie po restarcie, logowanie, usługa systemd |
| 1.1.0 | Karta podglądu filmu i serialu z TMDB (plakat, ocena, obsada, linki IMDb/Filmweb) |
| 1.2.0 | Menedżer plików (2 kolumny, przeciąganie, kopia z weryfikacją SHA-256), kategorie, edycje i wersje Plex, status serwerów Plex, kopie ustawień, okno Ustawień, przyciski Google/YouTube |
| 1.2.1 | Język EN/PL, motyw ciemny i jasny, dziennik aktywności, przenoszenie sezonów i odcinków, „Aktualizuj ścieżki”, komendy terminala, `fix.sh` |
| 1.2.2 | Usuwanie zaznaczonych kopii ustawień, zwijane komendy, poprawka podpowiedzi |

## 1.3 – kreator pierwszego uruchomienia, instrukcje, wybór wersji

**Kreator pierwszego uruchomienia**
- [ ] Kolejne kroki: język → motyw → konto → sposób instalacji → dyski i foldery → serwer Plex → klucz TMDB (opcjonalny) → podsumowanie.
- [ ] Wybór sposobu instalacji (odpowiada trzem scenariuszom):
  - [ ] „Dyski zewnętrzne (zalecane)”: skanowanie podłączonych dysków (`lsblk`/`df`), propozycja folderów `Movies`, `TV Shows`, `Kids`.
  - [ ] „Biblioteka na karcie SD (niezalecana)”: punkt montowania `/`, foldery w `~/Plex/…` tworzone automatycznie, ostrzeżenie o pojemności, zużyciu karty i prędkości (w ⓘ).
  - [ ] „Plex na innym urządzeniu”: adres IP serwera Plex, sprawdzenie połączenia, wskazanie zamontowanego udziału sieciowego, test zapisu. Uwaga w ⓘ, że Plex i Downloader muszą widzieć te same pliki (ścieżki mogą się różnić).
- [ ] Sprawdzenie uprawnień do zapisu i wolnego miejsca na każdym folderze.
- [ ] Tworzenie brakujących folderów na żądanie.
- [ ] W każdym kroku linki do instrukcji: HTML w nowym oknie i PDF do pobrania.
- [ ] Ponowne uruchomienie kreatora z Ustawień.

**Ustawienia**
- [ ] Eksport i import ustawień (plik JSON, bez hasła; przy imporcie podgląd zmian).
- [ ] Gotowy szablon „Biblioteka na karcie SD (niezalecana)” w zakładce Dyski.

**Instrukcje (EN i PL, HTML w aplikacji + PDF)**
- [ ] Instalacja serwera Plex na Raspberry Pi, w tym:
  - [ ] wariant z dyskami zewnętrznymi (fstab, uprawnienia),
  - [ ] wariant testowy z biblioteką na karcie SD (niezalecany): tworzenie folderu, udostępnienie przez SMB, ograniczenia.
- [ ] Instalacja Plex Downloadera (`setup.sh`, pierwsze logowanie, kreator).
- [ ] Konfiguracja na dwóch urządzeniach: stałe IP, udział SMB/NFS montowany w fstab, ręczne dodanie serwera Plex w Ustawieniach.
- [ ] Obsługa: Menedżer plików, kopie ustawień, dziennik, `update.sh`, `fix.sh`, przywracanie ustawień fabrycznych.
- [ ] Bezpieczeństwo sieci domowej (bez DMZ i przekierowania portu 8800, mocne hasła, Samba z `valid users`).

**Wybór wersji w `fix.sh` (zmiana sposobu wydawania w repozytorium)**
- [ ] Od wersji bazowej (proponuję **1.2.2**) każde wydanie dostaje tag git `vX.Y.Z` i wydanie na GitHubie z listą zmian.
- [ ] Plik `CHANGELOG.md` z historią wersji.
- [ ] Nowa opcja w `fix.sh`: „Zainstaluj inną wersję”. Pokazuje listę wersji od wersji bazowej z krótkim opisem. Przed zmianą tworzy kopię `config.json`, potem przełącza kod na wybrany tag, odbudowuje środowisko i restartuje usługę.
- [ ] Panel i `update.sh` wiedzą, że zainstalowana jest wersja przypięta (starsza). Dostępny jest powrót do najnowszej.
- [ ] Zgodność ustawień: nowsze wersje migrują `config.json` automatycznie. Przy cofnięciu do starszej wersji przywracana jest kopia ustawień z tamtego okresu, jeśli istnieje. Zachowanie sprawdzić w testach.

## 1.4 – dostęp zdalny przez VPN

- [ ] Skrypt `setup-vpn.sh`: instalacja Tailscale i link do logowania.
- [ ] Zakładka VPN: wybór „tylko sieć domowa” lub „sieć domowa + VPN”, port panelu, status i adres VPN, kod QR dla telefonu.
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
