from __future__ import annotations

import sqlite3
import math
from collections import defaultdict
from pathlib import Path

from ftth_bom.geometry import point_to_line_distance, read_gpkg_lines, read_gpkg_point
from ftth_bom.gpkg_scanner import read_material_takeoff
from ftth_bom.models import CableEdge, CableSummary, DeviceSummary, PoleUse, ProjectData, QuantitySummary
from ftth_bom.rules import (
    as_float,
    as_int,
    classify_material_name,
    extract_fx,
    extract_project_tokens,
    normalize_key,
    normalize_text,
)


def read_gpkg_project(path: str | Path) -> ProjectData:
    path = Path(path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        contents = _gpkg_contents(con)
        layer = _LayerFinder(contents)
        f_numbers, metadata_values, related_f_numbers = _extract_metadata(con)
        project_tokens = sorted(set(extract_project_tokens(path.stem, " ".join(metadata_values))))

        lokale = layer.find("Lokale")
        kable = layer.find("Kable Swiatlowodowe")
        plan_kable = layer.find("Plan_Kable Swiatlowodowe")
        urzadzenia = layer.find("Urzadzenia Pasywne")
        porty = layer.find("Porty Pasywne")
        kanalizacja = layer.find("Odcinki Kanalizacji")
        zapasy = layer.find("Zapasy")
        zestawienie = layer.find("Zestawienie Czynnosci i Materialow")
        przecisk = layer.find("PRZECISK")
        zud = layer.find("ZUD")
        obiekty = layer.find("Obiekty")
        plan_obiekty = layer.find("Plan_Obiekty")
        existing_obiekty = layer.find("_Obiekty")

        hh_by_node, hh_total = _read_hh(con, lokale)
        cable_edges = _read_cables(con, kable)
        cable_summary = _summarize_cables(cable_edges)
        devices = _read_devices(con, urzadzenia)
        ducts = _read_quantities(con, kanalizacja, "Kanalizacja")
        reserves = _read_quantities(con, zapasy, "Zapasy")
        material_takeoff = read_material_takeoff(con, contents)
        used_poles = _read_used_aerial_poles(
            con,
            [kable, plan_kable],
            [obiekty, plan_obiekty, existing_obiekty],
        )
        fiber_counts = _read_fiber_connection_counts(con, layer.find("Wlokna"), porty, cable_edges)
        pigtail_splices = fiber_counts["pigtail_splices"]
        oap_on_used_poles, oap_on_energy_poles = _read_oap_pole_counts(
            con,
            urzadzenia,
            [obiekty, plan_obiekty, existing_obiekty],
            used_poles,
        )
        used_energy_poles = _count_used_energy_poles(
            con,
            [obiekty, plan_obiekty, existing_obiekty],
            used_poles,
        )
        oap_uv_counts = _read_oap_hdpe_uv_pipe_counts(
            con,
            urzadzenia,
            [kable, plan_kable],
            [obiekty, plan_obiekty, existing_obiekty],
            used_poles,
        )
        schedule_count = _count_rows(con, zestawienie)

        return ProjectData(
            source_path=path,
            f_numbers=f_numbers,
            project_tokens=project_tokens,
            hh_total=hh_total,
            hh_by_node=hh_by_node,
            cable_edges=cable_edges,
            cable_summary=cable_summary,
            devices=devices,
            ducts=ducts,
            reserves=reserves,
            material_takeoff=material_takeoff,
            used_poles=used_poles,
            metadata={
                "schedule_rows": schedule_count,
                "metadata_values": metadata_values[:30],
                "related_f_numbers": related_f_numbers,
                "used_poles_tolerance_m": 2.0,
                "pigtail_splices": pigtail_splices,
                "pigtail_splices_raw": fiber_counts["pigtail_splices_raw"],
                "adapter_required_pigtails": fiber_counts["adapter_required_pigtails"],
                "existing_feeder_splice_connections": fiber_counts["existing_feeder_splice_connections"],
                "fiber_splice_connections": fiber_counts["fiber_splice_connections"],
                "splice_sleeves": fiber_counts["splice_sleeves"],
                "oap_on_used_poles": oap_on_used_poles,
                "oap_on_energy_poles": oap_on_energy_poles,
                "used_energy_poles": used_energy_poles,
                **oap_uv_counts,
                "przecisk_length_m": _read_layer_line_length_m(con, przecisk),
                "zud_length_m": _read_layer_line_length_m(con, zud),
            },
        )
    finally:
        con.close()


class _LayerFinder:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def find(self, wanted: str) -> str | None:
        wanted_norm = normalize_key(wanted)
        for name in self.names:
            if normalize_key(name) == wanted_norm:
                return name
        for name in self.names:
            if wanted_norm in normalize_key(name):
                return name
        return None


def _gpkg_contents(con: sqlite3.Connection) -> list[str]:
    try:
        return [row["table_name"] for row in con.execute("select table_name from gpkg_contents")]
    except sqlite3.Error:
        return [row["name"] for row in con.execute("select name from sqlite_master where type='table'")]


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in con.execute(f"pragma table_info([{table}])")]


