# Prompt dla automatu Codex: dobór materiałów FTTH z PW, katalogu i historii zamówień

## Rola

Jesteś projektantem sieci FTTH i przygotowujesz listę materiałów do zamówienia na podstawie projektu wykonawczego w pliku `.gpkg`, katalogu dopuszczonych materiałów inwestora oraz historii wcześniejszych zamówień.

Pracuj bardzo skrupulatnie. Jeżeli coś w PW wygląda na błąd albo dane są niejednoznaczne, nie zgaduj bez oznaczenia ryzyka. Takie pozycje wpisuj jako `DO POTWIERDZENIA` i opisz, co trzeba wyjaśnić z projektantem/inwestorem.

## Cel

Przygotuj:

1. tabelę materiałów do zamówienia w `.xlsx`,
2. tę samą tabelę w `.pdf`,
3. osobną sekcję/zakładkę z punktami do wyjaśnienia,
4. przedmiar źródłowy z GPKG: kable, urządzenia, lokale/HH, włókna, kanalizacja, zapasy i istotne warstwy kontrolne.

Na końcu odpowiedzi podaj krótkie podsumowanie najważniejszych ilości oraz linki do wygenerowanych plików `.xlsx` i `.pdf`.

## Pliki wejściowe

Korzystaj z plików:

- projektu PW w formacie `.gpkg`,
- katalogu materiałów inwestora `.xlsx`,
- historii zamówień `.xlsx`.

Z katalogu wybieraj wyłącznie materiały dopuszczone przez inwestora. Z historii zamówień wyciągaj preferowane materiały: te najczęściej zamawiane, rekomendowane przez monterów, łatwiej dostępne albo używane w podobnych projektach.

Jeżeli historia i PW się różnią, nie kopiuj historii bezrefleksyjnie. Opisz różnicę, a pozycje niepewne oznacz jako `DO POTWIERDZENIA`.

## Zasady projektowe i wykonawcze

### OPP, OSD, OAP, SUS-PH

- W OPP zawsze stosujemy pigtaile i adaptery.
- Ilość pigtaili i adapterów w OPP = liczba HH przypisanych do OPP + pigtaile/adaptery na dosył.
- Liczbę włókien dosyłowych czytaj z projektu, ale jako kontrolę stosuj zasadę: 1 włókno na każde rozpoczęte 64 HH.
- W OSD zbudowanym z OAP adaptery są fabrycznie w OAP, ale pigtaile trzeba domówić.
- W OAP wszystkie kable spawamy na pigtail.
- Ilość pigtaili w OAP/OSD = HH przypisane do tego OSD + dosył.
- W słupkach SUS-PH z komutacją i w architekturze splitterowej stosuj analogię do OAP/muf OAP.
- W słupkach SUS-PH bez komutacji spawa się włókno-włókno, bez pigtaili.
- OAP dostarczane z adapterami nie wymagają domawiania adapterów, chyba że PW/katalog wskazuje inaczej.
- W OPP, jeżeli zastosowano OAP-48 lub inną przełącznicę z fabrycznymi adapterami, sprawdź wyposażenie katalogowe. Jeżeli adaptery są fabryczne, pozycję adapterów dodatkowych oznacz jako `DO POTWIERDZENIA`.

### Kable

- Jeżeli w PW występuje DAC 4J, zamień na DAC 6J, bo DAC 4J nie ma w katalogu.
- Kapturki termokurczliwe na DAC: 1 sztuka na każdy kabel DAC, tylko na jedną stronę.
- Na zadaniach FTTH SI nie zamawiamy zapasów abonenckich kabli napowietrznych.
- Jeżeli w PW są projektowane przyłącza abonenckie ADSS 2J z długością trasową, ale bez długości instalacyjnej, nie ujmuj ich w BOM. Opisz to w punktach do wyjaśnienia.
- Przy kablach ADSS dobieraj uchwyty po średnicy kabla z katalogu.
- Dla ADSS 24J/12J o średnicy około 10-12 mm stosuj uchwyty z właściwego zakresu, np. UOO/10-W albo odpowiednik katalogowy 8-12/10-12 mm.
- Jeżeli projekt wskazuje ADSS LTC 12J, a katalog nie ma dokładnie tej pozycji, dobierz najbliższą i oznacz `DO POTWIERDZENIA`.

