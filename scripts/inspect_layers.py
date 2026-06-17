import sqlite3
import sys
from pathlib import Path


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
GPKG = BASE / "inputs" / "PW Jedlnia OPP03 z nr wstęga.gpkg"
LAYERS = [
    "PA",
    "K Linia Napowietrzna",
    "K Słup",
    "Odcinki Kanalizacji",
    "Otwory Kanalizacji",
    "K PA",
    "K ZS",
    "K OPP",
]


def clean(v):
    if isinstance(v, bytes):
        return f"BLOB({len(v)})"
    return v


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(GPKG)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    for layer in LAYERS:
        print(f"\n### {layer}")
        cols = [r["name"] for r in cur.execute(f"pragma table_info([{layer}])")]
        print(cols)
        non_geom = [c for c in cols if c != "geom"][:22]
        sql = f"select {', '.join('[' + c + ']' for c in non_geom)} from [{layer}] limit 10"
        for row in cur.execute(sql):
            print({k: clean(row[k]) for k in row.keys()})
    con.close()


if __name__ == "__main__":
    main()
