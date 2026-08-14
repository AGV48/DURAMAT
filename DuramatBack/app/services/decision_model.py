from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


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
    """Implementa el flujo de evaluación MCDM-LCA como un árbol de decisión."""

    k_base: float = 6.0
    x_rec: float = 50.0
    x_critica: float = 0.5
    v_corr_base: float = 0.05
    alpha_hr: float = 0.008

    def validate_inputs(self, matrix: dict[str, list[float]], material_names: list[str]) -> None:
        if not matrix:
            raise ValueError("La matriz de criterios está vacía.")
        if not material_names:
            raise ValueError("Debe existir al menos un material.")
        if len(material_names) != len(next(iter(matrix.values()))):
            raise ValueError("La cantidad de materiales no coincide con la cantidad de valores por criterio.")

        for criterion, values in matrix.items():
            if len(values) != len(material_names):
                raise ValueError(f"El criterio '{criterion}' no coincide con la cantidad esperada de materiales.")
            for value in values:
                if value is None or np.isnan(value):
                    raise ValueError(f"Hay valores nulos en el criterio '{criterion}'.")

    def normalize_min_max(self, matrix: dict[str, list[float]]) -> dict[str, list[float]]:
        normalized: dict[str, list[float]] = {}
        for criterion, values in matrix.items():
            arr = np.asarray(values, dtype=float)
            min_value = float(np.min(arr))
            max_value = float(np.max(arr))
            if np.isclose(max_value, min_value):
                normalized[criterion] = np.ones_like(arr, dtype=float).tolist()
            else:
                normalized[criterion] = ((arr - min_value) / (max_value - min_value)).tolist()
        return normalized

    def calculate_life_cycle(self, technical_performance: list[float], climate: dict[str, float]) -> list[float]:
        hr = float(climate.get("relative_humidity", 75.0)) / 100.0
        dt_norm = np.asarray(technical_performance, dtype=float)
        k_values = self.k_base * (1.0 - dt_norm)
        t_i = np.divide(self.x_rec, np.power(k_values, 2), out=np.zeros_like(dt_norm), where=k_values > 0)
        v_corr = self.v_corr_base * (1.0 + self.alpha_hr * hr)
        t_p = np.full_like(dt_norm, self.x_critica / v_corr, dtype=float)
        return (t_i + t_p).tolist()

    def annualize_lca(self, matrix: dict[str, list[float]], life_years: list[float]) -> dict[str, list[float]]:
        annualized: dict[str, list[float]] = {}
        for criterion in ["co2", "energy"]:
            if criterion not in matrix:
                continue
            values = np.asarray(matrix[criterion], dtype=float)
            years = np.asarray(life_years, dtype=float)
            result = np.divide(values, years, out=np.full_like(values, 0.0, dtype=float), where=years > 0)
            annualized[f"annualized_{criterion}"] = result.tolist()
        return annualized

    def build_decision_tree(
        self,
        material_names: list[str],
        matrix: dict[str, list[float]],
        climate: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> DecisionNode:
        if weights is None:
            weights = {
                "co2": 0.22,
                "energy": 0.18,
                "technical_performance": 0.22,
                "lcc_cost": 0.18,
                "health_ecosystems": 0.20,
            }

        self.validate_inputs(matrix, material_names)
        normalized = self.normalize_min_max(matrix)
        technical = normalized.get("technical_performance", [1.0] * len(material_names))
        life_years = self.calculate_life_cycle(technical, climate)
        annualized = self.annualize_lca(matrix, life_years)
        for criterion, values in annualized.items():
            normalized[criterion] = self.normalize_min_max({criterion: values})[criterion]

        score_rows = []
        for idx, material in enumerate(material_names):
            contribution_map: dict[str, float] = {}
            for criterion, value in normalized.items():
                if idx >= len(value):
                    continue
                contribution_map[criterion] = float(value[idx])

            total = 0.0
            for criterion, weight in weights.items():
                if criterion not in contribution_map:
                    continue
                total += contribution_map[criterion] * weight

            score_rows.append(
                {
                    "material": material,
                    "score": float(total),
                    "life_years": float(life_years[idx]),
                    "annualized_co2": float(annualized.get("annualized_co2", [0.0])[idx]),
                    "annualized_energy": float(annualized.get("annualized_energy", [0.0])[idx]),
                    "technical_performance": float(matrix.get("technical_performance", [0.0])[idx]),
                    "co2": float(matrix.get("co2", [0.0])[idx]),
                    "energy": float(matrix.get("energy", [0.0])[idx]),
                    "lcc_cost": float(matrix.get("lcc_cost", [0.0])[idx]),
                    "health_ecosystems": float(matrix.get("health_ecosystems", [0.0])[idx]),
                    "contribution": contribution_map,
                }
            )

        score_rows = sorted(score_rows, key=lambda item: item["score"], reverse=True)
        ranked_scores = {item["material"]: item["score"] for item in score_rows}

        root = DecisionNode(
            name="Modelo de Evaluación Integral",
            description="Árbol de decisión integrado MCDM-LCA",
            score_by_material=ranked_scores,
        )

        level_1 = DecisionNode(
            name="Nivel 1: Validación y preparación de datos",
            description="Verificación de rangos, integridad y normalización min-max.",
            criteria={criterion: float(np.mean(values)) for criterion, values in normalized.items()},
        )
        level_2 = DecisionNode(
            name="Nivel 2: Cálculo de durabilidad y vida útil",
            description="Carbonatación, inicio y propagación del deterioro.",
            criteria={"k_base": self.k_base, "x_rec": self.x_rec, "x_critica": self.x_critica},
            score_by_material={item["material"]: float(item["life_years"]) for item in score_rows},
        )
        level_3 = DecisionNode(
            name="Nivel 3: Integración LCA-MCDM",
            description="Impacto anualizado por CO₂ y energía para cada material.",
            criteria={criterion: float(np.mean(values)) for criterion, values in annualized.items()},
            score_by_material={item["material"]: float(item["annualized_co2"]) for item in score_rows},
        )
        level_4 = DecisionNode(
            name="Nivel 4: Agregación ponderada y ranking",
            description="Puntuación total y orden final de materiales.",
            criteria=weights,
            score_by_material=ranked_scores,
        )

        root.add_child(level_1)
        root.add_child(level_2)
        root.add_child(level_3)
        root.add_child(level_4)

        for item in score_rows:
            material_node = DecisionNode(
                name=item["material"],
                description=f"Puntuación final: {item['score']:.4f}",
                criteria={
                    "score": float(item["score"]),
                    "life_years": float(item["life_years"]),
                    "co2": float(item["co2"]),
                    "energy": float(item["energy"]),
                    "technical_performance": float(item["technical_performance"]),
                },
                score_by_material={item["material"]: float(item["score"])},
            )
            level_4.add_child(material_node)

        return root

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

    def calculate_scores(
        self,
        material_names: list[str],
        matrix: dict[str, list[float]],
        climate: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionNode]:
        if weights is None:
            weights = {
                "co2": 0.22,
                "energy": 0.18,
                "technical_performance": 0.22,
                "lcc_cost": 0.18,
                "health_ecosystems": 0.20,
            }

        if not np.isclose(sum(weights.values()), 1.0):
            raise ValueError("La suma de los pesos debe ser igual a 1.0")

        normalized = self.normalize_min_max(matrix)
        technical = normalized.get("technical_performance", [1.0] * len(material_names))
        life_years = self.calculate_life_cycle(technical, climate)

        annualized = self.annualize_lca(matrix, life_years)
        for criterion, values in annualized.items():
            normalized[criterion] = self.normalize_min_max({criterion: values})[criterion]

        score_rows: list[dict[str, Any]] = []
        for idx, material in enumerate(material_names):
            contribution_map: dict[str, float] = {}
            for criterion, value in normalized.items():
                if idx >= len(value):
                    continue
                contribution_map[criterion] = float(value[idx])

            total = 0.0
            for criterion, weight in weights.items():
                if criterion not in contribution_map:
                    continue
                total += contribution_map[criterion] * weight
                contribution_map[criterion] = contribution_map[criterion] * weight

            score_rows.append(
                {
                    "material": material,
                    "score": float(total),
                    "life_years": float(life_years[idx]),
                    "annualized_co2": float(annualized.get("annualized_co2", [0.0])[idx]),
                    "annualized_energy": float(annualized.get("annualized_energy", [0.0])[idx]),
                    "technical_performance": float(matrix.get("technical_performance", [0.0])[idx]),
                    "co2": float(matrix.get("co2", [0.0])[idx]),
                    "energy": float(matrix.get("energy", [0.0])[idx]),
                    "lcc_cost": float(matrix.get("lcc_cost", [0.0])[idx]),
                    "health_ecosystems": float(matrix.get("health_ecosystems", [0.0])[idx]),
                    "contribution": contribution_map,
                }
            )

        score_rows = sorted(score_rows, key=lambda item: item["score"], reverse=True)
        for rank, item in enumerate(score_rows, start=1):
            item["rank"] = rank

        tree = self.build_decision_tree(material_names, matrix, climate, weights)
        tree.score_by_material = {item["material"]: float(item["score"]) for item in score_rows}
        return score_rows, tree