def _column(columns: list[str], wanted: str) -> str | None:
    wanted_norm = normalize_key(wanted)
    for column in columns:
        if normalize_key(column) == wanted_norm:
            return column
    for column in columns:
        if wanted_norm in normalize_key(column):
            return column
    return None


def _count_rows(con: sqlite3.Connection, table: str | None) -> int:
    if not table:
        return 0
    try:
        return int(con.execute(f"select count(*) as c from [{table}]").fetchone()["c"])
    except sqlite3.Error:
        return 0


def _read_layer_line_length_m(con: sqlite3.Connection, table: str | None) -> float:
    if not table:
        return 0.0
    columns = _columns(con, table)
    geom_col = _column(columns, "geom")
    if not geom_col:
        return 0.0
    total = 0.0
    try:
        rows = con.execute(f"select [{geom_col}] as geom from [{table}]")
    except sqlite3.Error:
        return 0.0
    for row in rows:
        for line in read_gpkg_lines(row["geom"]):
            total += _line_length_m(line)
    return round(total, 1)


def _line_length_m(line) -> float:
    if len(line) < 2:
        return 0.0
    geographic = all(-180 <= point[0] <= 180 and -90 <= point[1] <= 90 for point in line)
    total = 0.0
    for index in range(len(line) - 1):
        start = line[index]
        end = line[index + 1]
        if geographic:
            total += _haversine_m(start, end)
        else:
            total += math.hypot(end[0] - start[0], end[1] - start[1])
    return total


def _haversine_m(start, end) -> float:
    lon1, lat1 = start
    lon2, lat2 = end
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _extract_metadata(con: sqlite3.Connection) -> tuple[list[str], list[str], list[str]]:
    tables = [row["name"] for row in con.execute("select name from sqlite_master where type='table'")]
    all_f_numbers: set[str] = set()
    primary_f_numbers: set[str] = set()
    metadata_values: list[str] = []

    metadata_table = next((table for table in tables if normalize_key(table) == "npd_suite_metadane"), None)
    if metadata_table:
        try:
            rows = con.execute(f"select [klucz] as key, [wartosc] as value from [{metadata_table}]")
        except sqlite3.Error:
            rows = []
        primary_keys = {"sap_definicja_projektu", "doszcz_nazwy", "numer_zadania", "zadanie"}
        for row in rows:
            value = normalize_text(row["value"])
            if not value:
                continue
            found = extract_fx(value)
            if not found:
                continue
            metadata_values.append(value)
            all_f_numbers.update(found)
            if normalize_key(row["key"]) in primary_keys:
                primary_f_numbers.update(found)

    for table in tables:
        if table == metadata_table:
            continue
        columns = _columns(con, table)
        text_columns = [column for column in columns if column.lower() in {"wartosc", "value", "opis", "nazwa"}]
        if not text_columns and any(token in normalize_key(table) for token in ["metadane", "dokumentacja"]):
            text_columns = columns[:8]
        for column in text_columns:
            try:
                rows = con.execute(f"select [{column}] as value from [{table}] where [{column}] is not null limit 300")
            except sqlite3.Error:
                continue
            for row in rows:
                value = normalize_text(row["value"])
                if not value:
                    continue
                found = extract_fx(value)
                if found:
                    metadata_values.append(value)
                    all_f_numbers.update(found)

    if not primary_f_numbers:
        primary_f_numbers = set(all_f_numbers)
    related_f_numbers = all_f_numbers - primary_f_numbers
    return sorted(primary_f_numbers), metadata_values, sorted(related_f_numbers)


def _read_hh(con: sqlite3.Connection, table: str | None) -> tuple[list[dict[str, object]], int]:
    if not table:
        return [], 0
    columns = _columns(con, table)
    node_col = _column(columns, "opp_osd") or _column(columns, "wezel") or columns[0]
    rows = [
        {"node": normalize_text(row["node"]), "hh": int(row["hh"])}
        for row in con.execute(f"select [{node_col}] as node, count(*) as hh from [{table}] group by [{node_col}]")
    ]
    return rows, sum(int(row["hh"]) for row in rows)