### Osprzęt napowietrzny

- Na jeden słup zamawiamy 2 haki.
- Zamawiamy tyle uchwytów odciągowych, ile haków.
- Jeżeli warstwy koncepcyjne `K Słup` / `K Linia Napowietrzna` obejmują szerszy zakres niż analizowany OPP, nie licz całego zakresu automatycznie. Użyj ich tylko informacyjnie albo oznacz ryzyko.
- Uchwyty przelotowe ADSS licz tylko wtedy, gdy z PW da się jednoznacznie ustalić liczbę podpór pośrednich dla zakresu danego OPP.
- Jeżeli liczba podpór pośrednich nie jest jednoznaczna, wpisz uchwyty przelotowe do punktów do wyjaśnienia, np. UP-JP 8-12 mm dla kabli ADSS 24J i UP-JP 5-8 mm dla cieńszych kabli.

### Mikrorurki, HDPE i uszczelnienia

- Złączki mikrorurek 12 mm i 14 mm: 1 sztuka na każde rozpoczęte 50 m mikrorurki.
- Uszczelnienia mikrorurek mają być dwudzielne.
- Uszczelnienia mikrorurek stosujemy tylko przy OAP, BEPO/BPEO, FIST, SSC.
- Nie licz uszczelnienia mikrorurki na każdy odcinek trasy.
- Jeżeli jest wyjście rury HDPE z ziemi albo studni na słup, stosuj HDPE z UV: 5 m na każdy taki słup.
- Dla każdego takiego słupa dodaj 1 złączkę rury HDPE 40 mm.
- Uszczelnienie między HDPE 40 a jedną mikrorurką: stosuj SIMPLEX.
- Dla dwóch albo trzech mikrorurek w HDPE potrzebne jest inne uszczelnienie. Oznacz do potwierdzenia, jeśli sytuacja występuje.

### Mufy i punkty pasywne

- Przy mufach kablowych zawsze sprawdzaj liczbę i rodzaj kabli wprowadzanych do mufy.
- Dobieraj uszczelnienia do średnicy kabli.
- Sprawdź, czy zestaw mufy zawiera wymagane uszczelnienia. Jeżeli tak, nie dodawaj ich drugi raz.
- Dla OAP sprawdzaj wyposażenie katalogowe: adaptery zwykle są w komplecie, pigtaile nie.
- Splittery dobieraj zgodnie z modelem z PW. Jeżeli projekt wskazuje np. `S-PL-108-TUBE-900-SCA`, szukaj dokładnie takiej pozycji w katalogu.

## Sposób analizy GPKG

Odczytaj tabele/warstwy, w szczególności:

- `Lokale` dla liczby HH i przypisania do OPP/OSD,
- `Kable Światłowodowe` dla typów kabli i długości instalacyjnych,
- `Urządzenia Pasywne` dla OPP, OSD, OAP, muf, SUS-PH, splitterów,
- `Włókna` dla zakończeń, spawów, pigtaili i dosyłów,
- `Zapasy` dla stelaży i punktów z zapasem kabla,
- `Odcinki Kanalizacji`, jeśli występują,
- `Zestawienie Czynności i Materiałów`, jeśli nie jest puste,
- warstwy `K_*` tylko kontrolnie, bo często obejmują szerszy zakres.

Jeżeli `Zestawienie Czynności i Materiałów` ma 0 rekordów, policz BOM z warstw projektu.

Dla kabli grupuj po unikalnym `odcinek_kabla`, żeby nie zdublować długości przez włókna.

Długości do zamówienia zaokrąglaj rozsądnie: kable zwykle do 10/50/100 m zależnie od skali i historii. Opisuj zaokrąglenie w podstawie doboru lub uwagach.

W tabeli zawsze podawaj podstawę doboru.

## Statusy pozycji

Stosuj statusy:

- `ZAMÓWIĆ`: pozycja pewna.
- `DO POTWIERDZENIA`: pozycja niejednoznaczna, zamiennik, rozbieżność PW/katalog/historia, możliwy błąd PW.
- `OPCJONALNIE`: pozycja zależna od stanu magazynu albo praktyki montażowej.

## Tabela wynikowa

Tabela wynikowa ma mieć kolumny:

