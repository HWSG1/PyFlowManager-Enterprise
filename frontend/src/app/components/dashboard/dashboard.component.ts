import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { ThemeService } from '../../services/theme.service';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-6">

      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold tracking-tight text-white">Dashboard Principal</h1>
          <p class="text-sm text-slate-400">Resumen operacional de PyFlow Manager.</p>
        </div>

        <div class="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs">
          <span class="text-slate-400">Última actualización:</span>
          <span class="text-blue-400 font-semibold">{{ lastUpdate }}</span>

          <button (click)="refresh()" class="text-slate-400 hover:text-white ml-2">
            ↻
          </button>
        </div>
      </div>

      <!-- KPI Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-4">

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">Scripts Activos</p>
          <h3 class="text-2xl font-bold text-slate-100">
            {{ dashboard?.activeScripts || 0 }} / {{ dashboard?.totalScripts || 0 }}
          </h3>
          <p class="text-[10px] text-slate-500 mt-2">Scripts disponibles</p>
        </div>

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">Éxitos últimas 24h</p>
          <h3 class="text-2xl font-bold text-emerald-400">
            {{ dashboard?.successToday || 0 }}
          </h3>
          <p class="text-[10px] text-slate-500 mt-2">
            Ejecuciones completadas
          </p>
        </div>

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">Errores últimas 24h</p>
          <h3 class="text-2xl font-bold text-rose-400">
            {{ dashboard?.errorsToday || 0 }}
          </h3>
          <p class="text-[10px] text-rose-400 mt-2">
            Requieren revisión
          </p>
        </div>

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">En Ejecución</p>
          <h3 class="text-2xl font-bold text-blue-400">
            {{ dashboard?.runningCount || 0 }}
          </h3>
          <p class="text-[10px] text-slate-500 mt-2">
            Procesos activos
          </p>
        </div>

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">En Cola</p>
          <h3 class="text-2xl font-bold text-amber-400">
            {{ dashboard?.queuedCount || 0 }}
          </h3>
          <p class="text-[10px] text-slate-500 mt-2">
            Pendientes de ejecución
          </p>
        </div>

        <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl">
          <p class="text-xs font-bold text-slate-400 uppercase mb-1">Duración prom. 24h</p>
          <h3 class="text-2xl font-bold text-cyan-400">
            {{ formatDuration(dashboard?.avgDurationSeconds || 0) }}
          </h3>
          <p class="text-[10px] text-slate-500 mt-2">
            Ejecuciones de hoy
          </p>
        </div>

      </div>

      <!-- Chart + Scheduler -->
      <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">

        <!-- Histórico -->
        <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl xl:col-span-3 h-fit">
          <div class="flex flex-col gap-3 mb-4 lg:flex-row lg:items-end lg:justify-between">
            <h4 class="font-semibold text-white">Histórico de Ejecuciones</h4>
            <div class="flex flex-wrap items-end gap-2">
              <label class="text-[10px] font-semibold text-slate-400 uppercase">
                Periodo
                <select
                  [(ngModel)]="chartRangePreset"
                  (ngModelChange)="onChartPresetChange()"
                  [disabled]="chartLoading"
                  class="mt-1 block min-w-[180px] bg-slate-900 border border-slate-800 rounded-md px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500 disabled:opacity-50">
                  <option value="today">Hoy</option>
                  <option value="yesterday">Ayer</option>
                  <option value="last7">Últimos 7 días</option>
                  <option value="currentMonth">Mes actual</option>
                  <option value="previousMonth">Mes anterior</option>
                  <option value="last3Months">Últimos 3 meses</option>
                  <option value="custom">Rango personalizado</option>
                </select>
              </label>

              @if (chartRangePreset === 'custom') {
                <label class="text-[10px] font-semibold text-slate-400 uppercase">
                  Desde
                  <input
                    type="date"
                    [(ngModel)]="chartDateFrom"
                    (ngModelChange)="onCustomRangeChange()"
                    [max]="chartDateTo"
                    class="mt-1 block bg-slate-900 border border-slate-800 rounded-md px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                </label>
                <label class="text-[10px] font-semibold text-slate-400 uppercase">
                  Hasta
                  <input
                    type="date"
                    [(ngModel)]="chartDateTo"
                    (ngModelChange)="onCustomRangeChange()"
                    [min]="chartDateFrom"
                    [max]="todayIso"
                    class="mt-1 block bg-slate-900 border border-slate-800 rounded-md px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500">
                </label>
              }
            </div>
          </div>

          <div class="h-80 relative">
            <canvas #dashChart></canvas>
          </div>
          <!-- Recent Executions Table -->
          <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h4 class="font-semibold text-white">Últimas Ejecuciones</h4>

              <button
                (click)="svc.switchTab('logs')"
                class="text-blue-500 hover:text-blue-400 text-xs font-semibold">
                Ver todos los logs ›
              </button>
            </div>

            <div class="overflow-x-auto">
              <table class="w-full text-left text-sm text-slate-300">
                <thead class="bg-slate-900/60 text-xs font-semibold uppercase text-slate-400 border-b border-slate-800">
                  <tr>
                    <th class="px-6 py-3.5">Script</th>
                    <th class="px-6 py-3.5">Estado</th>
                    <th class="px-6 py-3.5">Inicio</th>
                    <th class="px-6 py-3.5">Fin</th>
                    <th class="px-6 py-3.5">Duración</th>
                    <th class="px-6 py-3.5">Usuario</th>
                    <th class="px-6 py-3.5 text-right">Acción</th>
                  </tr>
                </thead>

                <tbody class="divide-y divide-slate-800/60">
                  @for (ex of dashboard?.lastExecutions || []; track ex.id) {
                    <tr class="hover:bg-slate-900/40 text-xs text-slate-300">
                      <td class="px-6 py-3.5 font-bold text-white">
                        {{ ex.script }}
                      </td>

                      <td class="px-6 py-3.5">
                        <span [class]="statusBadge(ex.status)">
                          {{ normalizeStatus(ex.status) }}
                        </span>
                      </td>

                      <td class="px-6 py-3.5 text-slate-500">
                        {{ formatDate(ex.startTime) }}
                      </td>

                      <td class="px-6 py-3.5 text-slate-500">
                        {{ formatDate(ex.endTime) }}
                      </td>

                      <td class="px-6 py-3.5 font-semibold">
                        {{ formatDuration(ex.durationSeconds || 0) }}
                      </td>

                      <td class="px-6 py-3.5">
                        {{ ex.user || 'Sistema' }}
                      </td>

                      <td class="px-6 py-3.5 text-right">
                        <button
                          (click)="svc.switchTab('logs')"
                          class="text-blue-500 hover:text-blue-400 font-semibold">
                          Ver log
                        </button>
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="7" class="px-6 py-8 text-center text-slate-500">
                        Aún no hay ejecuciones registradas.
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Scheduler / Salud -->
        <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
          <h4 class="font-semibold text-white mb-4">
            Estado del Scheduler
          </h4>

          <!-- Estado principal -->
          <div class="flex flex-col gap-3 text-sm">
            <div class="bg-slate-900 p-3 rounded border border-slate-800">
              <p class="text-slate-500 text-xs">Scheduler</p>
              <p
                class="font-bold"
                [class.text-emerald-400]="dashboard?.schedulerStatus === 'Activo'"
                [class.text-rose-400]="dashboard?.schedulerStatus !== 'Activo'">
                {{ dashboard?.schedulerStatus || 'Activo' }}
              </p>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="bg-slate-900 p-3 rounded border border-slate-800">
                <p class="text-slate-500 text-xs">Ejecutando</p>
                <p class="text-blue-400 font-bold">
                  {{ dashboard?.runningCount || 0 }}
                </p>
              </div>

              <div class="bg-slate-900 p-3 rounded border border-slate-800">
                <p class="text-slate-500 text-xs">En Cola</p>
                <p class="text-amber-400 font-bold">
                  {{ dashboard?.queuedCount || 0 }}
                </p>
              </div>

              <div class="bg-slate-900 p-3 rounded border border-slate-800">
                <p class="text-slate-500 text-xs">Máximo</p>
                <p class="text-white font-bold">
                  {{ dashboard?.maxConcurrentExecutions || 3 }}
                </p>
              </div>
            </div>
          </div>

          <!-- Próximas ejecuciones -->
          <div class="mt-5 border-t border-slate-800 pt-4">
            <div class="flex items-center justify-between mb-3">
              <h5 class="text-sm font-semibold text-white">
                Próximas ejecuciones
              </h5>

              <span class="text-[10px] text-slate-500">
                Top 5
              </span>
            </div>

            <div class="flex flex-col gap-2">
              @for (s of dashboard?.nextSchedules || []; track s.id) {
                <div class="bg-slate-900/70 border border-slate-800 rounded-lg px-3 py-2">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-xs text-slate-200 font-semibold truncate">
                      {{ s.script }}
                    </span>

                    <span class="text-[11px] text-blue-400 whitespace-nowrap">
                      {{ formatDate(s.next_run_at) }}
                    </span>
                  </div>

                  <div class="flex items-center justify-between mt-1">
                    <span class="text-[10px] text-slate-500">
                      {{ s.frequency_label || 'programada' }}
                    </span>

                    <span
                      class="text-[10px]"
                      [class.text-emerald-400]="s.last_status === 'Exitoso'"
                      [class.text-rose-400]="s.last_status === 'Error'"
                      [class.text-slate-500]="!s.last_status">
                      {{ s.last_status || 'Sin ejecución' }}
                    </span>
                  </div>
                </div>
              } @empty {
                <div class="bg-slate-900/70 border border-slate-800 rounded-lg px-3 py-4 text-center">
                  <p class="text-xs text-slate-500">
                    No hay programaciones activas.
                  </p>
                </div>
              }
            </div>
          </div>

          <!-- Salud del sistema -->
          <div class="mt-5 border-t border-slate-800 pt-4">
            <h5 class="text-sm font-semibold text-white mb-3">
              Salud del Sistema
            </h5>

            <div class="flex flex-col gap-2 text-xs">

              <div class="flex items-center justify-between">
                <span class="text-slate-400">Backend</span>
                <span
                  class="font-semibold"
                  [class.text-emerald-400]="dashboard?.systemHealth?.backend"
                  [class.text-rose-400]="!dashboard?.systemHealth?.backend">
                  {{ dashboard?.systemHealth?.backend ? 'Activo' : 'Inactivo' }}
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">Scheduler</span>
                <span
                  class="font-semibold"
                  [class.text-emerald-400]="dashboard?.systemHealth?.scheduler"
                  [class.text-rose-400]="!dashboard?.systemHealth?.scheduler">
                  {{ dashboard?.systemHealth?.scheduler ? 'Activo' : 'Inactivo' }}
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">SQL Server</span>
                <span
                  class="font-semibold"
                  [class.text-emerald-400]="dashboard?.systemHealth?.database"
                  [class.text-rose-400]="!dashboard?.systemHealth?.database">
                  {{ dashboard?.systemHealth?.database ? 'Activo' : 'Inactivo' }}
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">RAM</span>
                <span class="text-blue-400 font-semibold">
                  {{ formatPercent(dashboard?.systemHealth?.memoryUsage) }}
                  <span class="text-slate-500">
                    ({{ formatGb(dashboard?.systemHealth?.memoryUsedGb) }} /
                    {{ formatGb(dashboard?.systemHealth?.memoryTotalGb) }})
                  </span>
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">CPU</span>
                <span class="text-cyan-400 font-semibold">
                  {{ formatPercent(dashboard?.systemHealth?.cpuUsage) }}
                  <span class="text-slate-500">
                    ({{ dashboard?.systemHealth?.cpuCount || 0 }} cores)
                  </span>
                </span>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class DashboardComponent implements AfterViewInit, OnDestroy {
  @ViewChild('dashChart') chartRef!: ElementRef<HTMLCanvasElement>;

  lastUpdate = 'Justo ahora';
  todayIso = this.localIsoDate();
  chartRangePreset = 'last7';
  chartDateFrom = this.addDays(this.todayIso, -6);
  chartDateTo = this.todayIso;
  chartLoading = false;
  chart: Chart | null = null;
  refreshTimer: any;

  constructor(public svc: PyflowService, private themes: ThemeService) {
    effect(() => {
      this.themes.activeTheme();
      setTimeout(() => {
        if (this.chartRef?.nativeElement) {
          this.updateChart(this.dashboard?.executionsHistory || this.dashboard?.executionsLast7Days || []);
        }
      });
    });
  }

  get dashboard() {
    return this.svc.dashboard();
  }

  async ngAfterViewInit() {
    await this.refresh();
    this.refreshTimer = setInterval(() => this.refresh(), 30000);
  }

  ngOnDestroy() {
    this.chart?.destroy();

    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
    }
  }

  async refresh() {
    try {
      const data = await this.svc.loadDashboard(this.chartDateFrom, this.chartDateTo);

      this.lastUpdate = new Date().toLocaleTimeString('es-HN', {
        hour: '2-digit',
        minute: '2-digit'
      });

      this.updateChart(data?.executionsHistory || data?.executionsLast7Days || []);
    } catch (error) {
      console.error('Error cargando dashboard:', error);
      this.lastUpdate = 'Error al actualizar';

      if (!this.chart) {
        this.updateChart([]);
      }
    }
  }

  async applyChartRange() {
    if (!this.chartDateFrom || !this.chartDateTo || this.chartDateFrom > this.chartDateTo) {
      this.svc.showToast('Selecciona un rango de fechas válido.', 'error');
      return;
    }

    this.chartLoading = true;
    try {
      await this.refresh();
    } finally {
      this.chartLoading = false;
    }
  }

  async onChartPresetChange() {
    if (this.chartRangePreset === 'custom') return;

    this.todayIso = this.localIsoDate();
    const currentMonthStart = `${this.todayIso.slice(0, 7)}-01`;

    switch (this.chartRangePreset) {
      case 'today':
        this.chartDateFrom = this.todayIso;
        this.chartDateTo = this.todayIso;
        break;
      case 'yesterday':
        this.chartDateFrom = this.addDays(this.todayIso, -1);
        this.chartDateTo = this.chartDateFrom;
        break;
      case 'currentMonth':
        this.chartDateFrom = currentMonthStart;
        this.chartDateTo = this.todayIso;
        break;
      case 'previousMonth':
        this.chartDateTo = this.addDays(currentMonthStart, -1);
        this.chartDateFrom = `${this.chartDateTo.slice(0, 7)}-01`;
        break;
      case 'last3Months':
        this.chartDateFrom = this.addMonths(currentMonthStart, -2);
        this.chartDateTo = this.todayIso;
        break;
      default:
        this.chartDateFrom = this.addDays(this.todayIso, -6);
        this.chartDateTo = this.todayIso;
        break;
    }

    await this.applyChartRange();
  }

  onCustomRangeChange() {
    if (
      this.chartRangePreset === 'custom' &&
      this.chartDateFrom &&
      this.chartDateTo &&
      this.chartDateFrom <= this.chartDateTo
    ) {
      void this.applyChartRange();
    }
  }

  private localIsoDate(): string {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Tegucigalpa',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(new Date());
    return parts;
  }

  private addDays(isoDate: string, days: number): string {
    const date = new Date(`${isoDate}T00:00:00.000Z`);
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }

  private addMonths(isoDate: string, months: number): string {
    const date = new Date(`${isoDate}T00:00:00.000Z`);
    date.setUTCMonth(date.getUTCMonth() + months);
    return date.toISOString().slice(0, 10);
  }

  updateChart(rows: any[]) {
    const labels = rows.map(r => {
      const isoDate = String(r.executionDate || '').slice(0, 10);
      return new Date(`${isoDate}T12:00:00`).toLocaleDateString('es-HN', {
        weekday: 'short',
        day: '2-digit',
        month: '2-digit'
      });
    });

    const success = rows.map(r => Number(r.successCount || 0));
    const errors = rows.map(r => Number(r.errorCount || 0));
    const themeStyles = getComputedStyle(document.documentElement);
    const accent = themeStyles.getPropertyValue('--accent').trim() || '#2563eb';
    const muted = themeStyles.getPropertyValue('--muted').trim() || '#94a3b8';
    const border = themeStyles.getPropertyValue('--border').trim() || '#1e293b';

    this.chart?.destroy();

    const ctx = this.chartRef?.nativeElement?.getContext('2d');
    if (!ctx) return;

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Exitosas',
            data: success,
            borderColor: accent,
            backgroundColor: this.withAlpha(accent, 0.16),
            pointBackgroundColor: accent,
            tension: 0.35,
            fill: true,
            pointRadius: 4
          },
          {
            label: 'Errores',
            data: errors,
            borderColor: 'rgba(244,63,94,0.9)',
            backgroundColor: 'rgba(244,63,94,0.12)',
            tension: 0.35,
            fill: true,
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: muted,
              font: { size: 11 }
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: muted, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: border }
          },
          y: {
            stacked: false,
            ticks: { color: muted },
            grid: { color: border }
          }
        }
      }
    });
  }

  private withAlpha(color: string, alpha: number): string {
    const hex = color.replace('#', '').trim();
    const normalized = hex.length === 3
      ? hex.split('').map(char => char + char).join('')
      : hex;

    if (!/^[0-9a-f]{6}$/i.test(normalized)) {
      return color;
    }

    const red = parseInt(normalized.slice(0, 2), 16);
    const green = parseInt(normalized.slice(2, 4), 16);
    const blue = parseInt(normalized.slice(4, 6), 16);
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
  }

  normalizeStatus(status: string): string {
    const map: Record<string, string> = {
      COMPLETED: 'Exitoso',
      FAILED: 'Error',
      RUNNING: 'Ejecutando',
      CANCELLED: 'Cancelado',
      CANCELED: 'Cancelado',
      PENDING: 'Pendiente',
      QUEUED: 'En Cola'
    };

    return map[status] || status || 'Desconocido';
  }

  statusBadge(status: string): string {
    const normalized = this.normalizeStatus(status);

    const map: Record<string, string> = {
      Exitoso: 'px-2 py-0.5 rounded-full text-[10px] bg-emerald-950 border border-emerald-900 text-emerald-400 font-medium',
      Error: 'px-2 py-0.5 rounded-full text-[10px] bg-rose-950 border border-rose-900 text-rose-400 font-medium',
      Ejecutando: 'px-2 py-0.5 rounded-full text-[10px] bg-blue-950 border border-blue-900 text-blue-400 font-medium',
      Cancelado: 'px-2 py-0.5 rounded-full text-[10px] bg-slate-900 border border-slate-800 text-slate-400 font-medium',
      Pendiente: 'px-2 py-0.5 rounded-full text-[10px] bg-amber-950 border border-amber-900 text-amber-400 font-medium',
      'En Cola': 'px-2 py-0.5 rounded-full text-[10px] bg-amber-950 border border-amber-900 text-amber-400 font-medium'
    };

    return map[normalized] || map['Cancelado'];
  }

  formatDate(value: any): string {
    if (!value) return '-';

    try {
      const text = String(value).trim();
      const sqlDateWithoutTimezone = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}(?:\.\d+)?)$/.exec(text);
      const normalized = sqlDateWithoutTimezone
        ? `${sqlDateWithoutTimezone[1]}T${sqlDateWithoutTimezone[2]}Z`
        : text;
      const date = value instanceof Date ? value : new Date(normalized);

      if (Number.isNaN(date.getTime())) return text;

      return date.toLocaleString('es-HN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Tegucigalpa'
      });
    } catch {
      return String(value);
    }
  }

  formatDuration(seconds: number): string {
    if (!seconds || seconds <= 0) return '0s';

    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  formatPercent(value: any): string {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)}%` : '0.00%';
  }

  formatGb(value: any): string {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)}GB` : '--';
  }
}
