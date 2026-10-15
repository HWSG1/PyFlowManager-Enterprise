import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';

@Component({
  selector: 'app-genesys-flow-select',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="rounded border border-slate-700 bg-slate-900 p-2">
        <div class="flex flex-wrap gap-2 mb-2">
          @for (item of selections(); track item.id) {
            <button type="button" (click)="remove(item.id)" class="text-xs text-blue-200 border border-blue-500 rounded px-2 py-1" [attr.aria-label]="'Quitar ' + item.name">{{ item.name }} ×</button>
          }
        </div>
      <input type="search" aria-label="Buscar por nombre o correo" placeholder="Buscar por nombre o correo..."
        [(ngModel)]="search" class="w-full bg-slate-950 text-slate-200 rounded px-2 py-1.5 text-xs mb-2">
      <select #catalogSelect aria-label="Seleccionar opción" [ngModel]="''" (ngModelChange)="choose($event, catalogSelect)"
        [disabled]="loading" class="w-full bg-slate-900 text-slate-200 text-xs py-1.5">
        <option value="">Agregar opciones (vacío = sin filtro)</option>
        @for (flow of filteredFlows(); track flow.id) {
          <option [value]="flow.id">{{ flow.name }} · {{ flow.type }} · {{ flow.id }}</option>
        }
      </select>
      @if (loading) { <p class="text-xs text-slate-400 mt-2">Cargando opciones de Genesys...</p> }
      @if (error) { <p class="text-xs text-amber-300 mt-2" role="alert">{{ error }}</p> }
      @if (!loading && !error && !filteredFlows().length) { <p class="text-xs text-slate-400 mt-2">Sin coincidencias.</p> }
      <p class="text-xs text-slate-400 mt-2">Puede agregar varias opciones y quitar cada una con ×.</p>
      @if (catalog !== 'options') {
        <button type="button" (click)="load()" [disabled]="loading" class="text-xs text-blue-400 mt-2 disabled:opacity-50">Actualizar listado</button>
      }
    </div>
  `
})
export class GenesysFlowSelectComponent implements OnChanges {
  @Input() scriptId = 0;
  @Input() value = '';
  @Input() catalog = 'flows';
  @Input() options: string[] = [];
  @Output() valueChange = new EventEmitter<string>();
  flows: { id: string; name: string; type: string }[] = [];
  search = '';
  loading = false;
  error = '';
  private request = 0;
  constructor(private svc: PyflowService) {}
  ngOnChanges(changes: any) { if (changes.scriptId || changes.catalog || changes.options) { this.flows = []; this.search = ''; this.load(); } }
  filteredFlows() {
    const term = this.search.trim().toLocaleLowerCase();
    return this.flows.filter(flow => (flow.name + ' ' + flow.type + ' ' + flow.id).toLocaleLowerCase().includes(term));
  }
  selections(): { id: string; name: string }[] {
    if (!this.value) return [];
    if (this.catalog === 'flows' || this.catalog === 'options') {
      return this.value.split(/[;,\n]/).map(id => id.trim()).filter(id => !!id && id !== 'todos' && id !== 'ambas')
        .map(id => ({ id, name: this.flows.find(item => item.id === id)?.name || id }));
    }
    try { const items = JSON.parse(this.value); if (Array.isArray(items)) return items; } catch {}
    return this.value.split(/[;,\n]/).filter(Boolean).map(name => ({ id: 'legacy:' + name, name }));
  }
  choose(id: string, select: HTMLSelectElement) {
    select.value = '';
    const option = this.flows.find(item => item.id === id);
    if (!option) return;
    const selected = this.selections();
    if (this.catalog === 'flows' || this.catalog === 'options') {
      if (!selected.some(item => item.id === id)) selected.push(option);
      this.valueChange.emit(selected.map(item => item.id).join(';'));
      return;
    }
    // Preserve old name-based selections by resolving exact catalog matches first.
    const resolved = selected.map(item => item.id.startsWith('legacy:')
      ? this.flows.find(flow => flow.name === item.name || flow.type === item.name) || item : item);
    if (resolved.some(item => item.id.startsWith('legacy:'))) {
      this.error = 'Quite los valores antiguos que no coinciden con el catálogo antes de agregar opciones.';
      return;
    }
    if (!resolved.some(item => item.id === id)) resolved.push(option);
    this.valueChange.emit(JSON.stringify(resolved.map(item => ({ id: item.id, name: item.name }))));
  }
  remove(id: string) {
    const remaining = this.selections().filter(item => item.id !== id);
    if (this.catalog === 'flows' || this.catalog === 'options') {
      this.valueChange.emit(remaining.map(item => item.id).join(';'));
      return;
    }
    this.valueChange.emit(!remaining.length ? '' : remaining.every(item => item.id.startsWith('legacy:'))
      ? remaining.map(item => item.name).join(';') : JSON.stringify(remaining));
  }
  load() {
    if (this.catalog === 'options') {
      this.flows = this.options.filter(value => value !== 'todos' && value !== 'ambas')
        .map(value => ({ id: value, name: value, type: '' }));
      return;
    }
    if (!this.scriptId) return;
    const request = ++this.request;
    this.loading = true;
    this.error = '';
    this.svc.getGenesysCatalog(this.scriptId, this.catalog).subscribe({
      next: flows => { if (request === this.request) { this.flows = flows; this.loading = false; } },
      error: err => { if (request === this.request) { this.error = err?.error?.message || 'No se pudieron cargar los flujos.'; this.loading = false; } }
    });
  }
}
