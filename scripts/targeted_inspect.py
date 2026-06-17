import json
import sqlite3
import sys
from pathlib import Path


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
GPKG = BASE / "inputs" / "PW Jedlnia OPP03 z nr wstęga.gpkg"

LAYERS = [
    "Zestawienie Czynności i Materiałów",
    "Kable Światłowodowe",
    "Plan_Kable Światłowodowe",
    "Urządzenia Pasywne",
    "Plan_Urządzenia Pasywne",
    "Zapasy",
    "Plan_Zapasy",
    "Odcinki Kanalizacji",
    "Plan_Odcinki Kanalizacji",
    "Otwory Kanalizacji",
    "Plan_Otwory Kanalizacji",
    "PA",
    "Plan_PA",
    "K Linia Napowietrzna",
    "K Słup",
    "K Odcinki Kanalizacji",
    "K Kable Dosyłowe",
    "K Kable Dołączeniowe",
    "K Kable Instalacyjne",
    "K PA",
    "K ZS",
    "K OPP",
    "Lokale",
    "Plan_Lokale",
]


def clean(value):
    if isinstance(value, bytes):
        return f"<BLOB {len(value)} bytes>"
    if isinstance(value, str) and len(value) > 240:
        return value[:237] + "..."
    return value


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(GPKG)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    geom = {}
    for r in cur.execute("select table_name, column_name, geometry_type_name, srs_id from gpkg_geometry_columns"):
        geom[r["table_name"]] = dict(r)

    out = {}
    for layer in LAYERS:
        exists = cur.execute(
            "select 1 from sqlite_master where type='table' and name=?",
            (layer,),
        ).fetchone()
        if not exists:
            continue
        columns = [dict(r) for r in cur.execute(f"pragma table_info([{layer}])")]
        geom_col = geom.get(layer, {}).get("column_name")
        non_geom = [c["name"] for c in columns if c["name"] != geom_col]
        select_cols = non_geom[:35]
        sql_cols = ", ".join(f"[{c}]" for c in select_cols)
        rows = []
        if sql_cols:
            for row in cur.execute(f"select {sql_cols} from [{layer}] limit 12"):
                rows.append({k: clean(row[k]) for k in row.keys()})
        out[layer] = {
            "count": cur.execute(f"select count(*) c from [{layer}]").fetchone()["c"],
            "geometry": geom.get(layer),
            "columns": [{"name": c["name"], "type": c["type"]} for c in columns],
            "sample": rows,
        }

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    con.close()


if __name__ == "__main__":
    main()
