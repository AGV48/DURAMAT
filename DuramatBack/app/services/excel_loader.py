from __future__ import annotations

import unicodedata
from typing import Any

from openpyxl import Workbook

from app.services.decision_model import MODEL_CRITERIA


def map_criterion_name(name: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", str(name).strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("₂", "2")
    if any(token in normalized for token in ("co2", "gwp", "emision")):
        return "co2"
    if "energ" in normalized:
        return "energy"
    if any(token in normalized for token in ("tecnic", "desempen", "performance")):
        return "technical_performance"
    if any(token in normalized for token in ("costo", "cost", "lcc")):
        return "lcc_cost"
    if any(token in normalized for token in ("salud", "ecosist", "health")):
        return "health_ecosystems"
    if any(token in normalized for token in ("mencion", "cantidad")):
        return "cantidad_menciones"
    return None


def _find_matrix_sheet(workbook: Workbook) -> Any:
    for sheet in workbook.worksheets:
        title = sheet.title.lower()
        if "matriz" in title and "datos" in title:
            return sheet
    raise ValueError("No se encontró la hoja de matriz de datos de entrada.")


def read_material_matrix(workbook: Workbook) -> tuple[list[str], dict[str, list[float]]]:
    sheet = _find_matrix_sheet(workbook)
    header_row = None
    header: tuple[Any, ...] | None = None
    for index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if any(isinstance(value, str) and value.strip().lower() in {"material", "materiales"} for value in row):
            header_row, header = index, row
            break
    if header_row is None or header is None:
        raise ValueError("No se encontró la cabecera Material en la matriz.")

    try:
        material_column = next(
            index
            for index, value in enumerate(header)
            if isinstance(value, str) and value.strip().lower() in {"material", "materiales"}
        )
    except StopIteration as exc:
        raise ValueError("No se encontró la columna Material.") from exc

    material_names: list[str] = []
    rows: list[tuple[Any, ...]] = []
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        value = row[material_column] if material_column < len(row) else None
        if value is None or not str(value).strip():
            if material_names:
                break
            continue
        name = str(value).strip()
        if name.lower() in {"material", "materiales", "total", "#", "datos"}:
            continue
        material_names.append(name)
        rows.append(row)

    if not material_names:
        raise ValueError("No se encontraron materiales en la matriz.")

    matrix: dict[str, list[float]] = {}
    for column, heading in enumerate(header):
        criterion = map_criterion_name(heading) if heading is not None else None
        if criterion not in MODEL_CRITERIA:
            continue
        values: list[float] = []
        for row in rows:
            value = row[column] if column < len(row) else None
            try:
                values.append(float(value))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"El criterio '{heading}' contiene un valor no numérico.") from exc
        if criterion not in matrix:
            matrix[criterion] = values
    return material_names, matrix


def read_criteria_weights(workbook: Workbook) -> dict[str, float] | None:
    for sheet in workbook.worksheets:
        title = sheet.title.lower()
        if "peso" not in title or "final" not in title:
            continue
        weights: dict[str, float] = {}
        for row in sheet.iter_rows(values_only=True):
            if not row or not isinstance(row[0], str):
                continue
            criterion = map_criterion_name(row[0])
            if criterion not in MODEL_CRITERIA:
                continue
            candidates: list[float] = []
            for value in row[1:]:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if 0 < number < 1:
                    candidates.append(number)
            if candidates:
                weights[criterion] = candidates[-1]
        if set(weights) == set(MODEL_CRITERIA):
            return weights
    return None


class ExcelWorkbookLoader:
    """Carga hojas Excel para compatibilidad con consumidores existentes."""

    def load(self, file_path: str) -> dict[str, Any]:
        from openpyxl import load_workbook

        workbook = load_workbook(file_path, data_only=True)
        return {sheet.title: sheet for sheet in workbook.worksheets}

    def extract_materials_and_criteria(
        self, workbook_data: dict[str, Any]
    ) -> tuple[list[str], list[str], dict[str, list[float]]]:
        class WorkbookView:
            worksheets = list(workbook_data.values())

        materials, matrix = read_material_matrix(WorkbookView())
        return materials, list(matrix), matrix
