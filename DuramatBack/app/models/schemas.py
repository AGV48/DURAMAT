from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ClimateInput(BaseModel):
    temperature_c: float = Field(default=24.0, ge=-50.0, le=100.0)
    relative_humidity: float = Field(default=75.0, ge=0.0, le=100.0)
    co2_ppm: float = Field(default=420.0, ge=0.0)


class AnalysisRequest(BaseModel):
    climate: ClimateInput = ClimateInput()
    material_names: list[str] | None = None
    criteria: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_request(self):
        if self.material_names is not None and len(self.material_names) == 0:
            raise ValueError("material_names no puede estar vacío.")
        return self


class MaterialEvaluation(BaseModel):
    rank: int
    material: str
    score: float
    life_years: float
    annualized_co2: float
    annualized_energy: float
    technical_performance: float
    co2: float
    energy: float
    lcc_cost: float
    health_ecosystems: float
    contribution: dict[str, float] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    status: str = "success"
    message: str = "Evaluación completada exitosamente."
    climate: ClimateInput
    ranking: list[MaterialEvaluation]
    top_material: str | None = None
    score_gap_percent: float | None = None
