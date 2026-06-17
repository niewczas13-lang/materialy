import sqlite3
import sys
from pathlib import Path


BASE = Path(r"C:\Users\Pawel Z\Documents\Codex\2026-05-28\files-mentioned-by-the-user-historia")
GPKG = BASE / "inputs" / "PW Jedlnia OPP03 z nr wstęga.gpkg"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(GPKG)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    queries = {
        "Mikrorury odcinki": """
            select fid, id_odc, typ_elementu, producent, oznaczenie, od, do, dlugosc,
                   wtorna_dl_trasowa, wtorna_dl_w_kanalizacji, wtorna_dl_doziemna,
                   wtorna_dl_na_murze, wtorna_dl_podwieszenie, uwagi
            from [Odcinki Kanalizacji]
            where oznaczenie like '%FP-MR%'
            order by oznaczenie, fid
        """,
        "RHDPE odcinki": """
            select fid, id_odc, typ_elementu, producent, oznaczenie, od, do, dlugosc,
                   wtorna_dl_na_murze, wtorna_dl_podwieszenie
            from [Odcinki Kanalizacji]
            where oznaczenie like '%RHDPE%'
            order by fid
        """,
        "ADSS 2J planowane": """
            select odcinek_kabla, od, do, dl_trasowa, dl_instalacyjna
            from [Kable Światłowodowe]
            where model_kabla like '%ADSS 2J%'
            order by odcinek_kabla
        """,
        "DAC unique": """
            select model_kabla, count(distinct odcinek_kabla) n, sum(distinct dl_instalacyjna) rough_sum
            from [Kable Światłowodowe]
            where model_kabla like 'DAC%'
            group by model_kabla
        """,
        "OSD feed edges": """
            select od, do, model_kabla, liczba_wlokien, max(coalesce(dl_instalacyjna,0)) dl
            from [Kable Światłowodowe]
            where (od like '%/OSD%' or do like '%/OSD%' or od like '%/OPP%' or do like '%/OPP%')
              and do not like '%,%'
            group by od, do, model_kabla, liczba_wlokien
            order by od, do
        """,
    }
    for title, sql in queries.items():
        print(f"\n### {title}")
        for row in cur.execute(sql):
            print(dict(row))

    con.close()


if __name__ == "__main__":
    main()
