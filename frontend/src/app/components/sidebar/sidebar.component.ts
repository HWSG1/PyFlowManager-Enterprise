import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { PyflowService } from '../../services/pyflow.service';
import { TabName } from '../../models/models';

interface NavItem {
  tab: TabName;
  label: string;
  icon: SafeHtml;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="w-64 h-full bg-panel border-r border-app flex flex-col justify-between shrink-0 max-md:w-16 transition-all duration-300">
      <div class="p-4 flex flex-col gap-1">
        <p class="text-[10px] font-bold tracking-widest text-slate-500 uppercase px-3 mb-2 max-md:hidden">
          NAVEGACIÓN
        </p>

        @for (item of navItems; track item.tab) {
          <button (click)="svc.switchTab(item.tab)"
                  [class]="btnClass(item.tab)">
            <span [innerHTML]="item.icon" class="w-5 h-5 shrink-0 flex items-center justify-center"></span>
            <span class="max-md:hidden text-left flex-1">{{ item.label }}</span>
          </button>
        }
      </div>

      <div class="p-4 border-t border-slate-800 bg-panel/40 text-xs text-slate-500 max-md:hidden">
        <div class="flex items-center gap-2 mb-1">
          <span
            class="w-2 h-2 rounded-full"
            [class.bg-emerald-500]="svc.dashboard()?.systemHealth?.backend"
            [class.animate-pulse]="svc.dashboard()?.systemHealth?.backend"
            [class.bg-rose-500]="!svc.dashboard()?.systemHealth?.backend"></span>
          <span class="text-slate-300 font-semibold">
            PyEngine {{ svc.dashboard()?.systemHealth?.backend ? 'Running' : 'Sin conexión' }}
          </span>
        </div>
        <p>Carga de CPU: {{ formatPercent(svc.dashboard()?.systemHealth?.cpuUsage) }}</p>
        <p>
          Memoria:
          {{ formatGb(svc.dashboard()?.systemHealth?.memoryUsedGb) }} /
          {{ formatGb(svc.dashboard()?.systemHealth?.memoryTotalGb) }}
          ({{ formatPercent(svc.dashboard()?.systemHealth?.memoryUsage) }})
        </p>
      </div>
    </aside>
  `
})
export class SidebarComponent {
  constructor(
    public svc: PyflowService,
    private sanitizer: DomSanitizer
  ) {}

  navItems: NavItem[] = [
    {
      tab: 'dashboard',
      label: 'Dashboard',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>`)
    },
    {
      tab: 'scripts',
      label: 'Scripts',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="10" y1="12" x2="14" y2="12"/></svg>`)
    },
    {
      tab: 'schedules',
      label: 'Programaciones',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`)
    },
    {
      tab: 'logs',
      label: 'Logs e Histórico',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="12,8 12,12 16,14"/><path d="M3.05 11a9 9 0 1 1 .5 4m-.5 5v-5h5"/></svg>`)
    },
    {
      tab: 'users',
      label: 'Usuarios y Roles',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`)
    },
    {
      tab: 'settings',
      label: 'Configuración',
      icon: this.icon(`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`)
    }
  ];

  private icon(svg: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(svg);
  }

  btnClass(tab: TabName): string {
    const base = 'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all';
    const active = 'text-blue-400 bg-slate-900 border-l-4 border-blue-500';
    const inactive = 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/50 border-l-4 border-transparent';
    return `${base} ${this.svc.activeTab() === tab ? active : inactive}`;
  }

  formatPercent(value: any): string {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)}%` : '--';
  }

  formatGb(value: any): string {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)}GB` : '--';
  }
}