def _read_cables(con: sqlite3.Connection, table: str | None) -> list[CableEdge]:
    if not table:
        return []
    columns = _columns(con, table)
    cable_col = _column(columns, "odcinek_kabla") or _column(columns, "id") or columns[0]
    model_col = _column(columns, "model_kabla")
    fibers_col = _column(columns, "liczba_wlokien")
    from_col = _column(columns, "od")
    to_col = _column(columns, "do")
    route_col = _column(columns, "dl_trasowa")
    optical_col = _column(columns, "dl_optyczna")
    install_col = _column(columns, "dl_instalacyjna")

    select_parts = [
        f"[{cable_col}] as cable_id",
        f"max([{model_col}]) as model" if model_col else "'' as model",
        f"max([{fibers_col}]) as fibers" if fibers_col else "null as fibers",
        f"max([{from_col}]) as from_node" if from_col else "'' as from_node",
        f"max([{to_col}]) as to_node" if to_col else "'' as to_node",
        f"max(coalesce([{route_col}], 0)) as route_m" if route_col else "0 as route_m",
        f"max(coalesce([{optical_col}], 0)) as optical_m" if optical_col else "0 as optical_m",
        f"max(coalesce([{install_col}], 0)) as install_m" if install_col else "0 as install_m",
    ]
    query = f"select {', '.join(select_parts)} from [{table}] group by [{cable_col}]"
    edges: list[CableEdge] = []
    for row in con.execute(query):
        cable_id = normalize_text(row["cable_id"])
        model = normalize_text(row["model"])
        if not cable_id:
            continue
        edges.append(
            CableEdge(
                cable_id=cable_id,
                model=model,
                fibers=as_int(row["fibers"]),
                from_node=normalize_text(row["from_node"]),
                to_node=normalize_text(row["to_node"]),
                route_m=as_float(row["route_m"]),
                optical_m=as_float(row["optical_m"]),
                install_m=as_float(row["install_m"]),
                material_class=classify_material_name(model),
            )
        )
    return edges


def _summarize_cables(edges: list[CableEdge]) -> list[CableSummary]:
    grouped: dict[tuple[str, str, int | None], list[CableEdge]] = defaultdict(list)
    for edge in edges:
        grouped[(edge.material_class, edge.model, edge.fibers)].append(edge)
    summaries = []
    for (material_class, model, fibers), members in sorted(grouped.items()):
        summaries.append(
            CableSummary(
                material_class=material_class,
                model=model,
                fibers=fibers,
                sections=len(members),
                route_m=round(sum(edge.route_m for edge in members), 2),
                optical_m=round(sum(edge.optical_m for edge in members), 2),
                install_m=round(sum(edge.install_m for edge in members), 2),
            )
        )
    return summaries


def _read_devices(con: sqlite3.Connection, table: str | None) -> list[DeviceSummary]:
    if not table:
        return []
    columns = _columns(con, table)
    node_col = _column(columns, "wezel")
    type_col = _column(columns, "typ_elementu")
    producer_col = _column(columns, "producent")
    model_col = _column(columns, "model_urzadzenia")
    object_col = _column(columns, "typ_obiektu")
    query = f"""
        select
          {f'[{node_col}]' if node_col else "''"} as node,
          {f'[{type_col}]' if type_col else "''"} as element_type,
          {f'[{producer_col}]' if producer_col else "''"} as producer,
          {f'[{model_col}]' if model_col else "''"} as model,
          {f'[{object_col}]' if object_col else "''"} as object_type,
          count(*) as count
        from [{table}]
        group by node, element_type, producer, model, object_type
    """
    devices = []
    for row in con.execute(query):
        model = normalize_text(row["model"])
        devices.append(
            DeviceSummary(
                node=normalize_text(row["node"]),
                element_type=normalize_text(row["element_type"]),
                producer=normalize_text(row["producer"]),
                model=model,
                object_type=normalize_text(row["object_type"]),
                count=int(row["count"]),
                material_class=classify_material_name(model),
            )
        )
    return devices


