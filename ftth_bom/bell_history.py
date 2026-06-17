from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from ftth_bom.models import HistoryRow
from ftth_bom.rules import as_float, classify_material_name, extract_fx, fmt_sap, normalize_key, normalize_match, normalize_text


def _find_column(columns: list[object], *needles: str) -> object | None:
    normalized = {normalize_key(column): column for column in columns}
    for needle in needles:
        wanted = normalize_key(needle)
        if wanted in normalized:
            return normalized[wanted]
    for needle in needles:
        parts = [part for part in normalize_key(needle).split() if part]
        for key, column in normalized.items():
            if all(part in key for part in parts):
                return column
    return None


def _find_sheet(path: Path) -> str:
    with pd.ExcelFile(path) as xls:
        sheet_names = list(xls.sheet_names)
    for sheet in sheet_names:
        if normalize_key(sheet) == "stan materialow":
            return sheet
    for sheet in sheet_names:
        if "stan" in normalize_key(sheet) and "material" in normalize_key(sheet):
            return sheet
    return sheet_names[0]


def load_bell_history(path: str | Path) -> list[HistoryRow]:
    path = Path(path)
    sheet = _find_sheet(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        frame = pd.read_excel(path, sheet_name=sheet, header=1, dtype=object)
    frame = frame.dropna(how="all")

    columns = list(frame.columns)
    fx_col = _find_column(columns, "F/X", "X")
    target_col = _find_column(columns, "Docelowy X")
    sto_col = _find_column(columns, "STO")
    task_col = _find_column(columns, "zadanie")
    sap_col = _find_column(columns, "NUMER INDEKSU SAP", "NUMER INDEKSU")
    name_col = _find_column(columns, "Nazwa Towaru", "Rodzaj Asortymentu")
    unit_col = _find_column(columns, "JM")
    qty_col = _find_column(columns, "Ilosc_Zamówiona", "Ilosc Zamowiona", "Ilosc")
    status_col = _find_column(columns, "STATUS", "STAN")

    required = {
        "F/X": fx_col,
        "SAP": sap_col,
        "Nazwa Towaru": name_col,
        "JM": unit_col,
        "Ilosc_Zamówiona": qty_col,
    }
    missing = [name for name, column in required.items() if column is None]
    if missing:
        raise ValueError(f"Brakuje kolumn w BELL: {', '.join(missing)}")

    rows: list[HistoryRow] = []
    for record in frame.to_dict(orient="records"):
        sap = fmt_sap(record.get(sap_col))
        name = normalize_text(record.get(name_col))
        if not sap or not name:
            continue
        fx = normalize_text(record.get(fx_col))
        target_x = normalize_text(record.get(target_col)) if target_col is not None else ""
        sto = normalize_text(record.get(sto_col)) if sto_col is not None else ""
        task = normalize_text(record.get(task_col)) if task_col is not None else ""
        unit = normalize_text(record.get(unit_col))
        status = normalize_text(record.get(status_col)) if status_col is not None else ""
        all_fx = tuple(sorted(set(extract_fx(fx) + extract_fx(target_x))))
        search_text = normalize_match(" ".join([fx, target_x, sto, task, name, status]))
        material_class = classify_material_name(name, sap)
        rows.append(
            HistoryRow(
                fx=fx,
                target_x=target_x,
                sto=sto,
                task=task,
                sap=sap,
                name=name,
                unit=unit,
                ordered_qty=as_float(record.get(qty_col)),
                status=status,
                material_class=material_class,
                all_fx=all_fx,
                search_text=search_text,
            )
        )
    return rows
