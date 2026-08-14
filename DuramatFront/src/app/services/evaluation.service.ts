import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';

export interface ClimatePayload {
  temperature_c: number;
  relative_humidity: number;
  co2_ppm: number;
}

export interface MaterialEvaluationItem {
  rank: number;
  material: string;
  score: number;
  life_years: number;
  annualized_co2: number;
  annualized_energy: number;
  technical_performance: number;
  co2: number;
  energy: number;
  lcc_cost: number;
  health_ecosystems: number;
  contribution: Record<string, number>;
}

export interface EvaluationResponse {
  status: string;
  message: string;
  climate: ClimatePayload;
  ranking: MaterialEvaluationItem[];
  top_material: string | null;
  score_gap_percent: number | null;
}

@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly resultSignal = signal<EvaluationResponse | null>(null);
  readonly result = this.resultSignal.asReadonly();

  constructor(private readonly http: HttpClient) {}

  evaluate(file: File, climate: ClimatePayload): Observable<EvaluationResponse> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('temperature_c', String(climate.temperature_c));
    formData.append('relative_humidity', String(climate.relative_humidity));
    formData.append('co2_ppm', String(climate.co2_ppm));

    return this.http.post<EvaluationResponse>('http://localhost:8000/api/evaluate', formData, {
      headers: new HttpHeaders({ Accept: 'application/json' }),
    });
  }

  setResult(result: EvaluationResponse): void {
    this.resultSignal.set(result);
  }

  clear(): void {
    this.resultSignal.set(null);
  }
}
