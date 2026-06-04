import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PyflowService } from '../../services/pyflow.service';
import { AuthService } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <header class="bg-panel border-b border-app h-16 flex items-center justify-between px-6 z-30 shrink-0">
      <!-- Logo -->
      <div class="flex items-center gap-3">
        <div class="bg-blue-600 p-2 rounded-lg text-white flex items-center justify-center shadow-lg shadow-blue-900/30">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
          </svg>
        </div>
        <div>
          <span class="font-bold text-lg tracking-wider text-white">PyFlow</span>
          <span class="text-blue-500 font-medium text-sm ml-1">Manager</span>
          <span class="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full ml-2 border border-slate-700">v2.4-Enterprise</span>
        </div>
      </div>

      <!-- Right side -->
      <div class="flex items-center gap-6">
        <!-- Search -->
        <div class="relative w-80 max-md:hidden">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2"
               viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input type="text" placeholder="Buscar scripts, ejecuciones o logs..."
                 class="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-4 py-1.5 text-sm
                        focus:outline-none focus:border-blue-500 text-slate-200 transition-colors">
        </div>

        <select [ngModel]="themes.activeTheme()" (ngModelChange)="themes.setTheme($event)" class="input !py-1.5 !w-40 text-xs">
          @for (t of themes.themes(); track t.theme_key) { <option [value]="t.theme_key">{{t.theme_name}}</option> }
        </select>

        <!-- New Script btn -->
        <button (click)="svc.switchTab('scripts'); svc.showImportModal.set(true)"
                class="bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-xs font-semibold
                       px-4 py-2 rounded-lg flex items-center gap-2 shadow-lg shadow-blue-950 transition-all">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>
          </svg>
          Nuevo Script
        </button>

        <div class="h-6 w-[1px] bg-slate-800"></div>

        <!-- User avatar -->
        <div class="flex items-center gap-3">
          <div class="relative">
            <div class="w-9 h-9 rounded-full bg-blue-500 text-white font-bold flex items-center justify-center text-sm border-2 border-slate-800 shadow-md">
              AD
            </div>
            <span class="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 rounded-full border-2 border-slate-950"></span>
          </div>
          <div class="text-left max-sm:hidden">
            <p class="text-xs font-semibold text-slate-200">{{ auth.user()?.name || auth.user()?.username }}</p>
            <p class="text-[10px] text-slate-400">{{ auth.user()?.roles || 'Usuario' }}</p>
          </div>
          <button (click)="auth.logout()" class="text-xs text-slate-400 hover:text-white">Salir</button>
        </div>
      </div>
    </header>
  `
})
export class HeaderComponent {
  constructor(public svc: PyflowService, public auth: AuthService, public themes: ThemeService) {}
}
