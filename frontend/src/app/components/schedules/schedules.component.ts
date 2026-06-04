import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { Schedule } from '../../models/models';

@Component({
  selector: 'app-schedules',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-6">
      <div>
        <h1 class="text-2xl font-bold text-white">Programaciones y Automatización</h1>
        <p class="text-sm text-slate-400">
          Define reglas de ejecución automática usando expresiones CRON o intervalos.
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="flex flex-col gap-4">
          <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl flex flex-col gap-4">
            <h3 class="font-semibold text-white flex items-center gap-2">
              @if (svc.editingScheduleId()) {
                Editar Programación #{{ svc.editingScheduleId() }}
              } @else {
                Nueva Programación
              }
            </h3>

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Script Objetivo</label>
              <select
                [(ngModel)]="newSchedule.scriptId"
                (ngModelChange)="onScriptChange()"
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                <option [ngValue]="null">Seleccione un script...</option>
                @for (s of svc.scripts(); track s.id) {
                  <option [ngValue]="s.id">{{ s.name }}</option>
                }
              </select>
            </div>

            @if (scheduleParameters.length) {
              <div class="border border-slate-800 rounded-lg p-3 bg-slate-900/30">
                <h4 class="text-xs font-semibold text-slate-300 mb-3">
                  Parámetros de la programación
                </h4>

                @for (p of scheduleParameters; track p.param_key) {
                  <div class="mb-3">
                    <label class="text-xs text-slate-400 block mb-1">
                      {{ p.label || p.param_key }}
                      @if (p.is_required) {
                        <span class="text-rose-400">*</span>
                      }
                    </label>

                    @if (p.control_type === 'select') {
                      <select
                        [(ngModel)]="p.value"
                        class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                        @for (opt of getOptions(p); track opt) {
                          <option [value]="opt">{{ opt }}</option>
                        }
                      </select>
                    } @else if (p.control_type === 'textarea') {
                      <textarea
                        [(ngModel)]="p.value"
                        rows="3"
                        class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                      </textarea>
                    } @else {
                      <input
                        [type]="getInputType(p.control_type)"
                        [(ngModel)]="p.value"
                        class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                    }

                    <p class="text-[10px] text-slate-500 mt-1 code-font">
                      {{ p.param_key }}
                    </p>
                  </div>
                }
              </div>
            }

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Tipo de Frecuencia</label>
              <select
                [(ngModel)]="newSchedule.frequencyType"
                (ngModelChange)="onFrequencyChange()"
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                <option value="daily">Diario</option>
                <option value="hourly">Cada hora</option>
                <option value="weekly">Semanal</option>
                <option value="interval">Cada X minutos</option>
                <option value="cron">CRON personalizado</option>
              </select>
            </div>

            @if (newSchedule.frequencyType === 'daily') {
              <div>
                <label class="text-xs text-slate-400 font-semibold block mb-1">Hora diaria</label>
                <input
                  type="time"
                  [(ngModel)]="newSchedule.time"
                  (ngModelChange)="buildCronFromControls()"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
              </div>
            }

            @if (newSchedule.frequencyType === 'weekly') {
              <div>
                <label class="text-xs text-slate-400 font-semibold block mb-1">Día de la semana</label>
                <select
                  [(ngModel)]="newSchedule.weekDay"
                  (ngModelChange)="buildCronFromControls()"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                  <option value="1">Lunes</option>
                  <option value="2">Martes</option>
                  <option value="3">Miércoles</option>
                  <option value="4">Jueves</option>
                  <option value="5">Viernes</option>
                  <option value="6">Sábado</option>
                  <option value="0">Domingo</option>
                </select>

                <label class="text-xs text-slate-400 font-semibold block mt-3 mb-1">Hora</label>
                <input
                  type="time"
                  [(ngModel)]="newSchedule.time"
                  (ngModelChange)="buildCronFromControls()"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
              </div>
            }

            @if (newSchedule.frequencyType === 'interval') {
              <div>
                <label class="text-xs text-slate-400 font-semibold block mb-1">Intervalo en minutos</label>
                <input
                  type="number"
                  min="1"
                  [(ngModel)]="newSchedule.intervalMinutes"
                  (ngModelChange)="buildCronFromControls()"
                  class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
              </div>
            }

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Expresión CRON</label>
              <input
                type="text"
                [(ngModel)]="newSchedule.cron"
                [readonly]="newSchedule.frequencyType !== 'cron'"
                placeholder="30 2 * * *"
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs code-font text-slate-300 focus:outline-none focus:border-blue-500"
                [class.cursor-not-allowed]="newSchedule.frequencyType !== 'cron'">
              <p class="text-[10px] text-slate-500 mt-1">
                Formato: minuto hora día mes día-semana
              </p>
            </div>

            <div>
              <label class="text-xs text-slate-400 font-semibold block mb-1">Próxima Ejecución Estimada</label>
              <div class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-400">
                {{ getEstimatedNextRunLabel() }}
              </div>
              <p class="text-[10px] text-slate-500 mt-1">
                Este valor lo calcula el backend automáticamente al guardar.
              </p>
            </div>

            @if (svc.editingScheduleId()) {
              <div class="flex gap-2">
                <button
                  (click)="saveSchedule()"
                  class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2.5 rounded-lg">
                  Guardar Cambios
                </button>
                <button
                  (click)="cancelEdit()"
                  class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold px-4 rounded-lg">
                  Cancelar
                </button>
              </div>
            } @else {
              <button
                (click)="saveSchedule()"
                class="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2.5 rounded-lg flex items-center justify-center gap-1.5 shadow transition-all mt-1">
                + Guardar Programación
              </button>
            }
          </div>
        </div>

        <div class="lg:col-span-2">
          <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
              <h4 class="font-semibold text-white text-sm">
                Cronogramas de Ejecución
              </h4>

              <div class="flex flex-col md:flex-row gap-2">
                <input
                  type="text"
                  [(ngModel)]="scheduleNameFilter"
                  (ngModelChange)="currentPage = 1"
                  placeholder="Filtrar por nombre..."
                  class="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">

                <select
                  [(ngModel)]="scheduleStatusFilter"
                  (ngModelChange)="currentPage = 1"
                  class="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                  <option value="all">Todos</option>
                  <option value="active">Activos</option>
                  <option value="paused">Inactivos</option>
                </select>
              </div>
            </div>

            <div class="overflow-x-auto">
              <table class="w-full text-left text-sm text-slate-300">
                <thead class="bg-slate-900/60 text-xs font-semibold uppercase text-slate-400 border-b border-slate-800">
                  <tr>
                    <th class="px-6 py-3.5">Script</th>
                    <th class="px-6 py-3.5">Frecuencia</th>
                    <th class="px-6 py-3.5">Siguiente Ejecución</th>
                    <th class="px-6 py-3.5">Estado</th>
                    <th class="px-6 py-3.5 text-right">Acción</th>
                  </tr>
                </thead>

                <tbody class="divide-y divide-slate-800/60">
                  @for (s of paginatedSchedules; track s.id) {
                    <tr class="hover:bg-slate-900/40 text-xs">
                      <td class="px-6 py-3.5 code-font font-semibold text-blue-300">
                        {{ s.scriptName }}
                      </td>

                      <td class="px-6 py-3.5 text-slate-400">
                        {{ s.frequency }}
                      </td>

                      <td class="px-6 py-3.5 text-amber-400 font-semibold">
                        {{ s.nextRun }}
                      </td>

                      <td class="px-6 py-3.5">
                        <span
                          class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                          [class.bg-emerald-950]="s.status === 'active'"
                          [class.border]="true"
                          [class.border-emerald-900]="s.status === 'active'"
                          [class.text-emerald-400]="s.status === 'active'"
                          [class.bg-slate-900]="s.status !== 'active'"
                          [class.border-slate-700]="s.status !== 'active'"
                          [class.text-slate-400]="s.status !== 'active'">
                          {{ s.status === 'active' ? 'Activo' : 'Pausado' }}
                        </span>
                      </td>

                      <td class="px-6 py-3.5 text-right">
                        <div class="flex gap-2 justify-end">
                          <button
                            (click)="editSchedule(s.id)"
                            class="
                              px-3 py-1.5
                              text-[11px]
                              font-semibold
                              rounded-lg
                              bg-slate-800
                              border border-slate-700
                              text-white
                              hover:bg-slate-700
                              transition-all">
                            Editar
                          </button>

                          <button
                            (click)="toggleSchedule(s)"
                            class="
                              px-3 py-1.5
                              text-[11px]
                              font-semibold
                              rounded-lg
                              transition-all
                            "
                            [ngClass]="
                              s.status === 'active'
                                ? 'bg-amber-950 border border-amber-800 text-amber-400 hover:bg-amber-900'
                                : 'bg-emerald-950 border border-emerald-800 text-emerald-400 hover:bg-emerald-900'
                            ">
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="5" class="px-6 py-6 text-center text-xs text-slate-500">
                        No hay programaciones que coincidan con el filtro.
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>

            <div class="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950">
              <div class="text-xs text-slate-400">
                Mostrando {{ showingFrom }} - {{ showingTo }} de {{ getFilteredSchedules().length }} programaciones
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
      </div>
    </div>
  `
})
export class SchedulesComponent {
  newSchedule: {
    scriptId: number | null;
    frequencyType: string;
    cron: string;
    time: string;
    weekDay: string;
    intervalMinutes: number;
  } = this.getEmptyScheduleForm();

  scheduleParameters: any[] = [];
  scheduleNameFilter = '';
  scheduleStatusFilter = 'all';


  pageSize = 6;
  currentPage = 1;

  get paginatedSchedules() {
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    return this.getFilteredSchedules().slice(start, end);
  }

  get totalPages() {
    return Math.ceil(this.getFilteredSchedules().length / this.pageSize);
  }

  get showingFrom() {
    if (this.getFilteredSchedules().length === 0) return 0;
    return ((this.currentPage - 1) * this.pageSize) + 1;
  }

  get showingTo() {
    return Math.min(
      this.currentPage * this.pageSize,
      this.getFilteredSchedules().length
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

  getEmptyScheduleForm() {
    return {
      scriptId: null as number | null,
      frequencyType: 'daily',
      cron: '30 2 * * *',
      time: '02:30',
      weekDay: '1',
      intervalMinutes: 60
    };
  }

  resetScheduleForm() {
    this.svc.clearEditingSchedule();
    this.newSchedule = this.getEmptyScheduleForm();
    this.scheduleParameters = [];
    this.buildCronFromControls();
  }

  constructor(public svc: PyflowService) {
    this.buildCronFromControls();
  }

  onScriptChange() {
    this.loadScriptParameters();
  }

  loadScriptParameters() {
    if (!this.newSchedule.scriptId) {
      this.scheduleParameters = [];
      return;
    }

    this.svc.getScriptParameters(Number(this.newSchedule.scriptId)).subscribe({
      next: params => {
        this.scheduleParameters = params
          .filter(p => p.control_type !== 'global')
          .map(p => ({
            ...p,
            value: p.param_value || this.getDefaultValue(p)
          }));
      },
      error: err => {
        this.scheduleParameters = [];
        this.svc.showToast(
          `Error cargando parámetros: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  getDefaultValue(param: any): string {
    const options = this.getOptions(param);

    if (param.control_type === 'select' && options.length) {
      return options[0];
    }

    return '';
  }

  getOptions(param: any): string[] {
    if (!param.options_json) return [];

    try {
      const parsed = JSON.parse(param.options_json);

      if (Array.isArray(parsed)) {
        return parsed.map(x => String(x));
      }

      if (Array.isArray(parsed.options)) {
        return parsed.options.map((x: any) => String(x));
      }

      return [];
    } catch {
      return [];
    }
  }

  getInputType(controlType: string): string {
    if (controlType === 'date') return 'date';
    if (controlType === 'datetime') return 'datetime-local';
    if (controlType === 'number') return 'number';

    return 'text';
  }

  onFrequencyChange() {
    this.buildCronFromControls();
  }

  buildCronFromControls() {
    if (this.newSchedule.frequencyType === 'daily') {
      const [hour, minute] = this.newSchedule.time.split(':');
      this.newSchedule.cron = `${Number(minute)} ${Number(hour)} * * *`;
    }

    if (this.newSchedule.frequencyType === 'hourly') {
      this.newSchedule.cron = `0 * * * *`;
    }

    if (this.newSchedule.frequencyType === 'weekly') {
      const [hour, minute] = this.newSchedule.time.split(':');
      this.newSchedule.cron = `${Number(minute)} ${Number(hour)} * * ${this.newSchedule.weekDay}`;
    }

    if (this.newSchedule.frequencyType === 'interval') {
      const minutes = Number(this.newSchedule.intervalMinutes || 1);
      this.newSchedule.cron = `*/${minutes} * * * *`;
    }
  }

  parseCronToControls(cron: string) {

    if (!cron) return;

    const parts = cron.trim().split(' ');

    if (parts.length !== 5) return;

    const minute = parts[0];
    const hour = parts[1];
    const day = parts[2];
    const month = parts[3];
    const weekDay = parts[4];

    // Cada X minutos
    if (minute.startsWith('*/')) {

      this.newSchedule.frequencyType = 'interval';
      this.newSchedule.intervalMinutes =
        Number(minute.replace('*/', ''));

      return;
    }

    // Cada hora
    if (
      minute === '0' &&
      hour === '*'
    ) {

      this.newSchedule.frequencyType = 'hourly';
      return;
    }

    // Semanal
    if (
      day === '*' &&
      month === '*' &&
      weekDay !== '*'
    ) {

      this.newSchedule.frequencyType = 'weekly';

      this.newSchedule.weekDay = weekDay;

      this.newSchedule.time =
        `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;

      return;
    }

    // Diario
    if (
      day === '*' &&
      month === '*' &&
      weekDay === '*'
    ) {

      this.newSchedule.frequencyType = 'daily';

      this.newSchedule.time =
        `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;

      return;
    }

    // Personalizado
    this.newSchedule.frequencyType = 'cron';
  }

  getEstimatedNextRunLabel(): string {
    const cron = this.newSchedule.cron?.trim();

    if (!cron) return 'Pendiente de configurar';

    if (this.newSchedule.frequencyType === 'daily') {
      return `Se ejecutará diariamente a las ${this.newSchedule.time}`;
    }

    if (this.newSchedule.frequencyType === 'hourly') {
      return 'Se ejecutará cada hora';
    }

    if (this.newSchedule.frequencyType === 'weekly') {
      return `Se ejecutará semanalmente a las ${this.newSchedule.time}`;
    }

    if (this.newSchedule.frequencyType === 'interval') {
      return `Se ejecutará cada ${this.newSchedule.intervalMinutes} minutos`;
    }

    return `CRON personalizado: ${cron}`;
  }

  saveSchedule() {
    if (!this.newSchedule.scriptId) {
      this.svc.showToast('Debe seleccionar un script.', 'error');
      return;
    }

    this.buildCronFromControls();

    if (!this.newSchedule.cron.trim()) {
      this.svc.showToast('Debe ingresar una expresión CRON.', 'error');
      return;
    }

    for (const p of this.scheduleParameters) {
      if (p.is_required && !String(p.value || '').trim()) {
        this.svc.showToast(`Debe ingresar el parámetro: ${p.label || p.param_key}`, 'error');
        return;
      }
    }

    const parameters: Record<string, string> = {};

    for (const p of this.scheduleParameters) {
      parameters[p.param_key] = String(p.value ?? '');
    }

    const payload = {
      scriptId: Number(this.newSchedule.scriptId),
      frequency: this.newSchedule.frequencyType,
      cronExpression: this.newSchedule.cron,
      parameters
    };

    const editingId = this.svc.editingScheduleId();

    if (editingId) {
      this.svc.updateSchedule(editingId, payload).subscribe({
        next: () => {
          this.svc.showToast('Programación actualizada.');
          this.svc.loadSchedules();
          this.svc.loadScripts();
          this.resetScheduleForm();
        },
        error: err => {
          this.svc.showToast(
            `Error actualizando programación: ${err?.error?.message || err.message}`,
            'error'
          );
        }
      });

      return;
    }

    this.svc.addSchedule(payload as any).subscribe({
      next: () => {
        this.svc.showToast('Programación guardada.');
        this.svc.loadSchedules();
        this.svc.loadScripts();
        this.resetScheduleForm();
      },
      error: err => {
        this.svc.showToast(
          `Error guardando programación: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }



  getFilteredSchedules() {
    const name = this.scheduleNameFilter.trim().toLowerCase();

    return this.svc.schedules().filter(s => {
      const matchName = !name || s.scriptName.toLowerCase().includes(name);
      const matchStatus =
        this.scheduleStatusFilter === 'all' ||
        s.status === this.scheduleStatusFilter;

      return matchName && matchStatus;
    });
  }

  editSchedule(scheduleId: number) {
    this.svc.getSchedule(scheduleId).subscribe({
      next: data => {
        const schedule = data.schedule;

        this.svc.editingScheduleId.set(scheduleId);
        this.svc.editingScheduleData.set(data);

        this.newSchedule.scriptId = Number(schedule.script_id);
        this.newSchedule.cron = schedule.cron_expression || '';

        this.parseCronToControls(schedule.cron_expression || '');

        const paramsMap: Record<string, string> = {};

        for (const p of data.parameters || []) {
          paramsMap[p.param_key] = p.param_value;
        }

        this.svc.getScriptParameters(Number(schedule.script_id)).subscribe({
          next: params => {
            this.scheduleParameters = params
              .filter(p => p.control_type !== 'global')
              .map(p => ({
                ...p,
                value: paramsMap[p.param_key] ?? p.param_value ?? this.getDefaultValue(p)
              }));
          },
          error: err => {
            this.scheduleParameters = [];
            this.svc.showToast(
              `Error cargando parámetros: ${err?.error?.message || err.message}`,
              'error'
            );
          }
        });
      },
      error: err => {
        this.svc.showToast(
          `Error cargando programación: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  cancelEdit() {
    this.resetScheduleForm();
  }

  toggleSchedule(schedule: Schedule) {
    const ok = confirm(`¿Desea eliminar la programación de ${schedule.scriptName}?`);

    if (!ok) return;

    this.svc.deleteSchedule(schedule.id);

    if (this.svc.editingScheduleId() === schedule.id) {
      this.resetScheduleForm();
    }
  }

}