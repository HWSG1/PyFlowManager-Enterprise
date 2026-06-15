import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { ThemeService } from '../../services/theme.service';

type SettingsView = 'system' | 'variables' | 'themes';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-app">Configuración del Sistema</h1>
          <p class="text-sm text-muted">Variables globales, parámetros críticos, auto-refresh y temas.</p>
        </div>

        <div class="flex rounded-xl border border-app bg-slate-950/40 p-1">
          <button type="button" [class]="viewButtonClass('system')" (click)="activeView = 'system'">Sistema</button>
          <button type="button" [class]="viewButtonClass('variables')" (click)="activeView = 'variables'">Variables</button>
          <button type="button" [class]="viewButtonClass('themes')" (click)="activeView = 'themes'">Temas</button>
        </div>
      </div>

      @if (activeView === 'system') {
        <div class="card rounded-xl overflow-hidden">
          <div class="sticky top-0 z-10 bg-panel border-b border-app p-5">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h3 class="font-semibold">Parámetros del sistema por ambiente</h3>
                <p class="text-xs text-muted mt-1">Requiere PIN administrativo.</p>
              </div>

              <div class="flex items-center gap-2">
                <input class="input !w-52" [(ngModel)]="adminPin" type="password" placeholder="PIN administrativo">
                <button class="btn-primary" (click)="saveSystem()">Guardar configuración</button>
              </div>
            </div>

            <div class="flex gap-2 mt-4">
              @for (env of environments; track env.id) {
                <button
                  type="button"
                  class="px-3 py-2 rounded-lg border border-app text-sm"
                  [class.bg-accent]="selectedEnvironment === env.id"
                  [class.text-white]="selectedEnvironment === env.id"
                  (click)="selectedEnvironment = env.id">
                  {{ env.name }}
                </button>
              }
            </div>
          </div>

          <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-3">
            @for (s of filteredSystemSettings; track s.id) {
              <div class="border border-app rounded-lg p-3">
                <label class="text-xs text-muted">{{ s.setting_key }}</label>
                <input
                  class="input mt-1"
                  [(ngModel)]="s.setting_value"
                  [type]="s.setting_type === 'number' ? 'number' : (s.setting_type === 'secret' ? 'password' : 'text')">
                <p class="text-[11px] text-muted mt-1">{{ s.description }}</p>
              </div>
            }

            @if (!filteredSystemSettings.length) {
              <div class="text-xs text-muted border border-app rounded-lg p-4 md:col-span-2">
                No hay configuraciones para este ambiente.
              </div>
            }
          </div>
        </div>
      }

      @if (activeView === 'variables') {
        <div class="card rounded-xl overflow-hidden">
          <div class="sticky top-0 z-10 bg-panel border-b border-app p-5">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h3 class="font-semibold">Variables Globales Compartidas</h3>
                <p class="text-xs text-muted mt-1">Se inyectan automáticamente cuando un script las requiere.</p>
              </div>

              <div class="flex items-center gap-2">
                <input class="input !w-72" [(ngModel)]="variableFilter" placeholder="Filtrar variable...">
                <button (click)="addVar()" class="btn-secondary">+ Agregar</button>
                <button (click)="save()" class="btn-primary">Guardar variables</button>
              </div>
            </div>
          </div>

          <div class="p-5 flex flex-col gap-3">
            @for (v of filteredGlobalVars; track $index) {
              <div class="grid grid-cols-12 gap-2 items-start border border-app rounded-lg p-3 bg-slate-950/20">
                <div class="col-span-12 md:col-span-3">
                  <label class="text-[10px] text-muted uppercase">Variable</label>
                  <input [(ngModel)]="v.key" placeholder="VARIABLE" class="input mt-1">
                </div>

                <div class="col-span-12 md:col-span-3">
                  <label class="text-[10px] text-muted uppercase">Valor</label>
                  <input [type]="v.isSecret ? 'password' : 'text'" [(ngModel)]="v.value" placeholder="VALOR" class="input mt-1">
                </div>

                <div class="col-span-12 md:col-span-4">
                  <label class="text-[10px] text-muted uppercase">Descripción</label>
                  <input [(ngModel)]="v.description" placeholder="Descripción" class="input mt-1">
                </div>

                <label class="col-span-6 md:col-span-1 flex items-center gap-2 text-xs text-muted pt-6">
                  <input type="checkbox" [(ngModel)]="v.isSecret">
                  Secreta
                </label>

                <button
                  (click)="removeVar(v)"
                  class="col-span-6 md:col-span-1 text-rose-500 hover:text-rose-400 text-xs font-semibold text-right pt-6">
                  Eliminar
                </button>
              </div>
            }

            @if (!filteredGlobalVars.length) {
              <div class="text-xs text-muted border border-app rounded-lg p-4">
                No hay variables globales que coincidan con el filtro.
              </div>
            }
          </div>
        </div>
      }

      @if (activeView === 'themes') {
        <div class="card p-5 rounded-xl">
          <div class="flex items-center justify-between mb-3">
            <h3 class="font-semibold">Temas visuales disponibles</h3>
            <span class="text-xs text-muted">20 temas iniciales</span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
            @for (t of themes.themes(); track t.theme_key) {
              <button
                class="border border-app rounded-lg p-3 text-left hover:border-accent"
                (click)="themes.setTheme(t.theme_key)">
                <div class="w-full h-8 rounded-md bg-accent mb-2"></div>
                <p class="text-sm font-semibold">{{ t.theme_name }}</p>
                <p class="text-[11px] text-muted">{{ t.is_dark ? 'Dark' : 'Light' }}</p>
              </button>
            }
          </div>
        </div>
      }
    </div>
  `
})
export class SettingsComponent implements OnInit {
  activeView: SettingsView = 'variables';
  globalVars: any[] = [];
  systemSettings: any[] = [];
  adminPin = '';
  variableFilter = '';
  selectedEnvironment = 3;

  environments = [
    { id: 1, name: 'DEV' },
    { id: 2, name: 'QA' },
    { id: 3, name: 'PROD' }
  ];

  constructor(public svc: PyflowService, public themes: ThemeService) {}

  ngOnInit() {
    this.loadVariables();
  }

  loadVariables() {
    this.svc.loadSettings();
    setTimeout(() => {
      this.globalVars = this.svc.envParams().map((x: any) => ({
        id: x.id,
        key: x.key,
        value: x.value,
        isSecret: x.isSecret,
        description: x.description || ''
      }));
      this.systemSettings = this.svc.systemSettings().map((x: any) => ({ ...x }));
    }, 300);
  }

  addVar() {
    this.activeView = 'variables';
    this.variableFilter = '';
    this.globalVars.unshift({ id: null, key: '', value: '', isSecret: false, description: '' });
  }

  removeVar(v: any) {
    const index = this.globalVars.indexOf(v);
    if (index < 0) return;

    if (!v.id) {
      this.globalVars.splice(index, 1);
      return;
    }

    if (!confirm(`¿Deseas eliminar la variable ${v.key}?`)) return;

    this.svc.deleteGlobalVariable(v.id).subscribe({
      next: () => {
        this.svc.showToast('Variable eliminada.', 'info');
        this.globalVars.splice(index, 1);
        this.svc.loadSettings();
      },
      error: err => this.svc.showToast(`Error eliminando variable: ${err?.error?.message || err.message}`, 'error')
    });
  }

  saveSystem() {
    this.svc.saveSystemSettings(this.systemSettings, this.adminPin).subscribe({
      next: () => {
        this.svc.showToast('Configuración guardada.');
        this.adminPin = '';
        this.svc.loadSettings();
      },
      error: err => this.svc.showToast(`Error guardando configuración: ${err?.error?.message || err.message}`, 'error')
    });
  }

  save() {
    const variables = this.globalVars
      .filter(v => String(v.key || '').trim())
      .map(v => ({
        id: v.id,
        var_key: String(v.key || '').trim(),
        var_value: String(v.value ?? ''),
        is_secret: !!v.isSecret,
        description: v.description || null
      }));

    this.svc.saveGlobalVariables(variables).subscribe({
      next: () => {
        this.svc.showToast('Variables globales guardadas correctamente.');
        this.svc.loadSettings();
      },
      error: err => this.svc.showToast(`Error guardando variables: ${err?.error?.message || err.message}`, 'error')
    });
  }

  viewButtonClass(view: SettingsView): string {
    const base = 'px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors';
    return this.activeView === view
      ? `${base} bg-accent text-white`
      : `${base} text-muted hover:text-white`;
  }

  get filteredSystemSettings() {
    return this.systemSettings.filter(s => Number(s.environment_id) === this.selectedEnvironment);
  }

  get filteredGlobalVars() {
    const filter = this.variableFilter.trim().toLowerCase();
    if (!filter) return this.globalVars;

    return this.globalVars.filter(v =>
      String(v.key || '').toLowerCase().includes(filter) ||
      String(v.description || '').toLowerCase().includes(filter)
    );
  }
}
