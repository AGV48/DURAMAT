from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.decision_model import DecisionModelEngine


MATERIALS = ["Concreto RCD", "Geopolímeros", "Bambú", "Biochar", "Vidrio reciclado", "Hempcrete", "Ceniza cáscara arroz", "Fibras plástico"]
MATRIX = {
    "co2": [320, 100, 50, 180, 280, 40, 210, 240],
    "energy": [1.2, 3.5, 0.5, 1.8, 1.0, 0.8, 0.6, 2.5],
    "technical_performance": [7.5, 8, 7, 7, 6.5, 5.5, 7, 6],
    "lcc_cost": [4, 6, 5.5, 5.5, 3.5, 7.5, 3, 3.5],
    "health_ecosystems": [3.5, 3, 1.5, 2, 2.5, 1.5, 2.5, 4.5],
}
CLIMATE = {"temperature_c": 24.0, "relative_humidity": 75.0, "co2_ppm": 420.0}
EXCEL_CI = {
    "Concreto RCD": 0.3780,
    "Geopolímeros": 0.5046,
    "Bambú": 0.8724,
    "Biochar": 0.5306,
    "Vidrio reciclado": 0.4464,
    "Hempcrete": 0.7800,
    "Ceniza cáscara arroz": 0.5897,
    "Fibras plástico": 0.3381,
}


def test_static_topsis_matches_excel():
    ranking, _ = DecisionModelEngine(use_annualized=False).calculate_scores(MATERIALS, MATRIX, CLIMATE)
    assert {row["material"]: row["topsis_ci"] for row in ranking} == pytest.approx(EXCEL_CI, abs=0.0002)
    assert [row["material"] for row in ranking] == [
        "Bambú", "Hempcrete", "Ceniza cáscara arroz", "Biochar",
        "Geopolímeros", "Vidrio reciclado", "Concreto RCD", "Fibras plástico",
    ]


def test_annualized_ranking_has_bamboo_first_and_fibras_last():
    ranking, _ = DecisionModelEngine().calculate_scores(MATERIALS, MATRIX, CLIMATE)
    assert ranking[0]["material"] == "Bambú"
    assert ranking[-1]["material"] == "Fibras plástico"


def test_life_cycle_bounds_and_dt_effect():
    engine = DecisionModelEngine()
    ranking, _ = engine.calculate_scores(MATERIALS, MATRIX, CLIMATE)
    t_p = engine.x_critica / (engine.v_corr_base * (1 + engine.alpha_hr * 0.75))
    assert all(t_p <= row["life_years"] <= engine.life_cap for row in ranking)
    assert next(row for row in ranking if row["material"] == "Geopolímeros")["life_years"] != min(row["life_years"] for row in ranking)


def test_higher_co2_reduces_life_with_large_cap():
    engine = DecisionModelEngine(life_cap=1e6)
    low, _ = engine.calculate_scores(MATERIALS, MATRIX, CLIMATE)
    high_climate = {**CLIMATE, "co2_ppm": 1000.0}
    high, _ = engine.calculate_scores(MATERIALS, MATRIX, high_climate)
    low_life = {row["material"]: row["life_years"] for row in low}
    high_life = {row["material"]: row["life_years"] for row in high}
    assert all(high_life[name] < low_life[name] for name in low_life)


def test_validation_and_aggregation_errors():
    with pytest.raises(ValueError):
        DecisionModelEngine().calculate_scores(MATERIALS, {**MATRIX, "co2": MATRIX["co2"][:-1]}, CLIMATE)
    with pytest.raises(ValueError):
        DecisionModelEngine().calculate_scores(MATERIALS, {**MATRIX, "co2": [-1] + MATRIX["co2"][1:]}, CLIMATE)
    with pytest.raises(ValueError):
        DecisionModelEngine().calculate_scores(MATERIALS, {**MATRIX, "technical_performance": [12] + MATRIX["technical_performance"][1:]}, CLIMATE)
    with pytest.raises(ValueError):
        DecisionModelEngine().calculate_scores(MATERIALS, MATRIX, CLIMATE, {"co2": 0.8})
    with pytest.raises(ValueError):
        DecisionModelEngine(aggregation="xyz").calculate_scores(MATERIALS, MATRIX, CLIMATE)


def test_weights_wlc_and_tree_shape():
    engine = DecisionModelEngine(aggregation="wlc")
    ranking, tree = engine.calculate_scores(MATERIALS, MATRIX, CLIMATE, {key: value * 1.0001 for key, value in {
        "co2": 0.3402, "energy": 0.2046, "technical_performance": 0.1865,
        "lcc_cost": 0.1598, "health_ecosystems": 0.1088,
    }.items()})
    assert all(0 <= row["wlc_score"] <= 1 for row in ranking)
    assert len([node for node in tree.children if node.name.startswith("Nivel")]) == 4
    assert len(tree.children[3].children) == 8


def test_api_evaluates_reference_workbook():
    workbook_path = Path(__file__).parents[2] / "DuramatFront" / "MCDM_Materiales.xlsx"
    if not workbook_path.exists():
        pytest.skip("No existe el Excel de referencia.")
    from main import app

    with TestClient(app) as client:
        with workbook_path.open("rb") as workbook:
            response = client.post(
                "/api/evaluate",
                files={"file": ("MCDM_Materiales.xlsx", workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["ranking"]) == 8
    assert all("cantidad_menciones" not in row["contribution"] for row in payload["ranking"])
    assert sum(payload["weights"].values()) == pytest.approx(1)
    assert payload["ranking"][0]["material"] == "Bambú"
