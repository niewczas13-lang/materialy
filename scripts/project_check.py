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

    checks = {
        "MI-MKF 144 rows": """
            select odcinek_kabla, fragment, typ_elementu, od, do,
                   dl_trasowa, dl_optyczna, dl_instalacyjna
            from [Kable Światłowodowe]
            where model_kabla like '%144%'
            order by odcinek_kabla, fragment
        """,
        "MI-MKF all cable rows": """
            select model_kabla, odcinek_kabla, fragment, typ_elementu, od, do,
                   dl_trasowa, dl_optyczna, dl_instalacyjna
            from [Kable Światłowodowe]
            where model_kabla like 'MI-MKF%'
            order by model_kabla, odcinek_kabla, fragment
        """,
        "cables unique by model": """
            with per_cable as (
              select odcinek_kabla, model_kabla, liczba_wlokien,
                     max(coalesce(dl_instalacyjna,0)) dl_i,
                     max(coalesce(dl_optyczna,0)) dl_o,
                     max(coalesce(dl_trasowa,0)) dl_t
              from [Kable Światłowodowe]
              group by odcinek_kabla, model_kabla, liczba_wlokien
            )
            select model_kabla, count(*) n, sum(dl_t) trasa, sum(dl_o) optyczna, sum(dl_i) instal
            from per_cable
            group by model_kabla
            order by model_kabla
        """,
        "zapasy by cable model": """
            select k.model_kabla, count(z.fid) n_zapasow, sum(z.dlugosc) dl_zapasow
            from Zapasy z
            left join (
              select distinct odcinek_kabla, model_kabla from [Kable Światłowodowe]
            ) k on k.odcinek_kabla = z.odcinek_kabla
            group by k.model_kabla
            order by k.model_kabla
        """,
    }

    for title, sql in checks.items():
        print(f"\n### {title}")
        for row in cur.execute(sql):
            print(dict(row))

    con.close()


if __name__ == "__main__":
    main()