def _read_quantities(con: sqlite3.Connection, table: str | None, group: str) -> list[QuantitySummary]:
    if not table:
        return []
    columns = _columns(con, table)
    name_col = _column(columns, "model") or _column(columns, "oznaczenie") or _column(columns, "typ_elementu") or columns[0]
    length_col = _column(columns, "dlugosc") or _column(columns, "dl_trasowa")
    length_expr = f"sum(coalesce([{length_col}], 0))" if length_col else "0"
    query = f"select [{name_col}] as name, count(*) as count, {length_expr} as length_m from [{table}] group by [{name_col}]"
    return [
        QuantitySummary(
            group=group,
            name=normalize_text(row["name"]),
            count=int(row["count"]),
            length_m=round(as_float(row["length_m"]), 2),
        )
        for row in con.execute(query)
    ]


def _read_used_aerial_poles(
    con: sqlite3.Connection,
    cable_tables: list[str | None],
    pole_tables: list[str | None],
    tolerance_m: float = 2.0,
) -> list[PoleUse]:
    aerial_lines = _read_aerial_cable_lines(con, cable_tables)
    if not aerial_lines:
        return []

    matched: dict[str, dict[str, object]] = {}
    for pole in _read_pole_candidates(con, pole_tables):
        cable_matches: set[str] = set()
        material_classes: set[str] = set()
        min_distance = float("inf")
        for cable in aerial_lines:
            distance = min(point_to_line_distance(pole["point"], line) for line in cable["lines"])
            if distance <= tolerance_m:
                cable_matches.add(cable["cable_id"])
                material_classes.add(cable["material_class"])
                min_distance = min(min_distance, distance)
        if not cable_matches:
            continue

        key = pole["dedupe_key"]
        if key not in matched:
            matched[key] = {
                "source_layer": pole["source_layer"],
                "pole_id": pole["pole_id"],
                "model": pole["model"],
                "x": pole["point"][0],
                "y": pole["point"][1],
                "matched_cables": set(),
                "material_classes": set(),
                "distance_m": min_distance,
            }
        record = matched[key]
        record["matched_cables"].update(cable_matches)
        record["material_classes"].update(material_classes)
        record["distance_m"] = min(float(record["distance_m"]), min_distance)

    return [
        PoleUse(
            source_layer=str(record["source_layer"]),
            pole_id=str(record["pole_id"]),
            model=str(record["model"]),
            x=round(float(record["x"]), 3),
            y=round(float(record["y"]), 3),
            matched_cables=tuple(sorted(record["matched_cables"])),
            material_classes=tuple(sorted(record["material_classes"])),
            distance_m=round(float(record["distance_m"]), 2),
        )
        for record in sorted(matched.values(), key=lambda item: (str(item["source_layer"]), str(item["pole_id"])))
    ]


def _read_aerial_cable_lines(con: sqlite3.Connection, tables: list[str | None]) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for table in [name for name in tables if name]:
        columns = _columns(con, table)
        geom_col = _column(columns, "geom")
        cable_col = _column(columns, "odcinek_kabla") or _column(columns, "id") or columns[0]
        model_col = _column(columns, "model_kabla")
        type_col = _column(columns, "typ_elementu")
        if not geom_col:
            continue
        model_expr = f"[{model_col}]" if model_col else "''"
        type_expr = f"[{type_col}]" if type_col else "''"

        query = (
            "select "
            f"[{geom_col}] as geom, "
            f"[{cable_col}] as cable_id, "
            f"{model_expr} as model, "
            f"{type_expr} as element_type "
            f"from [{table}]"
        )
        for row in con.execute(query):
            material_class = classify_material_name(row["model"])
            if not _is_support_aerial_cable(material_class, row["element_type"]):
                continue
            cable_lines = read_gpkg_lines(row["geom"])
            if not cable_lines:
                continue
            lines.append(
                {
                    "source_layer": table,
                    "cable_id": normalize_text(row["cable_id"]) or f"{table}:{len(lines) + 1}",
                    "material_class": material_class,
                    "lines": cable_lines,
                }
            )
    return lines


def _read_pole_candidates(con: sqlite3.Connection, tables: list[str | None]) -> list[dict[str, object]]:
    poles: list[dict[str, object]] = []
    for table in [name for name in tables if name]:
        columns = _columns(con, table)
        geom_col = _column(columns, "geom")
        type_col = _column(columns, "typ_elementu")
        pole_col = _column(columns, "identyfikator_obiektu") or _column(columns, "nazwa") or columns[0]
        model_col = _column(columns, "model")
        if not geom_col:
            continue
        type_expr = f"[{type_col}]" if type_col else "''"
        model_expr = f"[{model_col}]" if model_col else "''"

        query = (
            "select "
            f"[{geom_col}] as geom, "
            f"{type_expr} as element_type, "
            f"[{pole_col}] as pole_id, "
            f"{model_expr} as model "
            f"from [{table}]"
        )
        for row in con.execute(query):
            if not _is_real_pole_candidate(row["element_type"], row["model"], row["pole_id"]):
                continue
            point = read_gpkg_point(row["geom"])
            if not point:
                continue
            pole_id = normalize_text(row["pole_id"])
            poles.append(
                {
                    "source_layer": table,
                    "pole_id": pole_id or f"{table}:{len(poles) + 1}",
                    "model": normalize_text(row["model"]),
                    "point": point,
                    "dedupe_key": normalize_key(pole_id) if pole_id else f"{round(point[0], 2)}:{round(point[1], 2)}",
                }
            )
    return poles


