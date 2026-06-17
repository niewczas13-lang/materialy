import json
import re
import sys
from pathlib import Path

import pandas as pd


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
CATALOG = BASE / "inputs" / "KATALOGI PT_03_2026.xlsx"
HISTORY = BASE / "inputs" / "historia zamówień.xlsx"

OUT_COLS = [
    "Materiał SAP",
    "Opis materiału SAP",
    "Nr poz Dostawcy w PZ",
    "Opis poz Dostawcy dł",
    "Opis długi prd.",
    "Nazwa",
    "podkategoria 2",
    "Jn zakupowa PZ",
    "Min ilość w opakowan",
    "Termin dostawy - dni",
]


QUERIES = [
    ("DAC 2J", ["DAC", "2J"]),
    ("DAC 4J", ["DAC", "4J"]),
    ("MI-MKF 12J", ["MI-MKF", "12J"]),
    ("MI-MKF 24J", ["MI-MKF", "24J"]),
    ("MI-MKF 144J", ["MI-MKF", "144J"]),
    ("ADSS 2J", ["ADSS", "2J"]),
    ("ADSS 12J", ["ADSS", "12J"]),
    ("ADSS 24J", ["ADSS", "24J"]),
    ("ADSS 36J", ["ADSS", "36J"]),
    ("SSC2110", ["SSC2110"]),
    ("OAP 8", ["OAP", "8"]),
    ("SUS PH S", ["SUS", "PH", "S"]),
    ("SPL 1x64", ["SPL", "1X64"]),
    ("adapter SC APC", ["ADAPTER", "SC", "APC"]),
    ("mufa", ["MUFA"]),
    ("uszczelnienia muf", ["USZCZEL", "MUFA"]),
    ("zawiesia ADSS", ["ADSS", "UCHWYT"]),
    ("zawiesia kabel", ["ZAWIES", "KABEL"]),
    ("uchwyt odciagowy", ["UCHWYT", "ODCI"]),
    ("słupek/szafka OSD", ["SŁUPEK"]),
    ("rura mikrokanalizacja", ["MIKRORUR"]),
    ("rura RHDPE", ["RHDPE"]),
]


def norm(value) -> str:
    value = "" if pd.isna(value) else str(value)
    return re.sub(r"\s+", " ", value.upper())


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cat = pd.read_excel(CATALOG, sheet_name="WYNIK")
    cat["_search"] = cat[[
        "Opis materiału SAP",
        "Nr poz Dostawcy w PZ",
        "Opis poz Dostawcy dł",
        "Opis długi prd.",
        "Nazwa",
        "podkategoria 2",
    ]].apply(lambda r: " | ".join(norm(v) for v in r), axis=1)

    hist = pd.read_excel(HISTORY, sheet_name="Sheet1")
    hist["_search"] = hist["Nazwa Towaru"].apply(norm)
    hist["Ilosc_Zamówiona"] = pd.to_numeric(hist["Ilosc_Zamówiona"], errors="coerce").fillna(0)

    out = {}
    for label, terms in QUERIES:
        mask = pd.Series(True, index=cat.index)
        for term in terms:
            mask &= cat["_search"].str.contains(term.upper(), regex=False, na=False)
        out[label] = {
            "catalog": cat.loc[mask, OUT_COLS].head(25).where(pd.notna(cat.loc[mask, OUT_COLS].head(25)), None).to_dict(orient="records"),
        }
        hmask = pd.Series(True, index=hist.index)
        for term in terms:
            hmask &= hist["_search"].str.contains(term.upper(), regex=False, na=False)
        h = (
            hist.loc[hmask]
            .groupby(["NUMER \nINDEKSU\n(SAP)", "Nazwa Towaru", "JM"], dropna=False)
            .agg(ilosc=("Ilosc_Zamówiona", "sum"), wystapienia=("Nazwa Towaru", "size"))
            .reset_index()
            .sort_values(["wystapienia", "ilosc"], ascending=False)
            .head(15)
        )
        out[label]["history"] = h.where(pd.notna(h), None).to_dict(orient="records")

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
