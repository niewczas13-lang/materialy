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

## Aktualizacja

```powershell
.\AKTUALIZUJ_APKE.bat
```

Skrypt zatrzymuje aplikacje, pobiera najnowsze pliki z GitHuba, robi reset
trackowanych plikow do aktualnej wersji `origin/main` i uruchamia aplikacje
ponownie w tle.

## Dane lokalne

Do repo nie sa wrzucane pliki projektowe ani historia/katalog:

- `*.gpkg`
- `*.xlsx`
- `data/`
- `outputs/`
- `dist/`

Katalog inwestora, BELL i analizowane GPKG trzymaj lokalnie w folderze
`inputs/`.