def _is_real_pole_candidate(element_type: object, model: object = "", pole_id: object = "") -> bool:
    element_text = normalize_key(element_type)
    model_text = normalize_key(model)
    pole_text = normalize_key(pole_id)
    if "slup" not in element_text:
        return False
    if "slupek" in element_text:
        return False
    if "sus" in model_text or "sus" in pole_text:
        return False
    return True


def _is_support_aerial_cable(material_class: str, element_type: object) -> bool:
    if material_class.startswith("ADSS") and material_class != "ADSS_2J":
        return True
    element_text = normalize_key(element_type)
    return "napowietrzny" in element_text and material_class.startswith("ADSS") and material_class != "ADSS_2J"


def _read_fiber_connection_counts(
    con: sqlite3.Connection,
    fiber_table: str | None,
    port_table: str | None,
    cable_edges: list[CableEdge] | None = None,
) -> dict[str, int]:
    if not fiber_table:
        return {
            "pigtail_splices": 0,
            "pigtail_splices_raw": 0,
            "adapter_required_pigtails": 0,
            "existing_feeder_splice_connections": 0,
            "fiber_splice_connections": 0,
            "splice_sleeves": 0,
        }

    cable_fibers = {edge.cable_id: edge.fibers for edge in cable_edges or []}
    cable_classes = {edge.cable_id: edge.material_class for edge in cable_edges or []}
    oap_adapter_ports = _read_oap_adapter_ports(con, port_table)
    columns = _columns(con, fiber_table)
    cable_col = _column(columns, "odcinek_kabla")
    start_connection_col = _column(columns, "typ_polaczenia_pocz")
    end_connection_col = _column(columns, "typ_polaczenia_kon")
    start_pigtail_col = _column(columns, "pigtail_pocz_spaw")
    end_pigtail_col = _column(columns, "pigtail_kon_spaw")
    start_node_col = _column(columns, "wezel_pocz")
    end_node_col = _column(columns, "wezel_kon")
    start_device_col = _column(columns, "oznaczenie_urzadzenia_pocz")
    end_device_col = _column(columns, "oznaczenie_urzadzenia_kon")
    start_port_col = _column(columns, "nr_portu_pocz")
    end_port_col = _column(columns, "nr_portu_kon")

    select_parts = [
        f"[{cable_col}] as cable_id" if cable_col else "'' as cable_id",
        f"[{start_connection_col}] as start_connection" if start_connection_col else "'' as start_connection",
        f"[{end_connection_col}] as end_connection" if end_connection_col else "'' as end_connection",
        f"[{start_pigtail_col}] as start_pigtail" if start_pigtail_col else "'' as start_pigtail",
        f"[{end_pigtail_col}] as end_pigtail" if end_pigtail_col else "'' as end_pigtail",
        f"[{start_node_col}] as start_node" if start_node_col else "'' as start_node",
        f"[{end_node_col}] as end_node" if end_node_col else "'' as end_node",
        f"[{start_device_col}] as start_device" if start_device_col else "'' as start_device",
        f"[{end_device_col}] as end_device" if end_device_col else "'' as end_device",
        f"[{start_port_col}] as start_port" if start_port_col else "'' as start_port",
        f"[{end_port_col}] as end_port" if end_port_col else "'' as end_port",
    ]

    raw_pigtails = 0
    pigtail_endpoint_cables: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    adapter_endpoint_cables: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    splice_endpoint_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    existing_feeder_endpoints: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for row in con.execute(f"select {', '.join(select_parts)} from [{fiber_table}]"):
        cable_id = normalize_text(row["cable_id"])
        if _is_splice_connection(row["start_connection"]):
            _add_physical_splice_endpoint(
                splice_endpoint_counts,
                existing_feeder_endpoints,
                cable_id,
                row["start_node"],
                row["start_device"],
                row["start_port"],
            )
        if _is_splice_connection(row["end_connection"]):
            _add_physical_splice_endpoint(
                splice_endpoint_counts,
                existing_feeder_endpoints,
                cable_id,
                row["end_node"],
                row["end_device"],
                row["end_port"],
            )

        if normalize_text(row["start_pigtail"]):
            raw_pigtails += 1
            port_key = _port_key(row["start_node"], row["start_device"], row["start_port"])
            pigtail_endpoint_cables[port_key].append(cable_id)
            if port_key not in oap_adapter_ports:
                adapter_endpoint_cables[port_key].append(cable_id)
        if normalize_text(row["end_pigtail"]):
            raw_pigtails += 1
            port_key = _port_key(row["end_node"], row["end_device"], row["end_port"])
            pigtail_endpoint_cables[port_key].append(cable_id)
            if port_key not in oap_adapter_ports:
                adapter_endpoint_cables[port_key].append(cable_id)

    fiber_splices = sum(math.ceil(count / 2) for count in splice_endpoint_counts.values())
    existing_feeder_splices = sum(
        _existing_feeder_splice_count(cable_id, cable_fibers, cable_classes, endpoints)
        for cable_id, endpoints in existing_feeder_endpoints.items()
    )
    fiber_splices += existing_feeder_splices
    real_pigtails = sum(
        _pigtail_material_count(cable_ids, cable_classes)
        for cable_ids in pigtail_endpoint_cables.values()
    )
    adapter_required_pigtails = sum(
        _pigtail_material_count(cable_ids, cable_classes)
        for cable_ids in adapter_endpoint_cables.values()
    )

    return {
        "pigtail_splices": real_pigtails,
        "pigtail_splices_raw": raw_pigtails,
        "adapter_required_pigtails": adapter_required_pigtails,
        "existing_feeder_splice_connections": existing_feeder_splices,
        "fiber_splice_connections": fiber_splices,
        "splice_sleeves": fiber_splices + raw_pigtails,
    }


