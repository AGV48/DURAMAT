import { Injectable, computed, signal } from '@angular/core';
import * as XLSX from 'xlsx';

export interface SheetNames {
  sheetName: string;
  items: string[];
}

@Injectable({ providedIn: 'root' })
export class ExcelDataService {
  private readonly materialsSignal = signal<SheetNames | null>(null);
  private readonly criteriaSignal = signal<SheetNames | null>(null);
  private readonly fileNameSignal = signal('');

  readonly materials = this.materialsSignal.asReadonly();
  readonly criteria = this.criteriaSignal.asReadonly();
  readonly fileName = this.fileNameSignal.asReadonly();
  readonly hasData = computed(() => Boolean(this.materialsSignal() && this.criteriaSignal()));

  async loadWorkbook(file: File): Promise<void> {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array' });

    this.fileNameSignal.set(file.name);
    this.materialsSignal.set(this.readNamesFromSheet(workbook, 6, 1, 'Materiales'));
    this.criteriaSignal.set(this.readNamesFromSheet(workbook, 0, 0, 'Criterios'));
  }

  clear(): void {
    this.fileNameSignal.set('');
    this.materialsSignal.set(null);
    this.criteriaSignal.set(null);
  }

  private readNamesFromSheet(
    workbook: XLSX.WorkBook,
    index: number,
    columnIndex: number,
    fallbackName: string,
  ): SheetNames {
    const sheetName = workbook.SheetNames[index];
    if (!sheetName) {
      throw new Error(`No se encontró la hoja ${index + 1} en el archivo.`);
    }

    const sheet = workbook.Sheets[sheetName];
    const rawRows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' }) as unknown[][];
    const items = rawRows
      .slice(4)
      .map((row) => String(row?.[columnIndex] ?? '').trim())
      .filter((value) => this.isValidName(value));

    if (items.length === 0) {
      return {
        sheetName: fallbackName,
        items: [],
      };
    }

    return {
      sheetName: fallbackName,
      items,
    };
  }

  private isValidName(value: string): boolean {
    const normalized = value.trim();
    if (!normalized) {
      return false;
    }

    const ignoredValues = new Set([
      'Criterio',
      'Material',
      'Total',
      '#',
    ]);

    return !ignoredValues.has(normalized) && !normalized.toLowerCase().includes('datos');
  }
}