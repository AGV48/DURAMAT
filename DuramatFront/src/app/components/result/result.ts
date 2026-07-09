import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ExcelDataService } from '../../services/excel-data.service';

@Component({
  selector: 'app-result',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './result.html',
  styleUrl: './result.css',
})
export class Result {
  private readonly excelDataService = inject(ExcelDataService);

  readonly fileName = this.excelDataService.fileName;
  readonly materials = this.excelDataService.materials;
  readonly criteria = this.excelDataService.criteria;
  readonly hasData = this.excelDataService.hasData;

}