def _add_physical_splice_endpoint(
    endpoint_counts: dict[tuple[str, str, str], int],
    existing_feeder_endpoints: dict[str, set[tuple[str, str, str]]],
    cable_id: str,
    node: object,
    device: object,
    port: object,
) -> None:
    if normalize_key(cable_id).startswith("okh"):
        existing_feeder_endpoints[cable_id].add(_port_key(node, device, port))
        return
    endpoint_counts[_port_key(node, device, port)] += 1


def _existing_feeder_splice_count(
    cable_id: str,
    cable_fibers: dict[str, int | None],
    cable_classes: dict[str, str],
    endpoints: set[tuple[str, str, str]] | None = None,
) -> int:
    explicit_count = len(endpoints or ())
    if explicit_count and any("/zs" in endpoint[0] for endpoint in endpoints or ()):
        return explicit_count
    fibers = cable_fibers.get(cable_id)
    material_class = cable_classes.get(cable_id, "")
    if fibers:
        if material_class.startswith("MIKROKABEL"):
            return max(explicit_count, 1, math.ceil(fibers / 3))
        return max(explicit_count, 1, math.ceil(fibers / 2))
    return max(explicit_count, 1)


def _pigtail_material_count(cable_ids: list[str], cable_classes: dict[str, str]) -> int:
    if len(cable_ids) <= 1:
        return len(cable_ids)
    duplicate_backbone = sum(1 for cable_id in cable_ids if cable_classes.get(cable_id) == "ADSS_36J")
    return max(1, len(cable_ids) - duplicate_backbone)


def _read_oap_adapter_ports(con: sqlite3.Connection, table: str | None) -> set[tuple[str, str, str]]:
    if not table:
        return set()
    columns = _columns(con, table)
    node_col = _column(columns, "wezel")
    device_col = _column(columns, "oznaczenie_urzadzenia")
    port_col = _column(columns, "nr_portu")
    model_col = _column(columns, "model_portu")
    if not node_col or not device_col or not port_col or not model_col:
        return set()

    ports: set[tuple[str, str, str]] = set()
    query = f"select [{node_col}] as node, [{device_col}] as device, [{port_col}] as port, [{model_col}] as model from [{table}]"
    for row in con.execute(query):
        model = normalize_key(row["model"])
        if "oap" in model and "adapter" in model:
            ports.add(_port_key(row["node"], row["device"], row["port"]))
    return ports


def _port_key(node: object, device: object, port: object) -> tuple[str, str, str]:
    return (normalize_key(node), normalize_key(device), normalize_key(port))


