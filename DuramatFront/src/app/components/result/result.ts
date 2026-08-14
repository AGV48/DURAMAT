import { CommonModule } from '@angular/common';
import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ExcelDataService } from '../../services/excel-data.service';
import { EvaluationService } from '../../services/evaluation.service';

@Component({
  selector: 'app-result',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './result.html',
  styleUrl: './result.css',
})
export class Result {
  private readonly excelDataService = inject(ExcelDataService);
  private readonly evaluationService = inject(EvaluationService);

  readonly fileName = this.excelDataService.fileName;
  readonly materials = this.excelDataService.materials;
  readonly criteria = this.excelDataService.criteria;
  readonly hasData = this.excelDataService.hasData;
  readonly evaluationResult = this.evaluationService.result;
  readonly topMaterial = computed(() => this.evaluationResult()?.top_material ?? 'Sin resultado');
  readonly climate = computed(() => this.evaluationResult()?.climate ?? null);
  readonly scoreGap = computed(() => this.evaluationResult()?.score_gap_percent ?? 0);
}
