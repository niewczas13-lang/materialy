from __future__ import annotations

import sqlite3
from collections import defaultdict

from ftth_bom.models import MaterialTakeoff
from ftth_bom.rules import as_float, classify_material_name, is_orderable_material_class, normalize_key, normalize_text


def read_material_takeoff(con: sqlite3.Connection, layers: list[str]) -> list[MaterialTakeoff]:
    grouped: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for layer in layers:
        if not _is_project_layer(layer):
            continue
        columns = _columns(con, layer)
        if not columns:
            continue
        if "odcinki kanalizacji" in normalize_key(layer):
            _scan_linear_layer(con, layer, columns, grouped)
        elif "urzadzenia pasywne" in normalize_key(layer):
            _scan_count_layer(con, layer, columns, grouped)

    return [
        MaterialTakeoff(
            material_class=material_class,
            name=name,
            source_layer=source_layer,
            count=int(record["count"]),
            length_m=round(float(record["length_m"]), 2),
            unit=unit,
            examples=tuple(record["examples"]),
        )
        for (material_class, name, source_layer, unit), record in sorted(grouped.items())
    ]


def _scan_linear_layer(
    con: sqlite3.Connection,
    layer: str,
    columns: list[str],
    grouped: dict[tuple[str, str, str, str], dict[str, object]],
) -> None:
    name_col = _column(columns, "oznaczenie") or _column(columns, "model")
    length_col = _column(columns, "dlugosc") or _column(columns, "wtorna_dl_trasowa")
    id_col = _column(columns, "id_odc") or _column(columns, "did")
    if not name_col:
        return

    select = [
        f"[{name_col}] as name",
        f"[{length_col}] as length_m" if length_col else "0 as length_m",
        f"[{id_col}] as example" if id_col else "'' as example",
    ]
    for row in con.execute(f"select {', '.join(select)} from [{layer}]"):
        name = normalize_text(row["name"])
        material_class = classify_material_name(name)
        if not _is_scanner_material(material_class):
            continue
        _add_grouped(
            grouped,
            material_class=material_class,
            name=name,
            source_layer=layer,
            unit="m",
            count=1,
            length_m=as_float(row["length_m"]),
            example=normalize_text(row["example"]),
        )


def _scan_count_layer(
    con: sqlite3.Connection,
    layer: str,
    columns: list[str],
    grouped: dict[tuple[str, str, str, str], dict[str, object]],
) -> None:
    model_col = _column(columns, "model_urzadzenia") or _column(columns, "model")
    producer_col = _column(columns, "producent")
    type_col = _column(columns, "typ_elementu")
    node_col = _column(columns, "wezel") or _column(columns, "nazwa")
    if not model_col:
        return
    select = [
        f"[{model_col}] as model",
        f"[{producer_col}] as producer" if producer_col else "'' as producer",
        f"[{type_col}] as element_type" if type_col else "'' as element_type",
        f"[{node_col}] as example" if node_col else "'' as example",
    ]
    for row in con.execute(f"select {', '.join(select)} from [{layer}]"):
        model = normalize_text(row["model"])
        material_class = classify_material_name(f"{model} {row['producer']} {row['element_type']}")
        if not _is_scanner_material(material_class):
            continue
        _add_grouped(
            grouped,
            material_class=material_class,
            name=model,
            source_layer=layer,
            unit="szt",
            count=1,
            length_m=0.0,
            example=normalize_text(row["example"]),
        )


def _add_grouped(
    grouped: dict[tuple[str, str, str, str], dict[str, object]],
    material_class: str,
    name: str,
    source_layer: str,
    unit: str,
    count: int,
    length_m: float,
    example: str,
) -> None:
    key = (material_class, name, source_layer, unit)
    if key not in grouped:
        grouped[key] = {"count": 0, "length_m": 0.0, "examples": []}
    record = grouped[key]
    record["count"] = int(record["count"]) + count
    record["length_m"] = float(record["length_m"]) + length_m
    if example and example not in record["examples"] and len(record["examples"]) < 8:
        record["examples"].append(example)


def _is_scanner_material(material_class: str) -> bool:
    if material_class == "INNE" or not is_orderable_material_class(material_class):
        return False
    return material_class.startswith(("MIKRORURKA", "HDPE")) or material_class in {
        "PSB_H_144",
        "SUS_PH_S",
        "MUFA_SSC2110",
        "SPLITTER_1X64",
        "SPLITTER",
        "OAP_8",
        "OAP_24",
        "OAP_48",
        "OAP",
    }


def _is_project_layer(layer: str) -> bool:
    key = normalize_key(layer)
    if key.startswith("_") or key.startswith("k "):
        return False
    if any(token in key for token in ["gpkg", "tile", "dzialki", "budynki", "osm", "style"]):
        return False
    return True


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [row["name"] for row in con.execute(f"pragma table_info([{table}])")]
    except sqlite3.Error:
        return []


def _column(columns: list[str], wanted: str) -> str | None:
    wanted_norm = normalize_key(wanted)
    for column in columns:
        if normalize_key(column) == wanted_norm:
            return column
    for column in columns:
        if wanted_norm in normalize_key(column):
            return column
    return None