def _is_real_pigtail_endpoint(
    node: object,
    device: object,
    port: object,
    oap_adapter_ports: set[tuple[str, str, str]],
) -> bool:
    if not oap_adapter_ports:
        return True
    return _port_key(node, device, port) in oap_adapter_ports


def _is_splice_connection(value: object) -> bool:
    return "spaw" in normalize_key(value)


def _read_pigtail_splice_count(con: sqlite3.Connection, table: str | None) -> int:
    if not table:
        return 0
    columns = _columns(con, table)
    start_col = _column(columns, "pigtail_pocz_spaw")
    end_col = _column(columns, "pigtail_kon_spaw")
    if not start_col and not end_col:
        return 0
    select_parts = [
        f"[{start_col}] as start_splice" if start_col else "'' as start_splice",
        f"[{end_col}] as end_splice" if end_col else "'' as end_splice",
    ]
    count = 0
    for row in con.execute(f"select {', '.join(select_parts)} from [{table}]"):
        if normalize_text(row["start_splice"]):
            count += 1
        if normalize_text(row["end_splice"]):
            count += 1
    return count


def _read_oap_pole_counts(
    con: sqlite3.Connection,
    device_table: str | None,
    pole_tables: list[str | None],
    used_poles: list[PoleUse],
    tolerance_m: float = 2.0,
) -> tuple[int, int]:
    if not device_table or not used_poles:
        return 0, 0
    energy_poles = _energy_pole_ids(con, pole_tables)
    columns = _columns(con, device_table)
    geom_col = _column(columns, "geom")
    model_col = _column(columns, "model_urzadzenia")
    if not geom_col or not model_col:
        return 0, 0

    oap_on_used = 0
    oap_on_energy = 0
    for row in con.execute(f"select [{geom_col}] as geom, [{model_col}] as model from [{device_table}]"):
        material_class = classify_material_name(row["model"])
        if not material_class.startswith("OAP"):
            continue
        point = read_gpkg_point(row["geom"])
        if not point:
            continue
        nearest = min(
            ((math.hypot(point[0] - pole.x, point[1] - pole.y), pole) for pole in used_poles),
            key=lambda item: item[0],
            default=None,
        )
        if not nearest or nearest[0] > tolerance_m:
            continue
        oap_on_used += 1
        if nearest[1].pole_id in energy_poles:
            oap_on_energy += 1
    return oap_on_used, oap_on_energy


def _count_used_energy_poles(
    con: sqlite3.Connection,
    pole_tables: list[str | None],
    used_poles: list[PoleUse],
) -> int:
    if not used_poles:
        return 0
    energy_poles = _energy_pole_ids(con, pole_tables)
    return sum(1 for pole in used_poles if pole.pole_id in energy_poles)


def _read_oap_hdpe_uv_pipe_counts(
    con: sqlite3.Connection,
    device_table: str | None,
    cable_tables: list[str | None],
    pole_tables: list[str | None],
    used_poles: list[PoleUse],
    tolerance_m: float = 2.0,
) -> dict[str, object]:
    empty = {
        "oap_hdpe_uv_pipe_count": 0,
        "oap_hdpe_uv_oap_count": 0,
        "oap_hdpe_uv_energy_pipe_count": 0,
        "oap_hdpe_uv_details": [],
    }
    if not device_table or not used_poles:
        return empty

    energy_poles = _energy_pole_ids(con, pole_tables)
    oaps = _read_oap_nodes_on_used_poles(con, device_table, used_poles, energy_poles, tolerance_m)
    if not oaps:
        return empty

    connections = _read_oap_cable_connections(con, cable_tables, {oap["node"] for oap in oaps})
    pipe_count = 0
    energy_pipe_count = 0
    oap_count = 0
    details: list[str] = []
    for oap in oaps:
        node = str(oap["node"])
        node_connections = connections.get(node, {})
        underground_cables = [
            cable_id
            for cable_id, info in node_connections.items()
            if str(info["material_class"]).startswith("MIKROKABEL")
        ]
        dac_drops = [
            cable_id
            for cable_id, info in node_connections.items()
            if _is_dac_drop_class(str(info["material_class"]))
        ]
        if not underground_cables and not dac_drops:
            continue

        node_pipe_count = max(1, len(underground_cables))
        if len(dac_drops) > 5:
            node_pipe_count = max(node_pipe_count, 2)

        oap_count += 1
        pipe_count += node_pipe_count
        if bool(oap["is_energy"]):
            energy_pipe_count += node_pipe_count
        details.append(
            f"{node}: {node_pipe_count} rury, mikrokable {len(underground_cables)}, DAC {len(dac_drops)}"
        )

    return {
        "oap_hdpe_uv_pipe_count": pipe_count,
        "oap_hdpe_uv_oap_count": oap_count,
        "oap_hdpe_uv_energy_pipe_count": energy_pipe_count,
        "oap_hdpe_uv_details": details,
    }


