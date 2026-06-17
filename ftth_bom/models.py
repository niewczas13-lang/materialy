from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class HistoryRow:
    fx: str
    target_x: str
    sto: str
    task: str
    sap: str
    name: str
    unit: str
    ordered_qty: float
    status: str
    material_class: str
    all_fx: tuple[str, ...]
    search_text: str


@dataclass(slots=True)
class MaterialPreference:
    material_class: str
    sap: str
    name: str
    unit: str
    total_qty: float
    occurrences: int
    fx_count: int
    examples: tuple[str, ...]
    match_level: str = "global"
    score: float = 0.0


@dataclass(slots=True)
class CableEdge:
    cable_id: str
    model: str
    fibers: int | None
    from_node: str
    to_node: str
    route_m: float
    optical_m: float
    install_m: float
    material_class: str


@dataclass(slots=True)
class CableSummary:
    material_class: str
    model: str
    fibers: int | None
    sections: int
    route_m: float
    optical_m: float
    install_m: float


@dataclass(slots=True)
class DeviceSummary:
    node: str
    element_type: str
    producer: str
    model: str
    object_type: str
    count: int
    material_class: str


@dataclass(slots=True)
class QuantitySummary:
    group: str
    name: str
    count: int
    length_m: float = 0.0


@dataclass(slots=True)
class MaterialTakeoff:
    material_class: str
    name: str
    source_layer: str
    count: int
    length_m: float
    unit: str
    examples: tuple[str, ...] = ()


@dataclass(slots=True)
class PoleUse:
    source_layer: str
    pole_id: str
    model: str
    x: float
    y: float
    matched_cables: tuple[str, ...]
    material_classes: tuple[str, ...]
    distance_m: float


@dataclass(slots=True)
class ProjectData:
    source_path: Path
    f_numbers: list[str]
    project_tokens: list[str]
    hh_total: int
    hh_by_node: list[dict[str, object]]
    cable_edges: list[CableEdge]
    cable_summary: list[CableSummary]
    devices: list[DeviceSummary]
    ducts: list[QuantitySummary]
    reserves: list[QuantitySummary]
    material_takeoff: list[MaterialTakeoff] = field(default_factory=list)
    used_poles: list[PoleUse] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogItem:
    sap: str
    name: str
    supplier: str
    supplier_position: str
    supplier_description: str
    unit: str
    category: str


@dataclass(slots=True)
class OrderRow:
    lp: int
    status: str
    category: str
    sap: str
    name: str
    unit: str
    qty_pw: str
    qty_order: float | int | str
    supplier: str
    basis: str
    notes: str
    material_class: str
    match_level: str


@dataclass(slots=True)
class Issue:
    topic: str
    description: str
    recommendation: str


@dataclass(slots=True)
class SapRow:
    sap: str
    name: str
    unit: str
    qty_order: float | int | str
    status: str


@dataclass(slots=True)
class AnalysisResult:
    task_name: str
    project: ProjectData
    order_rows: list[OrderRow]
    issues: list[Issue]
    preferences: list[MaterialPreference]
    sap_rows: list[SapRow]
    xlsx_path: Path | None = None
    pdf_path: Path | None = None
