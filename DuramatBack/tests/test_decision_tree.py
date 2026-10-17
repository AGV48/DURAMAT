from app.services.decision_model import DecisionModelEngine


def test_tree_is_built_with_criteria_and_scores():
    engine = DecisionModelEngine()
    material_names = ["M1", "M2"]
    matrix = {
        "co2": [10.0, 20.0],
        "energy": [80.0, 120.0],
        "technical_performance": [8.0, 5.0],
        "lcc_cost": [100.0, 90.0],
        "health_ecosystems": [0.7, 0.5],
    }

    tree = engine.build_decision_tree(material_names, matrix, {"temperature_c": 24.0, "relative_humidity": 75.0, "co2_ppm": 420.0})

    assert tree.name == "Modelo de Evaluación Integral"
    assert len(tree.children) >= 4
    assert any(node.name.startswith("Nivel") for node in tree.children)
    assert tree.score_by_material
    assert tree.score_by_material["M1"] >= 0
    assert tree.score_by_material["M2"] >= 0


def test_lower_environmental_impacts_improve_score():
    engine = DecisionModelEngine()
    matrix = {
        "co2": [10.0, 20.0],
        "energy": [10.0, 20.0],
        "technical_performance": [5.0, 5.0],
        "lcc_cost": [10.0, 20.0],
        "health_ecosystems": [0.1, 0.2],
    }

    ranking, _ = engine.calculate_scores(
        ["M1", "M2"],
        matrix,
        {"temperature_c": 24.0, "relative_humidity": 75.0, "co2_ppm": 420.0},
    )

    assert ranking[0]["material"] == "M1"