def _read_oap_nodes_on_used_poles(
    con: sqlite3.Connection,
    device_table: str,
    used_poles: list[PoleUse],
    energy_poles: set[str],
    tolerance_m: float,
) -> list[dict[str, object]]:
    columns = _columns(con, device_table)
    geom_col = _column(columns, "geom")
    model_col = _column(columns, "model_urzadzenia")
    node_col = _column(columns, "wezel")
    if not geom_col or not model_col or not node_col:
        return []

    oaps: list[dict[str, object]] = []
    query = f"select [{geom_col}] as geom, [{model_col}] as model, [{node_col}] as node from [{device_table}]"
    for row in con.execute(query):
        if not classify_material_name(row["model"]).startswith("OAP"):
            continue
        point = read_gpkg_point(row["geom"])
        if not point:
            continue
        nearest = min(
            ((math.hypot(point[0] - pole.x, point[1] - pole.y), pole) for pole in used_poles),
            key=lambda item: item[0],
            default=None,
        )
        if not nearest or nearest[0] > tolerance_m:
            continue
        pole = nearest[1]
        oaps.append(
            {
                "node": normalize_text(row["node"]),
                "model": normalize_text(row["model"]),
                "pole_id": pole.pole_id,
                "is_energy": pole.pole_id in energy_poles,
            }
        )
    return oaps


def _read_oap_cable_connections(
    con: sqlite3.Connection,
    tables: list[str | None],
    oap_nodes: set[str],
) -> dict[str, dict[str, dict[str, object]]]:
    connections: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    if not oap_nodes:
        return connections

    for table in [name for name in tables if name]:
        columns = _columns(con, table)
        cable_col = _column(columns, "odcinek_kabla") or _column(columns, "id") or columns[0]
        model_col = _column(columns, "model_kabla")
        from_col = _column(columns, "od")
        to_col = _column(columns, "do")
        type_col = _column(columns, "typ_elementu")
        if not from_col or not to_col:
            continue

        model_expr = f"[{model_col}]" if model_col else "''"
        type_expr = f"[{type_col}]" if type_col else "''"
        query = (
            "select "
            f"[{cable_col}] as cable_id, "
            f"{model_expr} as model, "
            f"[{from_col}] as from_node, "
            f"[{to_col}] as to_node, "
            f"{type_expr} as element_type "
            f"from [{table}]"
        )
        for row in con.execute(query):
            cable_id = normalize_text(row["cable_id"])
            if not cable_id:
                continue
            material_class = classify_material_name(row["model"])
            for node_value in (row["from_node"], row["to_node"]):
                node = normalize_text(node_value)
                if node not in oap_nodes:
                    continue
                info = connections[node].setdefault(
                    cable_id,
                    {
                        "material_class": material_class,
                        "types": set(),
                    },
                )
                info["types"].add(normalize_key(row["element_type"]))
    return connections


def _is_dac_drop_class(material_class: str) -> bool:
    return material_class.startswith("DAC")


def _energy_pole_ids(con: sqlite3.Connection, tables: list[str | None]) -> set[str]:
    energy_ids: set[str] = set()
    for table in [name for name in tables if name]:
        columns = _columns(con, table)
        pole_col = _column(columns, "identyfikator_obiektu")
        owner_col = _column(columns, "wlasciciel")
        kind_col = _column(columns, "slup_rodzaj")
        type_col = _column(columns, "typ_elementu")
        if not pole_col:
            continue
        owner_expr = f"[{owner_col}]" if owner_col else "''"
        kind_expr = f"[{kind_col}]" if kind_col else "''"
        type_expr = f"[{type_col}]" if type_col else "''"
        query = (
            "select "
            f"[{pole_col}] as pole_id, "
            f"{owner_expr} as owner, "
            f"{kind_expr} as pole_kind, "
            f"{type_expr} as element_type "
            f"from [{table}]"
        )
        for row in con.execute(query):
            if not _is_real_pole_candidate(row["element_type"], "", row["pole_id"]):
                continue
            text = normalize_key(f"{row['owner']} {row['pole_kind']}")
            if any(token in text for token in ["pge", "energetycz", "enea", "energa", "tauron"]):
                energy_ids.add(normalize_text(row["pole_id"]))
    return energy_ids
