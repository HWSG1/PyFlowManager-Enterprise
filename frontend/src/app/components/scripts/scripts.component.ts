import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { Script } from '../../models/models';

@Component({
  selector: 'app-scripts',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-white">Scripts Administrados</h1>
          <p class="text-sm text-slate-400">Sube, configura y arranca tus tareas de Python directamente.</p>
        </div>

        <button (click)="svc.showImportModal.set(true)"
          class="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm px-4 py-2 rounded-lg flex items-center gap-2 shadow-lg transition-all">
          ↑ Importar Script
        </button>
      </div>

      <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl flex flex-wrap gap-4 items-center justify-between">
        <div class="flex flex-wrap items-center gap-3">
          <input
            type="text"
            [(ngModel)]="searchTerm"
            (ngModelChange)="currentPage = 1"
            placeholder="Buscar script por nombre..."
            class="w-64 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">

          <select
            [(ngModel)]="filterCategory"
            (change)="currentPage = 1"
            class="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
            <option value="all">Todas las Categorías</option>
            <option value="BI & Analytics">BI & Analytics</option>
            <option value="ETL Pipeline">ETL Pipeline</option>
            <option value="Database Sync">Database Sync</option>
            <option value="Notificaciones">Notificaciones</option>
          </select>

          <select
            [(ngModel)]="filterStatus"
            (change)="currentPage = 1"
            class="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
            <option value="all">Todos los Estados</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>

        <div class="text-xs text-slate-400">
          Total: <span class="text-blue-400 font-bold">{{ filteredScripts.length }}</span>
        </div>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm text-slate-300">
            <thead class="bg-slate-900/70 text-xs font-semibold uppercase text-slate-400 border-b border-slate-800">
              <tr>
                <th class="px-6 py-4">Nombre</th>
                <th class="px-6 py-4">Categoría</th>
                <th class="px-6 py-4">Ruta Archivo</th>
                <th class="px-6 py-4">Estado</th>
                <th class="px-6 py-4">Última Ejecución</th>
                <th class="px-6 py-4">Próxima Ejecución</th>
                <th class="px-6 py-4 text-right w-[280px]">Acciones</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-slate-800/60">
              @for (script of paginatedScripts; track script.id) {
                <tr class="hover:bg-slate-900/40 text-xs transition-colors">
                  <td class="px-6 py-4">
                    <span class="code-font font-semibold text-blue-300">{{ script.name }}</span>
                    <p class="text-[10px] text-slate-500 mt-1 truncate max-w-[220px]">{{ script.description }}</p>
                  </td>

                  <td class="px-6 py-4">
                    <span class="px-2 py-1 rounded-full text-[10px] bg-slate-900 border border-slate-700 text-slate-300 font-medium">
                      {{ script.category }}
                    </span>
                  </td>

                  <td class="px-6 py-4 code-font text-slate-500 text-[10px] max-w-[240px] truncate">
                    {{ script.path }}
                  </td>

                  <td class="px-6 py-4">
                    <span [class]="script.status === 'active'
                      ? 'px-2 py-1 rounded-full text-[10px] bg-emerald-950 border border-emerald-800 text-emerald-400 font-semibold'
                      : 'px-2 py-1 rounded-full text-[10px] bg-slate-800 border border-slate-700 text-slate-400 font-semibold'">
                      {{ script.status === 'active' ? 'Activo' : 'Inactivo' }}
                    </span>
                  </td>

                  <td class="px-6 py-4 text-slate-500 whitespace-nowrap">
                    {{ script.lastRun }}
                    <span [class]="lastStatusBadge(script.lastStatus)" class="ml-2">
                      {{ script.lastStatus }}
                    </span>
                  </td>

                  <td class="px-6 py-4 text-slate-400 whitespace-nowrap">
                    {{ script.nextRun }}
                  </td>

                  <td class="px-6 py-4">
                    <div class="flex items-center justify-end gap-2">
                      <button (click)="svc.openScriptDetail(script)"
                        class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] font-semibold transition">
                        Ver
                      </button>

                      <button (click)="svc.executeScript(script)"
                        class="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[11px] font-semibold transition">
                        Ejecutar
                      </button>

                      <button (click)="svc.toggleScriptStatus(script.id)"
                        [class]="script.status === 'active'
                          ? 'px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[11px] font-semibold transition'
                          : 'px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[11px] font-semibold transition'">
                        {{ script.status === 'active' ? 'Inactivar' : 'Activar' }}
                      </button>
                    </div>
                  </td>
                </tr>
              }

              @empty {
                <tr>
                  <td colspan="7" class="px-6 py-10 text-center text-slate-500 text-xs">
                    No se encontraron scripts con los filtros actuales.
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950">
          <div class="text-xs text-slate-400">
            Mostrando {{ showingFrom }} - {{ showingTo }} de {{ filteredScripts.length }} scripts
          </div>

          <div class="flex items-center gap-3">
            <button
              (click)="prevPage()"
              [disabled]="currentPage === 1"
              class="px-3 py-1.5 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-40">
              ← Anterior
            </button>

            <span class="text-xs text-slate-400">
              Página {{ currentPage }} de {{ totalPages || 1 }}
            </span>

            <button
              (click)="nextPage()"
              [disabled]="currentPage >= totalPages"
              class="px-3 py-1.5 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-40">
              Siguiente →
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class ScriptsComponent {
  searchTerm = '';
  filterCategory = 'all';
  filterStatus = 'all';

  pageSize = 8;
  currentPage = 1;

  get paginatedScripts() {
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    return this.filteredScripts.slice(start, end);
  }

  get totalPages() {
    return Math.ceil(this.filteredScripts.length / this.pageSize);
  }

  get showingFrom() {
    if (this.filteredScripts.length === 0) return 0;
    return ((this.currentPage - 1) * this.pageSize) + 1;
  }

  get showingTo() {
    return Math.min(
      this.currentPage * this.pageSize,
      this.filteredScripts.length
    );
  }

  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
    }
  }

  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
    }
  }

  constructor(public svc: PyflowService) {}

  get filteredScripts(): Script[] {
    return this.svc.scripts().filter(s => {
      const matchName = s.name.toLowerCase().includes(this.searchTerm.toLowerCase());
      const matchCat = this.filterCategory === 'all' || s.category === this.filterCategory;
      const matchStatus = this.filterStatus === 'all' || s.status === this.filterStatus;
      return matchName && matchCat && matchStatus;
    });
  }

  lastStatusBadge(status: string): string {
    const map: Record<string, string> = {
      Exitoso: 'px-1.5 py-0.5 rounded text-[9px] bg-emerald-950 text-emerald-400',
      Error: 'px-1.5 py-0.5 rounded text-[9px] bg-rose-950 text-rose-400',
      Ejecutando: 'px-1.5 py-0.5 rounded text-[9px] bg-blue-950 text-blue-400',
      Cancelado: 'px-1.5 py-0.5 rounded text-[9px] bg-slate-800 text-slate-400',
      Nunca: 'px-1.5 py-0.5 rounded text-[9px] bg-slate-800 text-slate-500',
    };
    return map[status] ?? map['Nunca'];
  }
}