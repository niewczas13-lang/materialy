# FTTH BOM

Lokalna aplikacja web do generowania listy materialow FTTH z pliku GPKG.

## Uruchomienie na nowym komputerze

```powershell
git clone https://github.com/niewczas13-lang/materialy.git
cd materialy
.\INSTALUJ_ZALEZNOSCI.bat
.\URUCHOM_APKE.bat
```

Aplikacja startuje w tle na:

```text
http://127.0.0.1:8787/
```

Po sieci LAN jest dostepna pod adresem komputera, np.:

```text
http://192.168.x.x:8787/
```

## Autostart po restarcie

Po pierwszym uruchomieniu kliknij:

```powershell
.\DODAJ_AUTOSTART.bat
```

Skrypt tworzy zadanie Harmonogramu zadan Windows `FTTH BOM`, ktore uruchamia
aplikacje w tle po zalogowaniu uzytkownika. Nie wymaga uprawnien administratora
w typowej konfiguracji Windows.

Usuniecie autostartu:

```powershell
.\USUN_AUTOSTART.bat
```

## Aktualizacja

```powershell
.\AKTUALIZUJ_APKE.bat
```

Skrypt zatrzymuje aplikacje, pobiera najnowsze pliki z GitHuba, robi reset
trackowanych plikow do aktualnej wersji `origin/main` i uruchamia aplikacje
ponownie w tle.

Jesli przy aktualizacji pojawia sie `Repository not found`, to komputer nie ma
dostepu do repozytorium. Najprosciej ustaw repo jako publiczne w GitHub:
`Settings -> General -> Danger Zone -> Change repository visibility -> Public`.
Alternatywnie zaloguj Git/GitHub na komputerze klienta kontem, ktore ma dostep
do prywatnego repo.

## Dane lokalne

Do repo nie sa wrzucane pliki projektowe ani historia/katalog:

- `*.gpkg`
- `*.xlsx`
- `data/`
- `outputs/`
- `dist/`

Katalog inwestora, BELL i analizowane GPKG trzymaj lokalnie w folderze
`inputs/`.
