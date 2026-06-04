import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';

@Component({
  selector: 'app-import-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    @if (svc.showImportModal()) {
      <div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" (click)="closeOnBackdrop($event)">
        <div class="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-lg overflow-hidden shadow-2xl">
          
          <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
            <h3 class="font-bold text-white text-base flex items-center gap-2">
              Importar Script Python (.py)
            </h3>
            <button (click)="close()" class="text-slate-400 hover:text-white">✕</button>
          </div>

          <div class="p-6 flex flex-col gap-4">
            <input #fileInput type="file" accept=".py" hidden (change)="onFileSelected($event)" />

            <div
              class="border-2 border-dashed border-slate-800 hover:border-blue-500/60 rounded-xl p-8 text-center cursor-pointer bg-slate-950/30 transition-all flex flex-col items-center gap-2.5"
              (click)="fileInput.click()"
            >
              <div class="p-3 bg-blue-600/10 text-blue-400 rounded-full">
                ⬆
              </div>

              <div>
                <p class="text-sm text-slate-200 font-semibold">
                  {{ selectedFile ? selectedFile.name : 'Arrastra un archivo .py aquí' }}
                </p>
                <p class="text-xs text-slate-500 mt-1">O haz clic para explorar tu almacenamiento local</p>
              </div>

              <span class="text-[10px] text-slate-400 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded">
                Tamaño máximo: 25MB
              </span>
            </div>

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">
                Nombre del Script <span class="text-rose-500">*</span>
              </label>
              <input type="text" [(ngModel)]="scriptName"
                class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
            </div>

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Descripción</label>
              <input type="text" [(ngModel)]="scriptDesc" placeholder="Descripción breve del script..."
                class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
            </div>

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Categoría</label>
              <select [(ngModel)]="scriptCategory"
                class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                <option value="BI & Analytics">BI & Analytics</option>
                <option value="ETL Pipeline">ETL Pipeline</option>
                <option value="Database Sync">Database Sync</option>
                <option value="Notificaciones">Notificaciones</option>
              </select>
            </div>
          </div>

          <div class="px-6 py-4 border-t border-slate-800 bg-slate-950/20 flex justify-end gap-3">
            <button (click)="close()" class="text-slate-400 hover:text-white text-sm font-semibold px-4 py-2 rounded-lg border border-slate-800">
              Cancelar
            </button>
            <button (click)="importScript()" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm px-5 py-2 rounded-lg">
              Importar Script
            </button>
          </div>

        </div>
      </div>
    }
  `
})
export class ImportModalComponent {
  scriptName = '';
  scriptDesc = '';
  scriptCategory = 'BI & Analytics';
  selectedFile: File | null = null;

  constructor(public svc: PyflowService) {}

  close() {
    this.svc.showImportModal.set(false);
  }

  closeOnBackdrop(event: Event) {
    if (event.target === event.currentTarget) this.close();
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.py')) {
      this.svc.showToast('Solo se permiten archivos .py', 'error');
      return;
    }

    this.selectedFile = file;
    this.scriptName = file.name;

    this.svc.showToast(`Archivo seleccionado: ${file.name}`, 'success');
  }

  importScript() {
    if (!this.selectedFile) {
      this.svc.showToast('Debe seleccionar un archivo .py', 'error');
      return;
    }

    if (!this.scriptName.trim()) {
      this.svc.showToast('El nombre del script es requerido.', 'error');
      return;
    }

    this.svc.uploadScript(
      this.selectedFile,
      this.scriptName,
      this.scriptDesc,
      this.scriptCategory
    ).subscribe({
      next: () => {
        this.svc.showToast('Script importado correctamente.');
        this.svc.loadScripts();

        this.scriptName = '';
        this.scriptDesc = '';
        this.scriptCategory = 'BI & Analytics';
        this.selectedFile = null;

        this.close();
      },
      error: err => {
        this.svc.showToast(
          `Error importando script: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });

    this.scriptName = '';
    this.scriptDesc = '';
    this.scriptCategory = 'BI & Analytics';
    this.selectedFile = null;

    this.close();
  }
}