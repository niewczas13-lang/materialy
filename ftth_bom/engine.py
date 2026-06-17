from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from ftth_bom.bell_history import load_bell_history
from ftth_bom.catalog import Catalog
from ftth_bom.gpkg_reader import read_gpkg_project
from ftth_bom.models import AnalysisResult, Issue, MaterialPreference, OrderRow, ProjectData, SapRow
from ftth_bom.preferences import PreferenceStore
from ftth_bom.rules import is_orderable_material_class, normalize_qty, preferred_category, round_order_length, round_order_length_with_reserve
from ftth_bom.staging import staged_gpkg_path


ProgressCallback = Callable[[tuple[int, str]], None]


def run_analysis(
    gpkg_path: str | Path,
    catalog_path: str | Path,
    bell_path: str | Path,
    task_name: str | None = None,
    preferences_db: str | Path | None = None,
    local_copy: bool = False,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    original_gpkg_path = Path(gpkg_path)
    if local_copy:
        _report_progress(progress, 5, "Kopiowanie GPKG do lokalnego temp")
    with staged_gpkg_path(original_gpkg_path, enabled=local_copy) as analysis_gpkg_path:
        _report_progress(progress, 15, "Czytanie GPKG")
        project = read_gpkg_project(analysis_gpkg_path)
    project.source_path = original_gpkg_path
    _report_progress(progress, 35, "GPKG wczytane")

    _report_progress(progress, 45, "Czytanie historii BELL")
    history = load_bell_history(bell_path)
    _report_progress(progress, 60, "Budowa bazy preferencji")
    store = PreferenceStore.from_history(history, sqlite_path=preferences_db)
    _report_progress(progress, 70, "Czytanie katalogu SAP")
    catalog = Catalog.load(catalog_path)
    task_name = task_name or original_gpkg_path.stem

    order_rows: list[OrderRow] = []
    issues: list[Issue] = []
    _report_progress(progress, 80, "Przeliczanie BOM")

    exact_history_count = sum(1 for row in history if any(f in row.fx.upper() for f in project.f_numbers))
    token_history_count = sum(
        1
        for row in history
        if any(token.lower() in row.search_text for token in (token.lower() for token in project.project_tokens))
    )
    issues.append(
        Issue(
            topic="Historia BELL",
            description=(
                f"Diagnostyka historii: {exact_history_count} wierszy po wykrytym F/X, "
                f"{token_history_count} wierszy po tokenach OPP/OSD. "
                "Dobór materiałów w BOM nie zakłada, że bieżące F/X istnieje w BELL."
            ),
            recommendation="BELL służy jako baza nauczonych preferencji materiałowych dla klas z GPKG, a nie jako źródło pozycji bieżącego zadania.",
        )
    )

    for summary in project.cable_summary:
        if summary.material_class == "INNE":
            continue
        if not is_orderable_material_class(summary.material_class):
            issues.append(
                Issue(
                    topic="Pominieto ADSS 2J",
                    description=(
                        f"GPKG zawiera {summary.sections} odcinkow ADSS 2J "
                        f"({summary.route_m:g} m trasy), ale ta klasa wyglada jak kable uslugowe/drop."
                    ),
                    recommendation="Nie dodano ich do zamowienia materialow; potwierdz tylko, jesli ten etap ma obejmowac dropy abonenckie.",
                )
            )
            continue
        length = summary.install_m or summary.route_m or summary.optical_m
        if length <= 0:
            issues.append(
                Issue(
                    topic=f"Kabel {summary.model}",
                    description="Brak długości instalacyjnej/trasowej w danych GPKG.",
                    recommendation="Potwierdź długość z projektantem przed zamówieniem.",
                )
            )
            continue
        qty_order = round_order_length_with_reserve(length)
        basis = (
            f"PW: {summary.sections} unikalnych odcinków, "
            f"instalacyjna {summary.install_m:g} m, trasa {summary.route_m:g} m."
        )
        preference = store.recommend(summary.material_class, project.f_numbers, project.project_tokens)
        order_rows.append(
            _make_order_row(
                order_rows,
                material_class=summary.material_class,
                preference=preference,
                catalog=catalog,
                qty_pw=f"{length:g} m",
                qty_order=qty_order,
                basis=basis,
                notes=f"Model z PW: {summary.model}; dlugosc do zamowienia = PW x 1,03, potem zaokraglenie.",
                issues=issues,
            )
        )

    for device in project.devices:
        if device.material_class == "INNE" or not is_orderable_material_class(device.material_class):
            continue
        preference = store.recommend(device.material_class, project.f_numbers, project.project_tokens)
        order_rows.append(
            _make_order_row(
                order_rows,
                material_class=device.material_class,
                preference=preference,
                catalog=catalog,
                qty_pw=device.count,
                qty_order=device.count,
                basis=f"PW: {device.count} x {device.model} w warstwie Urządzenia Pasywne.",
                notes=f"Węzeł/przykład: {device.node}",
                issues=issues,
            )
        )

    handled_takeoff_classes = {
        row.material_class
        for row in order_rows
        if row.material_class.startswith(("OAP", "SPLITTER", "MUFA", "PSB", "SUS"))
    }
    for item in project.material_takeoff:
        if item.material_class in handled_takeoff_classes:
            continue
        if not item.material_class.startswith(("MIKRORURKA", "HDPE")):
            continue
        if item.unit == "m":
            qty_pw = f"{item.length_m:g} m"
            qty_order = round_order_length_with_reserve(item.length_m)
        else:
            qty_pw = item.count
            qty_order = item.count
        preference = store.recommend(item.material_class, project.f_numbers, project.project_tokens)
        order_rows.append(
            _make_order_row(
                order_rows,
                material_class=item.material_class,
                preference=preference,
                catalog=catalog,
                qty_pw=qty_pw,
                qty_order=qty_order,
                basis=(
                    f"Skaner GPKG: warstwa {item.source_layer}, {item.count} pozycji, "
                    f"nazwa/model: {item.name}."
                ),
                notes=f"Przyklady: {'; '.join(item.examples[:5])}",
                issues=issues,
            )
        )

    _add_accessory_rows(order_rows, issues, project, store, catalog)
    _report_progress(progress, 90, "Scalanie pozycji SAP")
    order_rows = _merge_order_rows(order_rows)
    sap_rows = [
        SapRow(row.sap, row.name, row.unit, row.qty_order, row.status)
        for row in order_rows
        if row.sap and row.qty_order not in ("", 0, 0.0)
    ]

    return AnalysisResult(
        task_name=task_name,
        project=project,
        order_rows=order_rows,
        issues=issues,
        preferences=[pref for pref in store.top_preferences() if is_orderable_material_class(pref.material_class)],
        sap_rows=sap_rows,
    )


def _report_progress(progress: ProgressCallback | None, percent: int, message: str) -> None:
    if progress is not None:
        progress((percent, message))


def _make_order_row(
    existing: list[OrderRow],
    material_class: str,
    preference: MaterialPreference | None,
    catalog: Catalog,
    qty_pw: object,
    qty_order: object,
    basis: str,
    notes: str,
    issues: list[Issue],
) -> OrderRow:
    status = "ZAMÓWIĆ"
    sap = preference.sap if preference else ""
    name = preference.name if preference else material_class
    unit = preference.unit if preference else ""
    supplier = ""
    match_level = preference.match_level if preference else "missing"

    if not preference:
        status = "DO POTWIERDZENIA"
        issues.append(
            Issue(
                topic=f"Brak preferencji {material_class}",
                description="Baza BELL nie wskazała jednoznacznego materiału dla tej klasy.",
                recommendation="Wybierz SAP z katalogu inwestora i pozwól bazie nauczyć się go z kolejnych zamówień.",
            )
        )
    else:
        item = catalog.get(sap)
        if item:
            name = item.name or name
            if material_class in {"TASMA_STALOWA", "TASMA_STALOWA_10MM", "KLAMRA_TASMY"} or not unit:
                unit = item.unit or unit
            supplier = " | ".join(part for part in [item.supplier, item.supplier_position] if part)
        else:
            status = "DO POTWIERDZENIA"
            issues.append(
                Issue(
                    topic=f"SAP poza katalogiem: {sap}",
                    description=f"Historia BELL wskazała {sap} ({preference.name}), ale nie znaleziono go w katalogu.",
                    recommendation="Sprawdź aktualny katalog inwestora lub wybierz dopuszczony zamiennik.",
                )
            )

    if match_level in {"project_token", "global", "missing"}:
        status = "DO POTWIERDZENIA"

    return OrderRow(
        lp=len(existing) + 1,
        status=status,
        category=preferred_category(material_class),
        sap=sap,
        name=name,
        unit=unit,
        qty_pw=str(qty_pw),
        qty_order=normalize_qty(qty_order) if isinstance(qty_order, (int, float)) else qty_order,
        supplier=supplier,
        basis=f"{basis} Dobór: {match_level}.",
        notes=notes,
        material_class=material_class,
        match_level=match_level,
    )


def _rule_preference(
    material_class: str,
    fallback_sap: str,
    project: ProjectData,
    store: PreferenceStore,
    catalog: Catalog,
) -> MaterialPreference | None:
    preference = store.recommend(material_class, project.f_numbers, project.project_tokens)
    if preference and preference.match_level not in {"global", "project_token", "missing"}:
        return preference
    item = catalog.get(fallback_sap)
    if not item:
        return preference
    return MaterialPreference(
        material_class=material_class,
        sap=item.sap,
        name=item.name,
        unit=item.unit,
        total_qty=0,
        occurrences=0,
        fx_count=0,
        examples=("katalog/regula",),
        match_level="rule_catalog",
        score=1.0,
    )


def _add_accessory_rows(
    order_rows: list[OrderRow],
    issues: list[Issue],
    project: ProjectData,
    store: PreferenceStore,
    catalog: Catalog,
) -> None:
    dac_count = sum(1 for edge in project.cable_edges if edge.material_class.startswith("DAC"))
    if dac_count:
        order_rows.append(
            _make_order_row(
                order_rows,
                "KAPTUREK_DAC",
                store.recommend("KAPTUREK_DAC", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=dac_count,
                qty_order=dac_count,
                basis="Reguła: 1 kapturek termokurczliwy na każdy kabel DAC, jedna strona.",
                notes="Kontrola z promptu FTTH.",
                issues=issues,
            )
        )

    oap_count = _device_count(project, lambda material_class: material_class.startswith("OAP"))
    pigtail_splices = int(project.metadata.get("pigtail_splices") or 0)
    adapter_required_pigtails = int(project.metadata.get("adapter_required_pigtails") or 0)
    if pigtail_splices:
        order_rows.append(
            _make_order_row(
                order_rows,
                "PIGTAIL_SC_APC",
                store.recommend("PIGTAIL_SC_APC", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=pigtail_splices,
                qty_order=pigtail_splices,
                basis="Warstwa Wlokna: realne pigtail_pocz_spaw/pigtail_kon_spaw po deduplikacji portow.",
                notes="Pigtail jest liczony takze w OAP, bo OAP ma adaptery fabryczne, ale pigtail trzeba domowic.",
                issues=issues,
            )
        )
        if adapter_required_pigtails:
            order_rows.append(
                _make_order_row(
                    order_rows,
                    "ADAPTER_SC_APC",
                    _rule_preference("ADAPTER_SC_APC", "2200005618", project, store, catalog),
                    catalog,
                    qty_pw=adapter_required_pigtails,
                    qty_order=adapter_required_pigtails,
                    basis="Warstwa Wlokna/Porty Pasywne: adaptery SC/APC tylko dla pigtaili poza portami OAP Adapter Port.",
                    notes="OAP na slupie jest wyposazony w adaptery, wiec tam adapterow nie zamawiamy.",
                    issues=issues,
                )
            )
    elif project.hh_total:
        feeder = max(1, (project.hh_total + 63) // 64)
        pigtail_qty = project.hh_total + feeder
        adapter_classes = [] if oap_count else ["ADAPTER_SC_APC"]
        for material_class in ["PIGTAIL_SC_APC", *adapter_classes]:
            order_rows.append(
                _make_order_row(
                    order_rows,
                    material_class,
                    store.recommend(material_class, project.f_numbers, project.project_tokens),
                    catalog,
                    qty_pw=pigtail_qty,
                    qty_order=pigtail_qty,
                    basis=f"Reguła OPP/OAP: HH {project.hh_total} + dosył {feeder}.",
                    notes="Jeśli OAP ma adaptery fabryczne, adaptery dodatkowe potwierdzić.",
                    issues=issues,
                )
            )

    splice_qty = int(project.metadata.get("splice_sleeves") or 0)
    if not splice_qty and project.hh_total:
        splice_qty = project.hh_total + max(1, (project.hh_total + 63) // 64)
    if splice_qty:
        order_rows.append(
            _make_order_row(
                order_rows,
                "OSLONKA_SPAWU",
                store.recommend("OSLONKA_SPAWU", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=splice_qty,
                qty_order=splice_qty,
                basis="Warstwa Wlokna: realne spawy termiczne + pigtail-spaw na adapterach OAP.",
                notes="Nie doliczono liczby odcinkow kabli jako sztucznych spawow.",
                issues=issues,
            )
        )

    psb_count = _device_count(project, lambda material_class: material_class == "PSB_H_144")
    if psb_count:
        order_rows.append(
            _make_order_row(
                order_rows,
                "FUNDAMENT_PSB_H",
                _rule_preference("FUNDAMENT_PSB_H", "2200008667", project, store, catalog),
                catalog,
                qty_pw=psb_count,
                qty_order=psb_count,
                basis=f"Regula: fundament prefabrykowany dla kazdej PSB-H ({psb_count} szt).",
                notes="Potwierdzone na DPW_F03013604.",
                issues=issues,
            )
        )

    passive_device_count = sum(device.count for device in project.devices if device.material_class != "INNE")
    if passive_device_count:
        label_qty = passive_device_count * 2
        order_rows.append(
            _make_order_row(
                order_rows,
                "NAKLEJKA_SI_50X72",
                _rule_preference("NAKLEJKA_SI_50X72", "2200029709", project, store, catalog),
                catalog,
                qty_pw=f"{passive_device_count} urzadzen pasywnych x 2",
                qty_order=label_qty,
                basis="Regula: 2 naklejki S-I 50x72 mm na urzadzenie pasywne w PW.",
                notes="Liczone z warstwy Urzadzenia Pasywne.",
                issues=issues,
            )
        )

    enclosure_count = _device_count(project, lambda material_class: material_class in {"PSB_H_144", "SUS_PH_S"})
    if enclosure_count:
        order_rows.append(
            _make_order_row(
                order_rows,
                "ZAMEK_ABLOY",
                _rule_preference("ZAMEK_ABLOY", "2200029956", project, store, catalog),
                catalog,
                qty_pw=enclosure_count,
                qty_order=enclosure_count,
                basis="Regula: 1 zamek ABLOY CL704B S-I Centrum na PSB/SUS.",
                notes="OAP i muf napowietrznych nie wyposazamy w zamki ABLOY.",
                issues=issues,
            )
        )

    przecisk_length = float(project.metadata.get("przecisk_length_m") or 0)
    if przecisk_length:
        foam_qty = max(1, math.ceil(przecisk_length / 100) + 1)
        order_rows.append(
            _make_order_row(
                order_rows,
                "PIANKA_MD",
                _rule_preference("PIANKA_MD", "2200000503", project, store, catalog),
                catalog,
                qty_pw=f"{przecisk_length:g} m przecisku / 100 m + 1 zapas",
                qty_order=foam_qty,
                basis="Regula klienta: srednio 1 pianka MD+ 310 ml na 100 m przecisku/wykopu, plus 1 szt zapasu.",
                notes="Dlugosc PRZECISK liczona z geometrii GPKG.",
                issues=issues,
            )
        )

    micro_12_length = sum(
        item.length_m for item in project.material_takeoff if item.material_class == "MIKRORURKA_12_8" and item.unit == "m"
    )
    if micro_12_length:
        connector_qty = max(1, round(micro_12_length / 50))
        order_rows.append(
            _make_order_row(
                order_rows,
                "ZLACZKA_MIKRO_12",
                _rule_preference("ZLACZKA_MIKRO_12", "2200008194", project, store, catalog),
                catalog,
                qty_pw=f"{micro_12_length:g} m mikrorurki 12/8 / 50 m",
                qty_order=connector_qty,
                basis="Regula klienta: ok. 1 zlaczka prosta na 50 m mikrorurki 12/8.",
                notes="Jesli projekt uzywa 14/10, dobrac odpowiednia zlaczke 14 mm.",
                issues=issues,
            )
        )

    aerial_support_edges = [
        edge for edge in project.cable_edges if edge.material_class.startswith("ADSS") and edge.material_class != "ADSS_2J"
    ]
    if project.used_poles:
        mounting_poles = _aerial_mounting_pole_count(project)
        equipment_poles = min(int(project.metadata.get("oap_on_used_poles") or 0), mounting_poles)
        transit_poles = max(0, mounting_poles - equipment_poles)
        uv_pipe_count = int(project.metadata.get("oap_hdpe_uv_pipe_count") or 0)
        uv_energy_pipe_count = int(project.metadata.get("oap_hdpe_uv_energy_pipe_count") or 0)
        hooks = mounting_poles * 2
        order_rows.append(
            _make_order_row(
                order_rows,
                "UCHWYT_ODCIAGOWY",
                store.recommend("UCHWYT_ODCIAGOWY", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=hooks,
                qty_order=hooks,
                basis="Reguła kontrolna: 2 haki/uchwyty odciągowe na odcinek napowietrzny ADSS w MVP.",
                notes="Liczbę słupów i uchwytów przelotowych potwierdzić z warstwą słupów.",
                issues=issues,
            )
        )
        order_rows[-1].basis = (
            "Geometria: 2 odciagi na slup mocowania ADSS "
            f"({mounting_poles} slupy x 2 = {hooks} szt., "
            f"tolerancja {project.metadata.get('used_poles_tolerance_m', 2.0)} m). "
            f"Dobor: {order_rows[-1].match_level}."
        )
        order_rows[-1].notes = "Szczegolowa lista slupow jest w arkuszu Slupy uzyte."

        order_rows.append(
            _make_order_row(
                order_rows,
                "HAK_UNIWERSALNY",
                store.recommend("HAK_UNIWERSALNY", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=hooks,
                qty_order=hooks,
                basis=f"Geometria: 2 haki uniwersalne na slup mocowania ADSS ({mounting_poles} x 2).",
                notes="Warstwy koncepcyjne K_* sa pominiete.",
                issues=issues,
            )
        )

        if uv_pipe_count:
            uv_hdpe_m = uv_pipe_count * 5
            order_rows.append(
                _make_order_row(
                    order_rows,
                    "HDPE_UV_40",
                    _rule_preference("HDPE_UV_40", "2200015460", project, store, catalog),
                    catalog,
                    qty_pw=f"{uv_hdpe_m} m ({uv_pipe_count} rury przy OAP/OSD na slupie x 5 m)",
                    qty_order=uv_hdpe_m,
                    basis="Regula: OAP/OSD na slupie z kablem DAC albo mikrokablem doziemnym wymaga rury HDPE-UV 40.",
                    notes="Gdy z OAP/OSD wychodzi ponad 5 kabli DAC albo kabel wraca do ziemi, liczba rur jest dublowana.",
                    issues=issues,
                )
            )

        tape_m = equipment_poles * 6 + transit_poles * 3 + uv_pipe_count * 4
        tape_rolls = max(1, math.ceil(tape_m / 50)) if tape_m else 0
        uv_tape_note = f" + {uv_pipe_count} rur UV x 4 m" if uv_pipe_count else ""
        order_rows.append(
            _make_order_row(
                order_rows,
                "TASMA_STALOWA",
                store.recommend("TASMA_STALOWA", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=(
                    f"{tape_m} m ({equipment_poles} slupow z OAP/mufa x 6 m + "
                    f"{transit_poles} przelotowych x 3 m{uv_tape_note})"
                ),
                qty_order=tape_rolls,
                basis="Regula: tasma 0,7 m na zacisk; 8 zaciskow przy OAP/mufie, 4 zaciski na slup przelotowy.",
                notes="Zamowienie w rolkach po 50 m wg katalogu.",
                issues=issues,
            )
        )

        clamp_qty = equipment_poles * 8 + transit_poles * 4 + uv_pipe_count * 4 + 5
        clamp_packs = max(1, math.ceil(clamp_qty / 100)) if clamp_qty else 0
        uv_clamp_note = f" + {uv_pipe_count} rur UV x 4" if uv_pipe_count else ""
        order_rows.append(
            _make_order_row(
                order_rows,
                "KLAMRA_TASMY",
                store.recommend("KLAMRA_TASMY", project.f_numbers, project.project_tokens),
                catalog,
                qty_pw=(
                    f"{clamp_qty} szt ({equipment_poles} slupow z OAP/mufa x 8 + "
                    f"{transit_poles} przelotowych x 4{uv_clamp_note} + 5 awaryjnych)"
                ),
                qty_order=clamp_packs,
                basis="Regula: klamry do tasmy 20 mm, z zapasem awaryjnym 5 szt.",
                notes="Zamowienie w opakowaniach po 100 szt wg katalogu.",
                issues=issues,
            )
        )

        energy_poles = int(project.metadata.get("used_energy_poles") or 0)
        if energy_poles:
            nameplate_points = math.ceil(energy_poles / 3)
            tape_10mm_m = round(nameplate_points * 2 * 0.7, 1)
            tape_10mm_rolls = max(1, math.ceil(tape_10mm_m / 50))
            order_rows.append(
                _make_order_row(
                    order_rows,
                    "TASMA_STALOWA_10MM",
                    _rule_preference("TASMA_STALOWA_10MM", "2200003733", project, store, catalog),
                    catalog,
                    qty_pw=(
                        f"{tape_10mm_m:g} m "
                        f"({energy_poles} slupow EN / 3 = {nameplate_points} punktow x 2 x 0,7 m)"
                    ),
                    qty_order=tape_10mm_rolls,
                    basis="Regula: tasma stalowa 10 mm na tabliczki znamionowe, 2 x 0,7 m co trzeci slup EN.",
                    notes="Zamowienie w rolkach po 50 m wg katalogu.",
                    issues=issues,
                )
            )

        energy_oap = int(project.metadata.get("oap_on_energy_poles") or 0)
        if energy_oap:
            order_rows.append(
                _make_order_row(
                    order_rows,
                    "DYSTANS_OAP",
                    store.recommend("DYSTANS_OAP", project.f_numbers, project.project_tokens),
                    catalog,
                    qty_pw=f"{energy_oap} OAP na slupach EN x 1",
                    qty_order=energy_oap,
                    basis="Geometria: 1 dystans na OAP tylko dla OAP osadzonych na slupach energetycznych.",
                    notes="Jesli komplet stelaza zawiera dystans, pozycje skorygowac przed zamowieniem.",
                    issues=issues,
                )
            )

        if uv_energy_pipe_count:
            dystans_hdpe_qty = uv_energy_pipe_count * 4
            order_rows.append(
                _make_order_row(
                    order_rows,
                    "DYSTANS_HDPE_UV",
                    _rule_preference("DYSTANS_HDPE_UV", "2200028483", project, store, catalog),
                    catalog,
                    qty_pw=f"{uv_energy_pipe_count} rur HDPE-UV na slupach EN x 4",
                    qty_order=dystans_hdpe_qty,
                    basis="Regula: 4 uchwyty dystansowe rury HDPE-UV na kazda rure przy OAP na slupie energetycznym.",
                    notes="Domyslnie dobrano wariant na slup zelbetowy; slup wirowy (SAP 2200028484) potwierdzic w terenie.",
                    issues=issues,
                )
            )

    if aerial_support_edges and not project.used_poles:
        issues.append(
            Issue(
                topic="Osprzet napowietrzny",
                description=(
                    "W projekcie sa kable ADSS, ale automat nie dopasowal ich geometrii "
                    "do warstw slupow Obiekty/Plan_Obiekty/_Obiekty."
                ),
                recommendation="Sprawdz geometrie slupow lub zwieksz tolerancje dopasowania przed zamowieniem osprzetu.",
            )
        )


def _device_count(project: ProjectData, predicate) -> int:
    return sum(device.count for device in project.devices if predicate(device.material_class))


def _aerial_mounting_pole_count(project: ProjectData) -> int:
    existing_network_poles = [pole for pole in project.used_poles if pole.source_layer == "_Obiekty"]
    return len(existing_network_poles) if existing_network_poles else len(project.used_poles)


def _merge_order_rows(rows: list[OrderRow]) -> list[OrderRow]:
    merged: dict[tuple[str, str, str, str], OrderRow] = {}
    for row in rows:
        key = (row.sap, row.material_class, row.status, row.unit)
        if key not in merged:
            merged[key] = row
            continue
        current = merged[key]
        if isinstance(current.qty_order, (int, float)) and isinstance(row.qty_order, (int, float)):
            current.qty_order = normalize_qty(float(current.qty_order) + float(row.qty_order))
            current.qty_pw = f"{current.qty_pw}; {row.qty_pw}"
            current.basis = f"{current.basis} | {row.basis}"
            current.notes = f"{current.notes} | {row.notes}"
    output = list(merged.values())
    for index, row in enumerate(output, start=1):
        row.lp = index
    return output
