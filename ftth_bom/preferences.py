from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from ftth_bom.models import HistoryRow, MaterialPreference
from ftth_bom.rules import normalize_match


class PreferenceStore:
    def __init__(self, rows: list[HistoryRow], preferences: list[MaterialPreference]) -> None:
        self.rows = rows
        self.preferences = preferences

    @classmethod
    def from_history(cls, rows: list[HistoryRow], sqlite_path: str | Path | None = None) -> "PreferenceStore":
        store = cls(rows=rows, preferences=_build_global_preferences(rows))
        if sqlite_path is not None:
            store.save_sqlite(sqlite_path)
        return store

    def recommend(
        self,
        material_class: str,
        f_numbers: list[str] | tuple[str, ...] | None = None,
        project_tokens: list[str] | tuple[str, ...] | None = None,
        use_context: bool = False,
    ) -> MaterialPreference | None:
        f_numbers = [f.upper() for f in (f_numbers or [])]
        project_tokens = [normalize_match(token) for token in (project_tokens or []) if token]

        class_rows = [row for row in self.rows if row.material_class == material_class]
        if not class_rows:
            return None

        if use_context:
            exact = [row for row in class_rows if f_numbers and any(f in row.fx.upper() for f in f_numbers)]
            if exact:
                return _best_preference(material_class, exact, "exact_f")

            target = [row for row in class_rows if f_numbers and any(f in row.target_x.upper() for f in f_numbers)]
            if target:
                return _best_preference(material_class, target, "target_x")

            token_rows = [
                row
                for row in class_rows
                if project_tokens and any(token and token in row.search_text for token in project_tokens)
            ]
            if token_rows:
                return _best_preference(material_class, token_rows, "project_token")

        return _best_preference(material_class, class_rows, "learned_class")

    def top_preferences(self, limit: int = 100) -> list[MaterialPreference]:
        return sorted(self.preferences, key=lambda pref: (pref.material_class, -pref.total_qty, pref.sap))[:limit]

    def save_sqlite(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        try:
            con.executescript(
                """
                drop table if exists history_rows;
                drop table if exists material_preferences;
                create table history_rows (
                    fx text,
                    target_x text,
                    sto text,
                    task text,
                    sap text,
                    name text,
                    unit text,
                    ordered_qty real,
                    status text,
                    material_class text,
                    all_fx text,
                    search_text text
                );
                create table material_preferences (
                    material_class text,
                    sap text,
                    name text,
                    unit text,
                    total_qty real,
                    occurrences integer,
                    fx_count integer,
                    examples text
                );
                create table if not exists analysis_runs (
                    id integer primary key autoincrement,
                    created_at text default current_timestamp,
                    task_name text,
                    gpkg_path text,
                    xlsx_path text,
                    pdf_path text
                );
                """
            )
            con.executemany(
                """
                insert into history_rows values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.fx,
                        row.target_x,
                        row.sto,
                        row.task,
                        row.sap,
                        row.name,
                        row.unit,
                        row.ordered_qty,
                        row.status,
                        row.material_class,
                        "|".join(row.all_fx),
                        row.search_text,
                    )
                    for row in self.rows
                ],
            )
            con.executemany(
                """
                insert into material_preferences values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        pref.material_class,
                        pref.sap,
                        pref.name,
                        pref.unit,
                        pref.total_qty,
                        pref.occurrences,
                        pref.fx_count,
                        "|".join(pref.examples),
                    )
                    for pref in self.preferences
                ],
            )
            con.commit()
        finally:
            con.close()


def _build_global_preferences(rows: list[HistoryRow]) -> list[MaterialPreference]:
    grouped: dict[tuple[str, str, str, str], list[HistoryRow]] = defaultdict(list)
    for row in rows:
        if row.material_class == "INNE":
            continue
        grouped[(row.material_class, row.sap, row.name, row.unit)].append(row)
    return [_preference_from_rows(key[0], members, "global") for key, members in grouped.items()]


def _best_preference(material_class: str, rows: list[HistoryRow], match_level: str) -> MaterialPreference:
    grouped: dict[tuple[str, str, str], list[HistoryRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.sap, row.name, row.unit)].append(row)
    preferences = [_preference_from_rows(material_class, members, match_level) for members in grouped.values()]
    return max(preferences, key=lambda pref: (pref.score, pref.total_qty, pref.occurrences))


def _preference_from_rows(material_class: str, rows: list[HistoryRow], match_level: str) -> MaterialPreference:
    first = rows[0]
    total_qty = sum(max(row.ordered_qty, 0) for row in rows)
    fx_values = sorted({fx for row in rows for fx in row.all_fx})
    examples = []
    for row in rows:
        label = row.task or row.sto or row.fx or row.target_x
        if label and label not in examples:
            examples.append(label)
        if len(examples) >= 5:
            break
    level_weight = {
        "exact_f": 10000,
        "target_x": 7000,
        "project_token": 4000,
        "learned_class": 1000,
        "global": 1000,
    }.get(match_level, 0)
    score = level_weight + total_qty + (len(rows) * 25) + (len(fx_values) * 10)
    return MaterialPreference(
        material_class=material_class,
        sap=first.sap,
        name=first.name,
        unit=first.unit,
        total_qty=total_qty,
        occurrences=len(rows),
        fx_count=len(fx_values),
        examples=tuple(examples),
        match_level=match_level,
        score=score,
    )
