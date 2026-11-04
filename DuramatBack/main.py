from __future__ import annotations

import logging
from io import BytesIO

import openpyxl
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.schemas import ClimateInput, DecisionNodeEvaluation, EvaluationResponse, MaterialEvaluation
from app.services.decision_model import DecisionModelEngine
from app.services.excel_loader import read_criteria_weights, read_material_matrix

logger = logging.getLogger(__name__)
app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    logger.error("Evaluation rejected: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Request validation failed for %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Request validation error",
            "errors": [
                {"loc": [str(part) for part in error.get("loc", [])], "msg": error.get("msg", "invalid value")}
                for error in exc.errors()
            ],
        },
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_excel(
    file: UploadFile = File(...),
    temperature_c: float = Form(24.0),
    relative_humidity: float = Form(75.0),
    co2_ppm: float = Form(420.0),
    aggregation: str = Form("topsis"),
) -> EvaluationResponse:
    if not file.filename:
        raise ValueError("Debe adjuntar un archivo Excel.")
    content = await file.read()
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=True)
    material_names, mapped_matrix = read_material_matrix(workbook)
    weights = read_criteria_weights(workbook)
    climate = ClimateInput(
        temperature_c=temperature_c,
        relative_humidity=relative_humidity,
        co2_ppm=co2_ppm,
    )
    engine = DecisionModelEngine(aggregation=aggregation)
    raw_ranking, tree = engine.calculate_scores(
        material_names,
        mapped_matrix,
        climate.model_dump(),
        weights=weights,
    )
    decision_tree_text = engine.render_decision_tree_text(tree, include_details=True)
    decision_nodes = [
        DecisionNodeEvaluation(
            name=node.name,
            description=node.description,
            scores={material: float(score) for material, score in node.score_by_material.items()},
        )
        for node in [*tree.children, tree]
        if node.score_by_material
    ]
    if settings.debug:
        try:
            engine.print_decision_tree_rich(tree, include_details=True)
        except ImportError:
            engine.print_decision_tree(tree)

    ranking = [
        MaterialEvaluation(
            rank=item["rank"],
            material=item["material"],
            score=float(item["score"]),
            topsis_ci=float(item["topsis_ci"]),
            wlc_score=float(item["wlc_score"]),
            life_years=float(item["life_years"]),
            annualized_co2=float(item["annualized_co2"]),
            annualized_energy=float(item["annualized_energy"]),
            technical_performance=float(item["technical_performance"]),
            co2=float(item["co2"]),
            energy=float(item["energy"]),
            lcc_cost=float(item["lcc_cost"]),
            health_ecosystems=float(item["health_ecosystems"]),
            contribution={key: float(value) for key, value in item["contribution"].items()},
        )
        for item in raw_ranking
    ]
    score_gap = 0.0
    if len(ranking) > 1:
        score_gap = ((ranking[0].score - ranking[1].score) / max(ranking[0].score, 1e-9)) * 100
    return EvaluationResponse(
        status="success",
        message="Evaluación completada exitosamente.",
        climate=climate,
        ranking=ranking,
        top_material=ranking[0].material if ranking else None,
        score_gap_percent=score_gap,
        decision_tree_text=decision_tree_text,
        decision_nodes=decision_nodes,
        aggregation=aggregation,
        weights=engine._prepare_weights(weights),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
