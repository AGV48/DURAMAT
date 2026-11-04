from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


MODEL_CRITERIA = ("co2", "energy", "technical_performance", "lcc_cost", "health_ecosystems")
CRITERIA_DIRECTION = {
    "co2": "min",
    "energy": "min",
    "technical_performance": "max",
    "lcc_cost": "min",
    "health_ecosystems": "min",
}
ANNUALIZED_MAP = {"co2": "annualized_co2", "energy": "annualized_energy"}
DEFAULT_WEIGHTS = {
    "co2": 0.3402,
    "energy": 0.2046,
    "technical_performance": 0.1865,
    "lcc_cost": 0.1598,
    "health_ecosystems": 0.1088,
}


@dataclass
class DecisionNode:
    name: str
    description: str = ""
    criteria: dict[str, float] = field(default_factory=dict)
    score_by_material: dict[str, float] = field(default_factory=dict)
    children: list["DecisionNode"] = field(default_factory=list)

    def add_child(self, child: "DecisionNode") -> None:
        self.children.append(child)


@dataclass
class DecisionModelEngine:
    """Motor MCDM-LCA.

    ``x_rec``, ``k_base``, ``k_min_ratio`` y ``life_cap`` son marcadores
    pendientes de calibración según fib Bulletin 34 / ISO 15686-1.
    La temperatura y ``alpha_hr`` aún no están calibradas.
    """

    k_base: float = 6.0
    x_rec: float = 50.0
    x_critica: float = 0.5
    v_corr_base: float = 0.05
    alpha_hr: float = 0.008
    k_min_ratio: float = 0.05
    life_cap: float = 100.0
    co2_ref_ppm: float = 420.0
    dt_scale: float = 10.0
    aggregation: str = "topsis"
    use_annualized: bool = True

    # [CORRECCIÓN 5]
    def _prepare_weights(self, weights: dict[str, float] | None) -> dict[str, float]:
        prepared = dict(DEFAULT_WEIGHTS if weights is None else weights)
        unknown = set(prepared) - set(MODEL_CRITERIA)
        if unknown:
            raise ValueError(f"Pesos desconocidos: {', '.join(sorted(unknown))}.")
        if any(value < 0 for value in prepared.values()):
            raise ValueError("Los pesos no pueden ser negativos.")
        total = sum(prepared.values())
        if abs(total - 1.0) > 0.01 or total <= 0:
            raise ValueError("La suma de los pesos debe diferir de 1.0 como máximo en 0.01.")
        return {criterion: value / total for criterion, value in prepared.items()}

    # [CORRECCIÓN 6]
    def validate_inputs(self, matrix: dict[str, list[float]], material_names: list[str]) -> None:
        if not matrix:
            raise ValueError("La matriz de criterios está vacía.")
        if not material_names:
            raise ValueError("Debe existir al menos un material.")
        relevant = {key: values for key, values in matrix.items() if key in MODEL_CRITERIA}
        if not relevant:
            raise ValueError("La matriz no contiene criterios del modelo.")
        expected = len(material_names)
        for criterion, values in relevant.items():
            if len(values) != expected:
                raise ValueError(f"El criterio '{criterion}' no coincide con la cantidad esperada de materiales.")
            for index, value in enumerate(values):
                material = material_names[index]
                if value is None:
                    raise ValueError(f"El valor de '{criterion}' para '{material}' no puede ser nulo.")
                try:
                    converted = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"El valor de '{criterion}' para '{material}' no es numérico.") from exc
                if not np.isfinite(converted):
                    raise ValueError(f"El valor de '{criterion}' para '{material}' no es válido.")
                values[index] = converted
                if criterion in {"co2", "energy", "lcc_cost", "health_ecosystems"} and converted < 0:
                    raise ValueError(f"El criterio '{criterion}' para '{material}' debe ser >= 0.")
                if criterion == "technical_performance" and not 0 <= converted <= 10:
                    raise ValueError(f"El criterio '{criterion}' para '{material}' debe estar entre 0 y 10.")

    # [CORRECCIÓN 2]
    def normalize_min_max(
        self, matrix: dict[str, list[float]], directions: dict[str, str] | None = None
    ) -> dict[str, list[float]]:
        directions = directions or CRITERIA_DIRECTION
        normalized: dict[str, list[float]] = {}
        for criterion, values in matrix.items():
            arr = np.asarray(values, dtype=float)
            minimum, maximum = float(np.min(arr)), float(np.max(arr))
            if np.isclose(maximum, minimum):
                normalized[criterion] = np.ones_like(arr, dtype=float).tolist()
            elif directions.get(criterion, "max") == "min":
                normalized[criterion] = ((maximum - arr) / (maximum - minimum)).tolist()
            else:
                normalized[criterion] = ((arr - minimum) / (maximum - minimum)).tolist()
        return normalized

    # [CORRECCIÓN 3], [CORRECCIÓN 4], [CORRECCIÓN 7]
    def calculate_life_cycle(self, technical_performance: list[float], climate: dict[str, float]) -> list[float]:
        hr = float(climate.get("relative_humidity", 75.0)) / 100.0
        co2_ppm = max(float(climate.get("co2_ppm", 420.0)), 0.0)
        dt = np.clip(np.asarray(technical_performance, dtype=float) / self.dt_scale, 0.0, 1.0)
        k_values = self.k_base * (1.0 - dt)
        k_values *= np.sqrt(co2_ppm / self.co2_ref_ppm)
        k_values = np.maximum(k_values, self.k_base * self.k_min_ratio)
        t_i = np.power(self.x_rec / k_values, 2)
        # TODO calibrar temperatura y alpha_hr.
        v_corr = self.v_corr_base * (1.0 + self.alpha_hr * hr)
        t_p = self.x_critica / v_corr
        return np.minimum(t_i + t_p, self.life_cap).tolist()

    # [CORRECCIÓN 1]
    def annualize_lca(self, matrix: dict[str, list[float]], life_years: list[float]) -> dict[str, list[float]]:
        annualized: dict[str, list[float]] = {}
        for criterion, annualized_name in ANNUALIZED_MAP.items():
            values = np.asarray(matrix[criterion], dtype=float)
            annualized[annualized_name] = (values / np.asarray(life_years, dtype=float)).tolist()
        return annualized

    # [CORRECCIÓN 8]
    def topsis(self, matrix: dict[str, list[float]], weights: dict[str, float]) -> list[float]:
        criteria = [criterion for criterion in MODEL_CRITERIA if criterion in matrix and criterion in weights]
        values = np.asarray([matrix[criterion] for criterion in criteria], dtype=float).T
        norms = np.sqrt(np.sum(values**2, axis=0))
        normalized = np.divide(values, norms, out=np.zeros_like(values), where=norms > 0)
        weighted = normalized * np.asarray([weights[criterion] for criterion in criteria])
        ideal_positive = np.array(
            [np.max(weighted[:, i]) if CRITERIA_DIRECTION[c] == "max" else np.min(weighted[:, i]) for i, c in enumerate(criteria)]
        )
        ideal_negative = np.array(
            [np.min(weighted[:, i]) if CRITERIA_DIRECTION[c] == "max" else np.max(weighted[:, i]) for i, c in enumerate(criteria)]
        )
        positive_distance = np.linalg.norm(weighted - ideal_positive, axis=1)
        negative_distance = np.linalg.norm(weighted - ideal_negative, axis=1)
        denominator = positive_distance + negative_distance
        return np.divide(
            negative_distance,
            denominator,
            out=np.full(len(values), 0.5, dtype=float),
            where=denominator > 0,
        ).tolist()

    # [CORRECCIÓN 8]
    def wlc(self, matrix: dict[str, list[float]], weights: dict[str, float]) -> list[float]:
        normalized = self.normalize_min_max(matrix, CRITERIA_DIRECTION)
        return [
            sum(weights[criterion] * normalized[criterion][index] for criterion in normalized if criterion in weights)
            for index in range(len(next(iter(normalized.values()))))
        ]

    # [REFACTOR], [CORRECCIÓN 1], [CORRECCIÓN 5], [CORRECCIÓN 6], [CORRECCIÓN 8]
    def _evaluate(
        self,
        material_names: list[str],
        matrix: dict[str, list[float]],
        climate: dict[str, float],
        weights: dict[str, float] | None,
    ) -> dict[str, Any]:
        prepared_weights = self._prepare_weights(weights)
        self.validate_inputs(matrix, material_names)
        model_matrix = {criterion: list(matrix[criterion]) for criterion in MODEL_CRITERIA if criterion in matrix}
        missing = [criterion for criterion in prepared_weights if criterion not in model_matrix]
        if missing:
            raise ValueError(f"Falta el criterio con peso: {', '.join(missing)}.")
        life_years = self.calculate_life_cycle(model_matrix["technical_performance"], climate)
        annualized = self.annualize_lca(model_matrix, life_years)
        scoring_matrix = dict(model_matrix)
        if self.use_annualized:
            for criterion, annualized_name in ANNUALIZED_MAP.items():
                scoring_matrix[criterion] = annualized[annualized_name]
        normalized = self.normalize_min_max(scoring_matrix, CRITERIA_DIRECTION)
        topsis_scores = self.topsis(scoring_matrix, prepared_weights)
        wlc_scores = self.wlc(scoring_matrix, prepared_weights)
        if self.aggregation not in {"topsis", "wlc"}:
            raise ValueError("aggregation debe ser 'topsis' o 'wlc'.")
        scores = topsis_scores if self.aggregation == "topsis" else wlc_scores
        rows: list[dict[str, Any]] = []
        for index, material in enumerate(material_names):
            rows.append(
                {
                    "material": material,
                    "score": float(scores[index]),
                    "topsis_ci": float(topsis_scores[index]),
                    "wlc_score": float(wlc_scores[index]),
                    "life_years": float(life_years[index]),
                    "annualized_co2": float(annualized["annualized_co2"][index]),
                    "annualized_energy": float(annualized["annualized_energy"][index]),
                    **{criterion: float(model_matrix[criterion][index]) for criterion in MODEL_CRITERIA},
                    "contribution": {
                        criterion: float(prepared_weights[criterion] * normalized[criterion][index])
                        for criterion in prepared_weights
                    },
                }
            )
        rows.sort(key=lambda item: item["score"], reverse=True)
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
        return {
            "rows": rows,
            "weights": prepared_weights,
            "normalized": normalized,
            "annualized": annualized,
            "life_years": life_years,
            "scoring_matrix": scoring_matrix,
        }

    # [REFACTOR]
    def _tree_from_result(self, material_names: list[str], result: dict[str, Any]) -> DecisionNode:
        rows = result["rows"]
        normalized = result["normalized"]
        annualized = result["annualized"]
        weights = result["weights"]
        tree = DecisionNode(
            name="Modelo de Evaluación Integral",
            description="Árbol de decisión integrado MCDM-LCA",
            score_by_material={row["material"]: row["score"] for row in rows},
        )
        level_1 = DecisionNode(
            name="Nivel 1: Validación y preparación de datos",
            description="Verificación de rangos y normalización min-max direccional.",
            criteria={criterion: float(np.mean(values)) for criterion, values in normalized.items()},
            score_by_material={
                material: float(np.mean([values[index] for values in normalized.values()]))
                for index, material in enumerate(material_names)
            },
        )
        climate = result.get("climate", {})
        level_2 = DecisionNode(
            name="Nivel 2: Cálculo de durabilidad y vida útil",
            description="Durabilidad con k_min_ratio, life_cap, co2_ppm y HR.",
            criteria={
                "k_base": self.k_base,
                "x_rec": self.x_rec,
                "k_min_ratio": self.k_min_ratio,
                "life_cap": self.life_cap,
                "co2_ppm": float(climate.get("co2_ppm", 420.0)),
                "HR": float(climate.get("relative_humidity", 75.0)) / 100.0,
            },
            score_by_material={row["material"]: row["life_years"] for row in rows},
        )
        level_3 = DecisionNode(
            name="Nivel 3: Integración LCA-MCDM",
            description="Impactos anualizados por CO2 y energía.",
            criteria={criterion: float(np.mean(values)) for criterion, values in annualized.items()},
            score_by_material={row["material"]: row["annualized_co2"] for row in rows},
        )
        level_4 = DecisionNode(
            name="Nivel 4: Agregación ponderada y ranking",
            description=f"Agregación {self.aggregation}; pesos usados.",
            criteria=weights,
            score_by_material={row["material"]: row["score"] for row in rows},
        )
        for level in (level_1, level_2, level_3, level_4):
            tree.add_child(level)
        for row in rows:
            level_4.add_child(
                DecisionNode(
                    name=row["material"],
                    description=f"Puntuación final: {row['score']:.4f}",
                    criteria={
                        "score": row["score"],
                        "topsis_ci": row["topsis_ci"],
                        "wlc_score": row["wlc_score"],
                        "life_years": row["life_years"],
                    },
                    score_by_material={row["material"]: row["score"]},
                )
            )
        return tree

    def build_decision_tree(
        self,
        material_names: list[str],
        matrix: dict[str, list[float]],
        climate: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> DecisionNode:
        result = self._evaluate(material_names, matrix, climate, weights)
        result["climate"] = climate
        return self._tree_from_result(material_names, result)

    def print_decision_tree(self, node: DecisionNode, depth: int = 0) -> None:
        indent = "  " * depth
        print(f"{indent}- {node.name}")
        if node.criteria:
            for key, value in node.criteria.items():
                print(f"{indent}    • {key}: {value}")
        if node.score_by_material:
            print(f"{indent}    • Puntajes por material: {node.score_by_material}")
        for child in node.children:
            self.print_decision_tree(child, depth + 1)

    def render_decision_tree_text(self, node: DecisionNode, include_details: bool = True) -> str:
        lines: list[str] = []

        def visit(current: DecisionNode, prefix: str, is_last: bool, is_root: bool = False) -> None:
            connector = "" if is_root else ("└── " if is_last else "├── ")
            lines.append(f"{prefix}{connector}{current.name}")
            child_prefix = prefix if is_root else f"{prefix}{'    ' if is_last else '│   '}"
            if include_details and current.description:
                lines.append(f"{child_prefix}desc: {current.description}")
            if include_details and current.criteria:
                lines.append(f"{child_prefix}criterios:")
                for key, value in current.criteria.items():
                    lines.append(f"{child_prefix}  - {key}: {value:.6g}" if isinstance(value, float) else f"{child_prefix}  - {key}: {value}")
            if include_details and current.score_by_material:
                lines.append(f"{child_prefix}puntajes:")
                for material, score in current.score_by_material.items():
                    lines.append(f"{child_prefix}  - {material}: {score:.6g}")
            for index, child in enumerate(current.children):
                visit(child, child_prefix, index == len(current.children) - 1)

        visit(node, "", True, True)
        return "\n".join(lines)

    def _build_rich_tree(self, node: DecisionNode, include_details: bool = True) -> Any:
        from rich.tree import Tree

        branch = Tree(f"[bold cyan]{node.name}[/bold cyan]")
        if include_details and node.description:
            branch.add(f"[dim]{node.description}[/dim]")
        if include_details and node.criteria:
            criteria_branch = branch.add("[yellow]Criterios[/yellow]")
            for key, value in node.criteria.items():
                criteria_branch.add(f"{key}: {value:.6g}" if isinstance(value, float) else f"{key}: {value}")
        if include_details and node.score_by_material:
            scores_branch = branch.add("[green]Puntajes por material[/green]")
            for material, score in node.score_by_material.items():
                scores_branch.add(f"{material}: {score:.6g}")
        for child in node.children:
            branch.add(self._build_rich_tree(child, include_details))
        return branch

    def print_decision_tree_rich(self, node: DecisionNode, include_details: bool = True) -> None:
        from rich.console import Console

        Console(force_terminal=True, soft_wrap=True).print(self._build_rich_tree(node, include_details))

    def calculate_scores(
        self,
        material_names: list[str],
        matrix: dict[str, list[float]],
        climate: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionNode]:
        result = self._evaluate(material_names, matrix, climate, weights)
        result["climate"] = climate
        return result["rows"], self._tree_from_result(material_names, result)
