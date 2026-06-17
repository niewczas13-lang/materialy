from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ftth_bom.engine import run_analysis
from ftth_bom.exporters import export_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Uniwersalny generator BOM FTTH z GPKG, katalogu i historii BELL.")
    parser.add_argument("--gpkg", required=True, help="Ścieżka do projektu PW .gpkg")
    parser.add_argument("--catalog", required=True, help="Ścieżka do katalogu materiałów inwestora .xlsx")
    parser.add_argument("--bell", required=True, help="Ścieżka do STAN BIEŻĄCY _BELL_.xlsx")
    parser.add_argument("--task", default=None, help="Nazwa zadania używana w nazwach plików wynikowych")
    parser.add_argument("--outputs", default=str(ROOT / "outputs"), help="Folder wynikowy")
    parser.add_argument("--preferences-db", default=str(ROOT / "data" / "preferences.sqlite"), help="Cache SQLite preferencji")
    parser.add_argument("--no-local-copy", action="store_true", help="Nie kopiuj GPKG do lokalnego folderu temp przed analiza.")
    args = parser.parse_args()

    def progress(event: tuple[int, str]) -> None:
        percent, message = event
        print(f"[{percent:3d}%] {message}", flush=True)

    result = run_analysis(
        gpkg_path=args.gpkg,
        catalog_path=args.catalog,
        bell_path=args.bell,
        task_name=args.task,
        preferences_db=args.preferences_db,
        local_copy=not args.no_local_copy,
        progress=progress,
    )
    progress((95, "Eksport XLSX/PDF"))
    export_result(result, args.outputs)
    progress((100, "Gotowe"))

    print(f"Zestawienie przygotowane: {result.task_name}")
    print(f"HH: {result.project.hh_total}")
    print(f"Pozycje BOM: {len(result.order_rows)}")
    print(f"Do wyjaśnienia: {sum(1 for row in result.order_rows if row.status == 'DO POTWIERDZENIA')}")
    print(f"XLSX: {result.xlsx_path}")
    print(f"PDF: {result.pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
