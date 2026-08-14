import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ExcelDataService } from '../../services/excel-data.service';
import { EvaluationService, type EvaluationResponse } from '../../services/evaluation.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class Home {
  loadingFile = false;
  errorMessage = '';
  temp = 24;
  humidity = 75;
  co2 = 420;

  constructor(
    private readonly excelDataService: ExcelDataService,
    private readonly evaluationService: EvaluationService,
    private readonly router: Router,
  ) {}

  async onFileSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    this.errorMessage = '';

    if (!file) {
      return;
    }

    this.loadingFile = true;

    try {
      await this.excelDataService.loadWorkbook(file);
      const response = await firstValueFrom(
        this.evaluationService.evaluate(file, {
          temperature_c: Number(this.temp),
          relative_humidity: Number(this.humidity),
          co2_ppm: Number(this.co2),
        }),
      );

      this.evaluationService.setResult(response);
      await this.router.navigate(['/result']);
    } catch (error: any) {
      console.error('Evaluation request failed', error);
      // Prefer server-provided detail when present (FastAPI ValueError handler returns { detail })
      const serverDetail = error && error.error && (error.error.detail || error.error.message);
      this.errorMessage = typeof serverDetail === 'string' && serverDetail ? serverDetail : (error instanceof Error ? error.message : 'No se pudo leer el archivo Excel.');
      this.excelDataService.clear();
      this.evaluationService.clear();
    } finally {
      this.loadingFile = false;
    }
  }

  evaluateModel() {
    // se reutiliza el flujo de evaluación del archivo cargado
  }
}
