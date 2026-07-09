import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ExcelDataService } from '../../services/excel-data.service';

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
      await this.router.navigate(['/result']);
    } catch (error) {
      this.errorMessage = error instanceof Error ? error.message : 'No se pudo leer el archivo Excel.';
      this.excelDataService.clear();
    } finally {
      this.loadingFile = false;
    }
  }

  evaluateModel() {
  }
}
