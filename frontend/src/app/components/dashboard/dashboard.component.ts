import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PyflowService } from '../../services/pyflow.service';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
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
          <div class="flex items-center justify-between mb-4">
            <h4 class="font-semibold text-white">Histórico de Ejecuciones</h4>
            <span class="text-xs bg-slate-900 border border-slate-800 px-2 py-1 rounded-md text-slate-400">
              Últimos 7 días
            </span>
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
                <span class="text-emerald-400 font-semibold">Activo</span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">Scheduler</span>
                <span class="text-emerald-400 font-semibold">Activo</span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">SQL Server</span>
                <span class="text-emerald-400 font-semibold">Activo</span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">RAM</span>
                <span class="text-blue-400 font-semibold">
                  {{ dashboard?.systemHealth?.memoryUsage || 0 }}%
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-400">CPU Cores</span>
                <span class="text-cyan-400 font-semibold">
                  {{ dashboard?.systemHealth?.cpuCount || 0 }}
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
  chart: Chart | null = null;
  refreshTimer: any;

  constructor(public svc: PyflowService) {}

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
      const data = await this.svc.loadDashboard();

      this.lastUpdate = new Date().toLocaleTimeString('es-HN', {
        hour: '2-digit',
        minute: '2-digit'
      });

      this.updateChart(data?.executionsLast7Days || []);
    } catch (error) {
      console.error('Error cargando dashboard:', error);
      this.lastUpdate = 'Error al actualizar';

      if (!this.chart) {
        this.updateChart([]);
      }
    }
  }

  updateChart(rows: any[]) {
    const labels = rows.map(r =>
      new Date(r.executionDate).toLocaleDateString('es-HN', {
        weekday: 'short'
      })
    );

    const success = rows.map(r => Number(r.successCount || 0));
    const errors = rows.map(r => Number(r.errorCount || 0));

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
            borderColor: 'rgba(16,185,129,0.9)',
            backgroundColor: 'rgba(16,185,129,0.15)',
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
              color: '#94a3b8',
              font: { size: 11 }
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: '#64748b' },
            grid: { color: '#1e293b' }
          },
          y: {
            stacked: false,
            ticks: { color: '#64748b' },
            grid: { color: '#1e293b' }
          }
        }
      }
    });
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
      const text = String(value).replace('Z', '');

      return new Date(text).toLocaleString('es-HN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
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
}