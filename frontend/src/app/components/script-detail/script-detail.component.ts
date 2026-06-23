import { Component, ElementRef, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { environment } from '../../../environments/environment';
import { ScriptGovernanceComponent } from '../script-governance/script-governance.component';

@Component({
  selector: 'app-script-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, ScriptGovernanceComponent],
  template: `
    <div class="h-full min-h-0 flex flex-col gap-4 overflow-hidden">

      <!-- Header -->
      <div class="shrink-0">
        <button
          (click)="svc.switchTab('scripts')"
          class="text-slate-400 hover:text-white text-xs font-semibold flex items-center gap-1.5 mb-2 transition-all">
          ← Regresar a la lista de scripts
        </button>

        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="p-2.5 bg-blue-600/10 text-blue-400 rounded-xl border border-blue-500/20">
              📄
            </div>

            <div>
              <h1 class="text-2xl font-bold text-white">{{ script?.name }}</h1>
              <p class="text-sm text-slate-400">{{ script?.description }}</p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              (click)="runScript()"
              [disabled]="isRunning"
              class="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs px-4 py-2.5 rounded-lg">
              ▶ Ejecutar Ahora
            </button>

            <button
              (click)="cancelExecution()"
              [disabled]="!isRunning"
              class="bg-slate-800 hover:bg-rose-900/60 disabled:opacity-50 disabled:cursor-not-allowed text-slate-300 border border-slate-700 font-semibold text-xs px-4 py-2.5 rounded-lg">
              ✕ Cancelar Ejecución
            </button>
          </div>
        </div>
      </div>

      <!-- Body -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0 overflow-hidden">

        <!-- Left Column -->
        <div class="lg:col-span-1 min-h-0 overflow-y-auto custom-scrollbar pr-2 flex flex-col gap-5">

          <!-- Status -->
          <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl shrink-0">
            <h4 class="font-semibold text-white text-sm mb-3">Estado de Ejecución Actual</h4>

            <div class="flex items-center justify-between p-3 bg-slate-900 border border-slate-800 rounded-lg">
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full" [class]="isRunning ? 'bg-blue-500 animate-pulse' : 'bg-slate-500'"></span>
                <span class="font-semibold text-sm text-slate-200">{{ statusText }}</span>
              </div>
              <span class="text-xs text-slate-500">{{ timer }}</span>
            </div>

            <div class="w-full mt-4">
              <div class="flex justify-between text-[11px] text-slate-400 mb-1">
                <span>Progreso estimado</span>
                <span>{{ progress }}%</span>
              </div>

              <div class="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
                <div class="bg-blue-500 h-full transition-all duration-300 rounded-full" [style.width.%]="progress"></div>
              </div>
            </div>
          </div>

          <!-- Script / Execution Params -->
          <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl shrink-0">
            <div class="flex items-center justify-between gap-3 mb-3">
              <h4 class="font-semibold text-white text-sm">
                {{ viewingExecutionParameters ? 'Parámetros de la Ejecución' : 'Parámetros del Script' }}
              </h4>

              @if (viewingExecutionParameters) {
                <span class="text-[10px] text-blue-400 code-font">
                  EX-{{ viewingExecutionParameters }}
                </span>
              }
            </div>

            @if (viewingExecutionParameters) {
              @if (executionParams.length === 0) {
                <div class="text-xs text-slate-500 border border-slate-800 rounded-lg p-3 bg-slate-900/40">
                  Esta ejecución no tiene parámetros registrados.
                </div>
              } @else {
                <div class="flex flex-col gap-2">
                  @for (param of executionParams; track param.id || param.param_key) {
                    <div class="border border-slate-800 rounded-lg p-3 bg-slate-900/50">
                      <div class="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                        {{ param.param_key }}
                      </div>
                      <div class="text-xs text-slate-200 code-font mt-1 break-all">
                        {{ param.param_value || '--' }}
                      </div>
                    </div>
                  }
                </div>
              }
            } @else if (scriptParams.length === 0) {
              <div class="text-xs text-slate-500 border border-slate-800 rounded-lg p-3 bg-slate-900/40">
                No existen parámetros configurados para este script.
              </div>
            } @else {
              <div class="flex flex-col gap-3">
                @for (param of scriptInputParams(); track param.id) {
                  <div>
                    <label class="text-xs text-slate-400 font-semibold block mb-1">
                      {{ param.label || param.param_key }}
                      @if (param.is_required) {
                        <span class="text-rose-400">*</span>
                      }
                    </label>

                    @if (param.control_type === 'select') {
                      <select
                        [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                        <option value="">Seleccione...</option>
                        @for (opt of parseOptions(param.options_json); track opt) {
                          <option [value]="opt">{{ opt }}</option>
                        }
                      </select>
                    } @else if (param.control_type === 'date') {
                      <input type="date" [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                    } @else if (param.control_type === 'datetime') {
                      <input type="datetime-local" [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                    } @else if (param.control_type === 'number') {
                      <input type="number" [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                    } @else if (param.control_type === 'textarea') {
                      <textarea rows="3" [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"></textarea>
                    } @else if (param.control_type === 'tags') {
                      <div class="bg-slate-900 border border-slate-800 rounded-lg p-2.5 min-h-[88px] focus-within:border-blue-500">
                        <div class="flex flex-wrap gap-2 mb-2 min-h-[28px]">
                          @for (tag of tagItems(param.param_key); track tag) {
                            <span class="inline-flex items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/10 px-2.5 py-1 text-[11px] text-blue-100 max-w-full">
                              <span class="truncate max-w-[220px]">{{ tag }}</span>
                              <button
                                type="button"
                                (click)="removeTagValue(param.param_key, tag)"
                                class="text-blue-200 hover:text-rose-300 leading-none">
                                ×
                              </button>
                            </span>
                          } @empty {
                            <span class="text-[11px] text-slate-500 py-1">
                              Sin filtros agregados.
                            </span>
                          }
                        </div>

                        <div class="flex gap-2">
                          <input
                            type="text"
                            [(ngModel)]="tagDraftValues[param.param_key]"
                            (keydown)="onTagInputKeydown($event, param.param_key)"
                            placeholder="Buscar o agregar valor..."
                            class="min-w-0 flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">

                          <button
                            type="button"
                            (click)="addTagValue(param.param_key)"
                            class="shrink-0 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs px-3 py-1.5 rounded">
                            Agregar
                          </button>
                        </div>
                      </div>
                    } @else {
                      <input type="text" [(ngModel)]="paramValues[param.param_key]"
                        class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                    }
                  </div>
                }

                @if (sortedGlobalParams().length > 0) {
                  <div class="pt-2 border-t border-slate-800/70">
                    <div class="text-[10px] uppercase tracking-wide text-slate-500 font-semibold mb-2">Variables globales</div>
                    <div class="flex flex-col gap-3">
                      @for (param of sortedGlobalParams(); track param.id) {
                        <div [class]="globalParamClass(param)">
                          <div [class]="globalParamTitleClass(param)">
                            {{ isGlobalParamConfigured(param) ? '✓ Variable global configurada:' : '✕ Variable global no configurada:' }}
                          </div>
                          <div class="text-xs text-slate-200 code-font mt-1">
                            {{ globalParamKey(param) }}
                          </div>
                          @if (!isGlobalParamConfigured(param)) {
                            <div class="text-[11px] text-rose-300 mt-2">
                              Agrega esta variable en Configuración para poder ejecutar el script.
                            </div>
                          }
                        </div>
                      }
                    </div>
                  </div>
                }
              </div>
            }
          </div>

          <!-- Script Info -->
          <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl shrink-0">
            <h4 class="font-semibold text-white text-sm mb-3">Información del Script</h4>

            <div class="flex flex-col gap-2 text-xs">
              <div class="flex justify-between">
                <span class="text-slate-400">Autor:</span>
                <span class="text-slate-200 font-medium">{{ script?.author }}</span>
              </div>

              <div class="flex justify-between">
                <span class="text-slate-400">Versión:</span>
                <span class="text-slate-200 font-medium code-font">{{ script?.version }}</span>
              </div>

              <div class="flex justify-between">
                <span class="text-slate-400">Categoría:</span>
                <span class="text-slate-200 font-medium">{{ script?.category }}</span>
              </div>

              <div class="flex justify-between">
                <span class="text-slate-400">Éxitos Totales:</span>
                <span class="text-emerald-400 font-bold">{{ script?.successCount }}</span>
              </div>

              <div class="flex justify-between">
                <span class="text-slate-400">Errores Totales:</span>
                <span class="text-rose-400 font-bold">{{ script?.errorCount }}</span>
              </div>

              <div class="flex justify-between">
                <span class="text-slate-400">Duración Prom.:</span>
                <span class="text-slate-200 font-medium">{{ script?.avgDuration }}</span>
              </div>
            </div>
          </div>

          @if (script?.id) {
            <app-script-governance [scriptId]="script!.id" />
          }

          <!-- Danger Zone -->
          <div class="bg-rose-950/20 border border-rose-900/60 p-5 rounded-xl shrink-0 mb-2">
            <h4 class="font-semibold text-rose-300 text-sm mb-2">Zona peligrosa</h4>

            <p class="text-xs text-slate-400 mb-4">
              Esta acción eliminará definitivamente el script, sus versiones y el archivo físico.
            </p>

            <button
              (click)="showDeleteConfirm = true"
              class="w-full bg-rose-600/20 hover:bg-rose-600/30 border border-rose-700 text-rose-300 font-semibold text-xs px-4 py-2.5 rounded-lg transition-all">
              Eliminar Script Definitivamente
            </button>

            @if (showDeleteConfirm) {
              <div class="mt-4 border border-rose-900 bg-slate-950 rounded-lg p-4">
                <p class="text-xs text-slate-300 mb-3">
                  Para confirmar, escribe <b class="text-rose-300">ELIMINAR</b>.
                </p>

                <input
                  type="text"
                  [(ngModel)]="deleteConfirmText"
                  placeholder="ELIMINAR"
                  class="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-rose-500 mb-3">

                <div class="flex justify-end gap-2">
                  <button
                    (click)="cancelDeleteConfirm()"
                    class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold">
                    Cancelar
                  </button>

                  <button
                    (click)="deleteScriptDefinitively()"
                    [disabled]="deleteConfirmText !== 'ELIMINAR'"
                    class="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold">
                    Eliminar
                  </button>
                </div>
              </div>
            }
          </div>
        </div>

        <!-- Right Column -->
        <div class="lg:col-span-2 min-h-0 overflow-hidden flex flex-col gap-5">

          <!-- Console -->
          <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col shrink-0">
            <div class="px-5 py-3 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span class="text-xs text-slate-400 ml-2 code-font">pyflow_console — {{ script?.name }}</span>
              </div>

              <button (click)="clearConsole()" class="text-slate-500 hover:text-slate-300 text-xs">
                Limpiar
              </button>
            </div>

            <div
              #consolePane
              (scroll)="onConsoleScroll()"
              class="h-[360px] overflow-y-auto custom-scrollbar bg-slate-950/80 p-4 code-font text-xs leading-relaxed flex flex-col gap-1">
              @for (line of consoleLines; track $index) {
                <div [class]="line.cls">{{ line.text }}</div>
              }
            </div>
          </div>

          <!-- Recent executions -->
          <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col flex-1 min-h-0">
            <div class="px-5 py-4 border-b border-slate-800 shrink-0">
              <h4 class="font-semibold text-white text-sm">Últimas Ejecuciones de este Script</h4>
            </div>

            <div class="flex-1 min-h-0 overflow-auto custom-scrollbar">
              <table class="w-full text-xs text-slate-300">
                <thead class="bg-slate-900/80 text-[10px] font-semibold uppercase text-slate-400 border-b border-slate-800 sticky top-0 z-10">
                  <tr>
                    <th class="px-5 py-3 text-left">ID</th>
                    <th class="px-5 py-3 text-left">Estado</th>
                    <th class="px-5 py-3 text-left">Inicio</th>
                    <th class="px-5 py-3 text-left">Duración</th>
                    <th class="px-5 py-3 text-left">Mensaje</th>
                    <th class="px-5 py-3 text-left">Log</th>
                  </tr>
                </thead>

                <tbody class="divide-y divide-slate-800/60">
                  @for (ex of scriptExecutions; track ex.id) {
                    <tr class="hover:bg-slate-900/40">
                      <td class="px-5 py-3 code-font text-slate-400">{{ ex.id }}</td>

                      <td class="px-5 py-3">
                        <span [class]="statusBadge(ex.status)">{{ ex.status }}</span>
                      </td>

                      <td class="px-5 py-3 text-slate-500">{{ ex.start }}</td>

                      <td class="px-5 py-3 font-semibold">{{ ex.duration }}</td>

                      <td class="px-5 py-3 text-slate-500 truncate max-w-[220px]">
                        {{ ex.message }}
                      </td>

                      <td class="px-5 py-3">
                        <button
                          (click)="openExecutionLog(ex.id)"
                          class="text-blue-400 hover:text-blue-300 font-semibold text-xs">
                          Ver Log
                        </button>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  `
})
export class ScriptDetailComponent implements OnInit, OnDestroy {
  @ViewChild('consolePane') consolePane?: ElementRef<HTMLDivElement>;

  isRunning = false;
  progress = 0;
  timer = '--:--';
  statusText = 'Detenido / En espera';
  showDeleteConfirm = false;
  deleteConfirmText = '';


  consoleLines: { text: string; cls: string }[] = [
    { text: '[SYSTEM] Consola lista. Esperando ejecución...', cls: 'text-slate-500' }
  ];

  scriptParams: any[] = [];
  executionParams: any[] = [];
  viewingExecutionParameters: number | null = null;
  paramValues: Record<string, any> = {};
  tagDraftValues: Record<string, string> = {};

  private intervalId: ReturnType<typeof setInterval> | null = null;
  private eventSource: EventSource | null = null;
  private currentExecutionId: number | null = null;
  private consoleSessionId = 0;
  private shouldFollowConsole = true;

  constructor(public svc: PyflowService) {}

  ngOnInit() {
    this.loadScriptParameters();

    const selectedExecutionId = this.svc.consumeSelectedExecutionLogId();
    if (selectedExecutionId !== null) {
      this.openExecutionLog(selectedExecutionId);
    }
  }

  get script() {
    return this.svc.selectedScript();
  }

  get scriptExecutions() {
    return this.svc.executions().filter(e => e.script === this.script?.name);
  }

  isGlobalParam(param: any): boolean {
    return String(param?.control_type || '').toLowerCase() === 'global' ||
      String(param?.param_type || '').toLowerCase() === 'global' ||
      !!String(param?.global_key || '').trim();
  }

  scriptInputParams(): any[] {
    return this.scriptParams.filter(param => !this.isGlobalParam(param));
  }

  sortedGlobalParams(): any[] {
    return this.scriptParams
      .filter(param => this.isGlobalParam(param))
      .sort((a, b) => {
        const aConfigured = this.isGlobalParamConfigured(a) ? 1 : 0;
        const bConfigured = this.isGlobalParamConfigured(b) ? 1 : 0;

        if (aConfigured !== bConfigured) {
          return aConfigured - bConfigured;
        }

        return this.globalParamKey(a).localeCompare(this.globalParamKey(b));
      });
  }

  globalParamKey(param: any): string {
    return String(param?.global_key || param?.param_key || '').trim();
  }

  isGlobalParamConfigured(param: any): boolean {
    const key = this.globalParamKey(param).toLowerCase();
    if (!key) return false;

    return this.svc.envParams().some(item =>
      String(item.key || '').trim().toLowerCase() === key
    );
  }

  globalParamClass(param: any): string {
    const base = 'border rounded-lg p-3';

    return this.isGlobalParamConfigured(param)
      ? `${base} border-emerald-900/60 bg-emerald-950/20`
      : `${base} border-rose-900/70 bg-rose-950/20`;
  }

  globalParamTitleClass(param: any): string {
    return this.isGlobalParamConfigured(param)
      ? 'text-xs text-emerald-400 font-semibold'
      : 'text-xs text-rose-400 font-semibold';
  }

  tagItems(key: string): string[] {
    return String(this.paramValues[key] || '')
      .split(';')
      .map(value => value.trim())
      .filter(Boolean);
  }

  addTagValue(key: string) {
    const draft = String(this.tagDraftValues[key] || '').trim();
    if (!draft) return;

    const current = this.tagItems(key);
    const incoming = draft
      .replace(/\r?\n/g, ';')
      .replace(/,/g, ';')
      .split(';')
      .map(value => value.trim())
      .filter(Boolean);

    for (const value of incoming) {
      if (!current.includes(value)) {
        current.push(value);
      }
    }

    this.paramValues[key] = current.join(';');
    this.tagDraftValues[key] = '';
  }

  removeTagValue(key: string, value: string) {
    this.paramValues[key] = this.tagItems(key)
      .filter(item => item !== value)
      .join(';');
  }

  onTagInputKeydown(event: KeyboardEvent, key: string) {
    if (['Enter', 'Tab', ',', ';'].includes(event.key)) {
      event.preventDefault();
      this.addTagValue(key);
    }
  }

  loadScriptParameters() {
    const script = this.script;
    if (!script) return;

    this.svc.getScriptParameters(script.id).subscribe({
      next: params => {
        this.scriptParams = params || [];

        this.paramValues = {};
        this.tagDraftValues = {};

        for (const p of this.scriptParams) {
          if (!this.isGlobalParam(p)) {
            this.paramValues[p.param_key] = p.param_value || '';
          }
        }
      },
      error: err => {
        this.svc.showToast(
          `Error cargando parámetros: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  parseOptions(optionsJson: string | null): string[] {
    if (!optionsJson) return [];

    try {
      const parsed = JSON.parse(optionsJson);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  validateParameters(): boolean {
    const missing = this.scriptParams.filter(p =>
      !this.isGlobalParam(p) &&
      p.is_required &&
      !String(this.paramValues[p.param_key] ?? '').trim()
    );

    if (missing.length > 0) {
      this.svc.showToast('Debe completar los parámetros obligatorios.', 'error');
      return false;
    }

    return true;
  }

  clearConsole() {
    this.consoleLines = [
      { text: '[SYSTEM] Consola limpiada.', cls: 'text-slate-500' }
    ];
    this.shouldFollowConsole = true;
    this.scrollConsoleToBottom(true);
  }

  onConsoleScroll() {
    const el = this.consolePane?.nativeElement;
    if (!el) return;

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    this.shouldFollowConsole = distanceFromBottom < 24;
  }

  private scrollConsoleToBottom(force = false) {
    if (!force && !this.shouldFollowConsole) return;

    setTimeout(() => {
      const el = this.consolePane?.nativeElement;
      if (!el) return;

      el.scrollTop = el.scrollHeight;
    }, 0);
  }

  private readProgress(message: any): number | null {
    const match = String(message || '').trim().match(/^PYFLOW_PROGRESS=(\d{1,3})(?:\.\d+)?$/i);
    if (!match) return null;

    const progress = Number(match[1]);
    if (!Number.isFinite(progress)) return null;

    return Math.max(0, Math.min(100, progress));
  }

  private stopConsoleWatch() {
    this.consoleSessionId++;

    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  runScript() {
  if (!this.script || this.isRunning) return;

  if (!this.validateParameters()) {
    return;
  }

  const token =
    localStorage.getItem('pyflow_token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('access_token') ||
    localStorage.getItem('auth_token');

  if (!token) {
    this.svc.showToast('Sesión inválida o expirada. Inicia sesión nuevamente.', 'error');
    return;
  }

  this.stopConsoleWatch();
  this.viewingExecutionParameters = null;
  this.executionParams = [];
  this.consoleLines = [];
  this.shouldFollowConsole = true;
  this.scrollConsoleToBottom(true);
  this.statusText = 'Iniciando...';
  this.progress = 5;
  this.isRunning = true;

  this.svc.showToast(`Ejecutando ${this.script.name}`, 'info');

  fetch(`${environment.apiUrl}/scripts/${this.script.id}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      parameters: this.paramValues
    })
  })
    .then(async r => {
      const data = await r.json().catch(() => ({}));

      if (!r.ok) {
        throw new Error(data?.message || data?.error || `Error HTTP ${r.status}`);
      }

      return data;
    })
    .then(result => {
      const executionId =
        result?.executionId ??
        result?.execution_id ??
        result?.id;

      if (!executionId) {
        console.error('Respuesta sin executionId:', result);
        throw new Error('El backend no devolvió el ID de ejecución.');
      }

      this.currentExecutionId = Number(executionId);

      this.consoleLines.push({
        text: `[SYSTEM] Ejecución EX-${executionId} iniciada`,
        cls: 'text-blue-400'
      });

      this.scrollConsoleToBottom();
      this.connectExecutionStream(Number(executionId));
    })
    .catch(err => {
      this.isRunning = false;
      this.statusText = 'Error';
      this.progress = 0;

      console.log('TOKEN:', token);
      this.consoleLines.push({
        text: `[ERROR] ${err.message}`,
        cls: 'text-red-400'
      });

      this.scrollConsoleToBottom();
      this.svc.showToast(err.message, 'error');
    });
}

  connectExecutionStream(executionId: number) {
    this.stopConsoleWatch();
    const sessionId = this.consoleSessionId;

    const seen = new Set<string>();

    const loadLogsFromDb = () => {
      this.svc.getExecutionLogs(executionId).subscribe({
        next: rows => {
          if (sessionId !== this.consoleSessionId || this.currentExecutionId !== executionId) return;

          for (const row of rows) {
            const key = `${row.id}-${row.message}`;

            if (seen.has(key)) continue;
            seen.add(key);

            const progress = this.readProgress(row.message);
            if (progress !== null) {
              this.progress = progress;
              continue;
            }

            let css = 'text-slate-300';

            if (row.log_level === 'ERROR') css = 'text-red-400';
            if (row.log_level === 'WARNING') css = 'text-amber-400';
            if (row.message?.toLowerCase().includes('exitosamente')) {
              css = 'text-emerald-400 font-bold';
            }

            this.consoleLines.push({
              text: `[${row.log_level}] ${row.message}`,
              cls: css
            });
            this.scrollConsoleToBottom();
          }

          this.scrollConsoleToBottom();
        }
      });
    };

    loadLogsFromDb();

    this.intervalId = setInterval(() => {
      loadLogsFromDb();
      this.svc.loadExecutions();
    }, 2000);

    const token = encodeURIComponent(localStorage.getItem('pyflow_token') || '');
    this.eventSource = new EventSource(`${environment.apiUrl}/executions/${executionId}/stream?access_token=${token}`);

    this.eventSource.onmessage = event => {
      if (sessionId !== this.consoleSessionId || this.currentExecutionId !== executionId) return;

      const payload = JSON.parse(event.data);

      if (payload.progress !== undefined) {
        const progress = Number(payload.progress);
        if (Number.isFinite(progress)) {
          this.progress = Math.max(0, Math.min(100, progress));
          this.statusText = 'Ejecutando';
        }
        return;
      }

      const progressFromMessage = this.readProgress(payload.message);
      if (progressFromMessage !== null) {
        this.progress = progressFromMessage;
        this.statusText = 'Ejecutando';
        return;
      }

      if (payload.done) {
        this.isRunning = false;
        this.progress = 100;
        this.statusText = payload.status;

        if (this.intervalId) {
          clearInterval(this.intervalId);
          this.intervalId = null;
        }

        this.eventSource?.close();
        this.eventSource = null;

        loadLogsFromDb();
        this.svc.loadExecutions();
        this.svc.loadScripts();
      }
    };

    this.eventSource.onerror = () => {
      if (sessionId !== this.consoleSessionId || this.currentExecutionId !== executionId) return;

      this.eventSource?.close();
      this.eventSource = null;
    };
  }

  cancelExecution() {
    if (!this.isRunning || !this.currentExecutionId) return;

    this.svc.cancelExecution(this.currentExecutionId).subscribe({
      next: () => {
        this.isRunning = false;
        this.statusText = 'Cancelado';
        this.progress = 100;

        this.consoleLines.push({
          text: '[CANCELLED] Ejecución cancelada manualmente.',
          cls: 'text-amber-400'
        });
        this.scrollConsoleToBottom();

        this.stopConsoleWatch();

        this.svc.loadExecutions();
        this.svc.loadScripts();
      },
      error: err => {
        this.consoleLines.push({
          text: `[ERROR] No se pudo cancelar: ${err?.error?.message || err.message}`,
          cls: 'text-red-400'
        });
        this.scrollConsoleToBottom();
      }
    });
  }

  ngOnDestroy() {
    this.stopConsoleWatch();
  }

  statusBadge(status: string): string {
    const map: Record<string, string> = {
      Exitoso: 'px-2 py-0.5 rounded-full text-[10px] bg-emerald-950 border border-emerald-900 text-emerald-400 font-medium',
      Error: 'px-2 py-0.5 rounded-full text-[10px] bg-rose-950 border border-rose-900 text-rose-400 font-medium',
      Ejecutando: 'px-2 py-0.5 rounded-full text-[10px] bg-blue-950 border border-blue-900 text-blue-400 font-medium',
      Cancelado: 'px-2 py-0.5 rounded-full text-[10px] bg-slate-900 border border-slate-800 text-slate-400 font-medium'
    };

    return map[status] ?? map['Cancelado'];
  }
  openExecutionLog(executionId: string | number) {
    const cleanId = Number(String(executionId).replace('EX-', ''));

    this.currentExecutionId = cleanId;
    this.stopConsoleWatch();
    this.clearConsole();
    this.shouldFollowConsole = true;
    this.loadExecutionParametersForLog(cleanId);
    const sessionId = this.consoleSessionId;

    const loadLogs = () => {
      this.svc.getExecutionLogs(cleanId).subscribe({
        next: rows => {
          if (sessionId !== this.consoleSessionId || this.currentExecutionId !== cleanId) return;

          this.consoleLines = [];

          if (!rows || rows.length === 0) {
            this.consoleLines.push({
              text: `[SYSTEM] No hay logs registrados para EX-${cleanId}.`,
              cls: 'text-slate-500'
            });
            this.scrollConsoleToBottom();
          }

          for (const row of rows) {
            const progress = this.readProgress(row.message);
            if (progress !== null) {
              this.progress = progress;
              continue;
            }

            let css = 'text-slate-300';

            if (row.log_level === 'ERROR') css = 'text-red-400';
            if (row.log_level === 'WARNING') css = 'text-amber-400';
            if (row.message?.toLowerCase().includes('exitosamente')) {
              css = 'text-emerald-400 font-bold';
            }

            this.consoleLines.push({
              text: `[${row.log_level}] ${row.message}`,
              cls: css
            });
            this.scrollConsoleToBottom();
          }

          this.svc.loadExecutions();

          const selectedExecution = this.scriptExecutions.find(
            ex => String(ex.id).replace('EX-', '') === String(cleanId)
          );

          if (selectedExecution?.status === 'Ejecutando') {
            this.isRunning = true;
            this.statusText = 'Ejecutando';
            this.progress = 50;
          } else {
            this.isRunning = false;
            this.statusText = selectedExecution?.status || 'Detenido / En espera';

            if (selectedExecution?.status === 'Exitoso' || selectedExecution?.status === 'Cancelado') {
              this.progress = 100;
            }
          }

          this.scrollConsoleToBottom();
        }
      });
    };

    loadLogs();

    this.intervalId = setInterval(() => {
      loadLogs();
      this.svc.loadScripts();
    }, 2000);
  }

  cancelDeleteConfirm() {
  this.showDeleteConfirm = false;
  this.deleteConfirmText = '';
}

  loadExecutionParametersForLog(executionId: number) {
    this.viewingExecutionParameters = executionId;
    this.executionParams = [];

    this.svc.getExecutionParameters(executionId).subscribe({
      next: rows => {
        if (this.viewingExecutionParameters !== executionId) return;
        this.executionParams = rows || [];
      },
      error: err => {
        if (this.viewingExecutionParameters !== executionId) return;

        this.svc.showToast(
          `Error cargando parametros de ejecucion: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  deleteScriptDefinitively() {
    if (!this.script || this.deleteConfirmText !== 'ELIMINAR') return;

    this.svc.deleteScriptDefinitively(this.script.id).subscribe({
      next: () => {
        this.svc.showToast('Script eliminado definitivamente.', 'success');
        this.svc.loadScripts();
        this.svc.switchTab('scripts');
      },
      error: err => {
        this.svc.showToast(
          `Error eliminando script: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }
  
}