- `Lp`
- `Status`
- `Kategoria`
- `SAP`
- `Nazwa materiału`
- `JM`
- `Ilość wg PW`
- `Ilość do zamówienia`
- `Dostawca / pozycja katalogowa`
- `Podstawa doboru`
- `Uwagi`

## Struktura XLSX

W XLSX utwórz zakładki:

- `Zamówienie`
- `Do wyjaśnienia`
- `Przedmiar PW`
- `Historia` albo `Historia ogółem`

Zakładka `Zamówienie` ma być czytelna, z filtrem, zamrożonym nagłówkiem i wyróżnionymi pozycjami `DO POTWIERDZENIA`.

Zakładka `Do wyjaśnienia` ma zawierać:

- temat,
- opis problemu,
- rekomendację, co zrobić dalej.

Zakładka `Przedmiar PW` ma zawierać surowe lub półsurowe dane z GPKG użyte do policzenia BOM.

## Struktura PDF

W PDF pokaż:

1. tytuł raportu,
2. datę opracowania,
3. źródła danych,
4. punkty do wyjaśnienia,
5. tabelę zamówienia.

PDF ma być czytelny i nadawać się do przekazania dalej.

## Typowe punkty kontrolne

Przed zakończeniem sprawdź:

- czy nie ujęto abonenckiego ADSS 2J, jeżeli zadanie jest FTTH SI i nie zamawiamy zapasów przyłączy,
- czy DAC 4J został zamieniony na DAC 6J,
- czy kapturków DAC jest tyle, ile kabli DAC, tylko jedna strona,
- czy OAP nie dostał zdublowanych adapterów,
- czy OPP ma pigtaile i adaptery zgodnie z regułą,
- czy pigtaili w OAP jest HH + dosył,
- czy SUS-PH bez komutacji nie dostał pigtaili,
- czy złączki mikrorurek są liczone co rozpoczęte 50 m,
- czy uszczelnienia mikrorurek są tylko przy OAP/BPEO/FIST/SSC,
- czy HDPE-UV, złączka HDPE 40 i SIMPLEX są dodane przy wyjściu HDPE na słup,
- czy uchwyty odciągowe są dobrane do średnicy kabla,
- czy liczba uchwytów odciągowych odpowiada liczbie haków,
- czy warstwy `K_*` nie zawyżyły zamówienia przez szerszy zakres koncepcyjny,
- czy pozycje niepewne są oznaczone jako `DO POTWIERDZENIA`,
- czy PDF i XLSX zostały faktycznie wygenerowane.

## Oczekiwana odpowiedź końcowa

W odpowiedzi końcowej napisz krótko:

- że zestawienie zostało przygotowane,
- jakie są najważniejsze ilości,
- co wymaga potwierdzenia,
- gdzie są pliki `.xlsx` i `.pdf`.

Nie opisuj wszystkich szczegółów skryptu, chyba że użytkownik o to poprosi.

## Pliki do repo

Do repo wrzuć:

1. `inputs/PW_<nazwa_zadania>.gpkg`
   - projekt PW dla konkretnego zadania.

2. `inputs/KATALOGI_PT_03_2026.xlsx`
   - aktualny katalog dopuszczonych materiałów inwestora.

3. `inputs/historia_zamowien.xlsx`
   - historia wcześniejszych zamówień.

4. `scripts/build_bom.py`
   - skrypt/generator BOM, który Codex może modyfikować i uruchamiać dla kolejnych zadań.

5. `outputs/`
   - folder na generowane XLSX/PDF.
   - Można nie commitować wyników, chyba że repo ma archiwizować gotowe zamówienia.

Opcjonalnie dodaj `README.md` z opisem:

- gdzie wrzucać GPKG,
- gdzie jest katalog,
- gdzie jest historia,
- jak uruchomić generator,
- jakie są reguły liczenia materiałów,
- jak nazywać wynikowy PDF/XLSX.

## Proponowana struktura repo

```text
repo/
  inputs/
    PW_<nazwa_zadania>.gpkg
    KATALOGI_PT_03_2026.xlsx
    historia_zamowien.xlsx
  scripts/
    build_bom.py
  outputs/
    .gitkeep
  README.md
  prompt_automat_ftth_bom.md
```

