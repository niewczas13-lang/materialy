from __future__ import annotations

from pathlib import Path

import pandas as pd

from ftth_bom.models import CatalogItem
from ftth_bom.rules import fmt_sap, normalize_key, normalize_text


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


class Catalog:
    def __init__(self, items: dict[str, CatalogItem]) -> None:
        self.items = items

    @classmethod
    def load(cls, path: str | Path) -> "Catalog":
        path = Path(path)
        with pd.ExcelFile(path) as xls:
            sheet_names = list(xls.sheet_names)
        sheet = "WYNIK" if "WYNIK" in sheet_names else sheet_names[0]
        frame = pd.read_excel(path, sheet_name=sheet, dtype=object)
        columns = list(frame.columns)

        sap_col = _find_column(columns, "Materiał SAP", "Material SAP", "SAP")
        name_col = _find_column(columns, "Opis materiału SAP", "Opis materialu SAP", "Nazwa")
        supplier_col = _find_column(columns, "Nazwa")
        supplier_pos_col = _find_column(columns, "Nr poz Dostawcy w PZ", "Nr poz Dostawcy")
        supplier_desc_col = _find_column(columns, "Opis poz Dostawcy dł", "Opis poz Dostawcy")
        unit_col = _find_column(columns, "Jn zakupowa PZ", "JM")
        category_col = _find_column(columns, "podkategoria 2", "Kategoria")
        if sap_col is None:
            raise ValueError("Nie znaleziono kolumny SAP w katalogu.")

        items: dict[str, CatalogItem] = {}
        for record in frame.to_dict(orient="records"):
            sap = fmt_sap(record.get(sap_col))
            if not sap or sap in items:
                continue
            name = normalize_text(record.get(name_col)) if name_col is not None else ""
            supplier = normalize_text(record.get(supplier_col)) if supplier_col is not None else ""
            items[sap] = CatalogItem(
                sap=sap,
                name=name,
                supplier=supplier,
                supplier_position=normalize_text(record.get(supplier_pos_col)) if supplier_pos_col is not None else "",
                supplier_description=normalize_text(record.get(supplier_desc_col)) if supplier_desc_col is not None else "",
                unit=normalize_text(record.get(unit_col)) if unit_col is not None else "",
                category=normalize_text(record.get(category_col)) if category_col is not None else "",
            )
        return cls(items)

    def get(self, sap: str) -> CatalogItem | None:
        return self.items.get(fmt_sap(sap))

    def contains(self, sap: str) -> bool:
        return fmt_sap(sap) in self.items
