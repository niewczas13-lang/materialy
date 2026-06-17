import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
INPUTS = BASE / "inputs"


def excel_summary(path: Path, max_rows: int = 8) -> dict:
    xls = pd.ExcelFile(path)
    sheets = {}
    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        sheets[sheet] = {
            "shape": list(df.shape),
            "columns": [str(c) for c in df.columns],
            "sample": df.head(max_rows).where(pd.notna(df), None).to_dict(orient="records"),
        }
    return sheets


def gpkg_summary(path: Path, sample_rows: int = 5) -> dict:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    tables = [r["name"] for r in cur.execute("select name from sqlite_master where type='table' order by name")]

    try:
        contents = [dict(r) for r in cur.execute(
            "select table_name, data_type, identifier, description, min_x, min_y, max_x, max_y "
            "from gpkg_contents order by table_name"
        )]
    except sqlite3.Error as exc:
        contents = [{"error": str(exc)}]

    geom_cols = {}
    try:
        for r in cur.execute("select table_name, column_name, geometry_type_name, srs_id from gpkg_geometry_columns"):
            geom_cols[r["table_name"]] = dict(r)
    except sqlite3.Error:
        pass

    layer_details = []
    for item in contents:
        table = item.get("table_name")
        if not table:
            continue
        cols = [dict(r) for r in cur.execute(f"pragma table_info([{table}])")]
        geom_name = geom_cols.get(table, {}).get("column_name")
        non_geom_cols = [c["name"] for c in cols if c["name"] != geom_name]
        count = cur.execute(f"select count(*) as c from [{table}]").fetchone()["c"]
        sample_select = ", ".join(f"[{c}]" for c in non_geom_cols[:25])
        samples = []
        if sample_select:
            samples = [dict(r) for r in cur.execute(f"select {sample_select} from [{table}] limit {sample_rows}")]
        layer_details.append({
            "table": table,
            "count": count,
            "geometry": geom_cols.get(table),
            "columns": [{"name": c["name"], "type": c["type"]} for c in cols],
            "samples": samples,
        })

    con.close()
    return {"tables": tables, "contents": contents, "layers": layer_details}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    summary = {
        "excels": {
            "historia zamówień.xlsx": excel_summary(INPUTS / "historia zamówień.xlsx"),
            "KATALOGI PT_03_2026.xlsx": excel_summary(INPUTS / "KATALOGI PT_03_2026.xlsx"),
        },
        "gpkg": gpkg_summary(INPUTS / "PW Jedlnia OPP03 z nr wstęga.gpkg"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
