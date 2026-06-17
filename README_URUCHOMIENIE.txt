FTTH BOM - paczka lokalna
=========================

1. Skopiuj caly folder aplikacji na komputer docelowy.
2. Upewnij sie, ze jest zainstalowany Python 3.11 albo 3.12.
   Przy instalacji Pythona zaznacz opcje "Add Python to PATH".
3. Uruchom jednorazowo:
   INSTALUJ_ZALEZNOSCI.bat
4. Uruchom aplikacje w tle:
   URUCHOM_APKE.bat
5. Otworz w przegladarce na tym samym komputerze:
   http://127.0.0.1:8787/
6. Zatrzymanie aplikacji:
   STOP_APKE.bat
7. Aktualizacja aplikacji z GitHuba:
   AKTUALIZUJ_APKE.bat

Aktualizacja z GitHuba
----------------------

AKTUALIZUJ_APKE.bat robi kolejno:

1. zatrzymuje aplikacje,
2. pobiera najnowsze pliki z repozytorium git,
3. ustawia lokalne pliki aplikacji zgodnie z aktualna galezia,
4. uruchamia aplikacje ponownie w tle.

Foldery inputs, outputs i data nie sa czyszczone przez aktualizacje. Pliki
GPKG/XLSX z projektami, katalogiem i BELL trzeba trzymac lokalnie w inputs.
Nie sa one wrzucane do repozytorium, zeby nie publikowac danych projektowych.

Jezeli aktualizacja pokazuje "Repository not found", to ten komputer nie ma
dostepu do repozytorium GitHub. Najprosciej ustaw repo jako publiczne w GitHub:
Settings -> General -> Danger Zone -> Change repository visibility -> Public.
Alternatywnie zaloguj Git/GitHub na komputerze klienta kontem, ktore ma dostep
do prywatnego repo.

Dostep z innego komputera w sieci LAN
-------------------------------------

URUCHOM_APKE.bat odpala aplikacje na 0.0.0.0:8787, czyli po sieci lokalnej.
Na drugim komputerze wejdz w przegladarce na:

   http://ADRES_IP_KOMPUTERA_Z_APKA:8787/

Przyklad:

   http://192.168.1.25:8787/

Adres IP komputera z apka sprawdzisz w PowerShell:

   ipconfig

Szukaj adresu IPv4 w stylu 192.168.x.x albo 10.x.x.x.

Jezeli z drugiego komputera nadal nie wchodzi, Windows Firewall prawdopodobnie
blokuje Pythona albo port 8787. Wtedy przy pierwszym starcie wybierz "Allow
access" / "Zezwalaj na dostep", albo dodaj regule zapory dla portu TCP 8787.

Wazne foldery
-------------

- inputs - tutaj musza byc pliki katalogu i BELL:
  - KATALOGI PT_03_2026.xlsx
  - STAN BIEZACY _BELL_.xlsx / STAN BIEZACY _BELL_ z polskimi znakami
- outputs - tutaj pojawia sie XLSX/PDF po analizie
- data - lokalny cache preferencji materialowych oraz plik PID aplikacji

Jak uzywac
----------

1. Uruchom apke przez URUCHOM_APKE.bat.
2. Wrzuc plik GPKG przez formularz.
3. Aplikacja pokaze procentowy status analizy.
4. Po analizie kliknij Pobierz XLSX albo Pobierz PDF.
5. Po pracy kliknij STOP_APKE.bat.

GPKG z dysku sieciowego
-----------------------

Po wrzuceniu pliku przez web aplikacja zapisuje GPKG w lokalnym folderze TEMP
i dopiero z tej lokalnej kopii czyta geopaczke. Dzieki temu dluga analiza nie
mieli SQLite/GPKG po dysku zmapowanym sieciowo.

CLI opcjonalnie
---------------

python scripts/build_bom.py --gpkg "sciezka\projekt.gpkg" --catalog "inputs\KATALOGI PT_03_2026.xlsx" --bell "inputs\STAN BIEZACY _BELL_.xlsx" --task "nazwa_zadania"

CLI domyslnie tez kopiuje GPKG do lokalnego TEMP i pokazuje postep w procentach.
Jezeli chcesz pominac kopiowanie, dodaj:

python scripts/build_bom.py ... --no-local-copy

Uwaga
-----

Paczka nie wymaga internetu do samej pracy, ale instalacja zaleznosci przez
INSTALUJ_ZALEZNOSCI.bat wymaga dostepu do pip/PyPI, jezeli biblioteki nie sa
juz zainstalowane.
