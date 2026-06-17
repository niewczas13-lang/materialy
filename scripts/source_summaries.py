import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
INPUTS = BASE / "inputs"
GPKG = INPUTS / "PW Jedlnia OPP03 z nr wstęga.gpkg"
CATALOG = INPUTS / "KATALOGI PT_03_2026.xlsx"
HISTORY = INPUTS / "historia zamówień.xlsx"


def rows(cur, sql, params=()):
    return [dict(r) for r in cur.execute(sql, params).fetchall()]


def gpkg_summaries():
    con = sqlite3.connect(GPKG)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    summaries = {
        "cable_models_unique_order_lengths": rows(cur, """
            with per_cable as (
              select
                odcinek_kabla,
                model_kabla,
                liczba_wlokien,
                max(coalesce(dl_instalacyjna, dl_optyczna, dl_trasowa, 0)) as dl_zamowieniowa_m,
                max(coalesce(dl_optyczna, dl_instalacyjna, dl_trasowa, 0)) as dl_optyczna_m,
                max(coalesce(dl_trasowa, 0)) as dl_trasowa_m,
                max(coalesce(dl_podwieszana, 0)) as dl_podwieszana_m,
                group_concat(distinct typ_elementu) as typy
              from [Kable Światłowodowe]
              where coalesce(model_kabla, '') <> ''
              group by odcinek_kabla, model_kabla, liczba_wlokien
            )
            select
              model_kabla,
              liczba_wlokien,
              count(*) as liczba_odcinkow,
              round(sum(dl_zamowieniowa_m), 2) as suma_dl_zamowieniowa_m,
              round(sum(dl_optyczna_m), 2) as suma_dl_optyczna_m,
              round(sum(dl_trasowa_m), 2) as suma_dl_trasowa_m,
              round(sum(dl_podwieszana_m), 2) as suma_dl_podwieszana_m,
              group_concat(distinct typy) as typy
            from per_cable
            group by model_kabla, liczba_wlokien
            order by liczba_wlokien, model_kabla
        """),
        "cable_types_raw_rows": rows(cur, """
            select
              typ_elementu,
              model_kabla,
              count(*) as rows_count,
              count(distinct odcinek_kabla) as unique_cables,
              round(sum(coalesce(dl_trasowa, 0)), 2) as sum_dl_trasowa_rows,
              round(sum(coalesce(dl_instalacyjna, 0)), 2) as sum_dl_instalacyjna_rows,
              round(sum(coalesce(dl_podwieszana, 0)), 2) as sum_dl_podwieszana_rows
            from [Kable Światłowodowe]
            group by typ_elementu, model_kabla
            order by typ_elementu, model_kabla
        """),
    }

    for layer in [
        "Urządzenia Pasywne",
        "Zapasy",
        "PA",
        "Odcinki Kanalizacji",
        "Otwory Kanalizacji",
        "K Linia Napowietrzna",
        "K Słup",
        "K Kable Dosyłowe",
        "K Kable Dołączeniowe",
        "K Kable Instalacyjne",
        "K PA",
        "K ZS",
        "K OPP",
    ]:
        exists = cur.execute("select 1 from sqlite_master where type='table' and name=?", (layer,)).fetchone()
        if not exists:
            continue
        columns = [r["name"] for r in cur.execute(f"pragma table_info([{layer}])")]
        summaries[f"{layer}_columns"] = columns
        summaries[f"{layer}_count"] = cur.execute(f"select count(*) c from [{layer}]").fetchone()["c"]
        select_cols = [c for c in columns if c.lower() not in {"geom"}][:18]
        if select_cols:
            summaries[f"{layer}_sample"] = rows(
                cur,
                f"select {', '.join('[' + c + ']' for c in select_cols)} from [{layer}] limit 8",
            )

    con.close()
    return summaries


def catalog_history_summaries():
    cat = pd.read_excel(CATALOG, sheet_name="WYNIK")
    hist = pd.read_excel(HISTORY, sheet_name="Sheet1")

    hist["ilosc"] = pd.to_numeric(hist["Ilosc_Zamówiona"], errors="coerce").fillna(0)
    hist_group = (
        hist.groupby(["NUMER \nINDEKSU\n(SAP)", "Nazwa Towaru", "JM"], dropna=False)
        .agg(ilosc_sum=("ilosc", "sum"), wystapienia=("ilosc", "size"), projekty=("NAZWA", lambda s: ", ".join(sorted(set(map(str, s)))[:6])))
        .reset_index()
        .sort_values(["wystapienia", "ilosc_sum"], ascending=False)
    )

    text_cols = ["Opis materiału SAP", "Opis poz Dostawcy dł", "Opis długi prd.", "podkategoria 2", "Nazwa"]
    cat["_txt"] = cat[text_cols].fillna("").astype(str).apply(lambda r: " | ".join(r), axis=1).str.upper()

    keyword_groups = {
        "kable_dac_ftth": ["DAC", "2J", "4J", "8J", "12J", "24J", "48J", "72J"],
        "mufy": ["MUFA", "FOSC", "FIST", "NAS", "OSŁONA ZŁĄCZOWA"],
        "uszczelnienia": ["USZCZEL", "SEAL"],
        "splittery_adaptery": ["SPLIT", "ADAPTER", "PIGTAIL", "PATCHCORD"],
        "napowietrzne_zawiesia": ["ZAWIES", "UCHWYT", "ODCIĄG", "KOTW", "NAPOW", "ADSS"],
        "rury_kanalizacja": ["RHDPE", "MIKRORUR", "RURA", "KANAL", "ZŁĄCZKA", "ZŁACZKA"],
        "szafy_skrzynki": ["SZAF", "SZAFA", "SZAFKA", "OPP", "OSD", "PRZEŁĄCZNICA"],
    }
    catalog_hits = {}
    for name, keywords in keyword_groups.items():
        mask = False
        for kw in keywords:
            mask = mask | cat["_txt"].str.contains(kw, regex=False, na=False)
        cols = [
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
        catalog_hits[name] = cat.loc[mask, cols].head(80).where(pd.notna(cat.loc[mask, cols].head(80)), None).to_dict(orient="records")

    return {
        "history_top": hist_group.head(120).where(pd.notna(hist_group.head(120)), None).to_dict(orient="records"),
        "catalog_hits": catalog_hits,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {"gpkg": gpkg_summaries(), "catalog_history": catalog_history_summaries()}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
