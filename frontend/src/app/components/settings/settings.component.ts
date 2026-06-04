import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-settings', standalone: true, imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-6">
      <div>
        <h1 class="text-2xl font-bold text-app">Configuración del Sistema</h1>
        <p class="text-sm text-muted">Variables globales, parámetros críticos, auto-refresh y temas.</p>
      </div>

      <div class="card p-5 rounded-xl">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold">Parámetros del sistema por ambiente</h3>
          <span class="text-xs text-muted">Requiere PIN administrativo</span>
        </div>

        <div class="flex gap-2 mb-4">
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

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
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

        <div class="flex justify-end items-center gap-2 mt-4">
          <input
            class="input !w-52"
            [(ngModel)]="adminPin"
            type="password"
            placeholder="PIN administrativo">

          <button class="btn-primary" (click)="saveSystem()">
            Guardar configuración
          </button>
        </div>
      </div>

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

      <div class="card p-5 rounded-xl">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold">Variables Globales Compartidas</h3>
          <button (click)="addVar()" class="text-accent text-xs font-semibold">+ Agregar Variable</button>
        </div>

        <p class="text-xs text-muted mb-4">
          Se inyectan automáticamente en scripts cuando son requeridas como parámetro global.
        </p>

        <div class="flex flex-col gap-3">
          @for (v of globalVars; track $index) {
            <div class="grid grid-cols-12 gap-2 items-center">
              <input [(ngModel)]="v.key" placeholder="VARIABLE" class="col-span-3 input">

              <input
                [type]="v.isSecret ? 'password' : 'text'"
                [(ngModel)]="v.value"
                placeholder="VALOR"
                class="col-span-3 input">

              <input [(ngModel)]="v.description" placeholder="Descripción" class="col-span-3 input">

              <label class="col-span-2 flex items-center gap-2 text-xs text-muted">
                <input type="checkbox" [(ngModel)]="v.isSecret">
                Secreta
              </label>

              <button
                (click)="removeVar(v, $index)"
                class="col-span-1 text-rose-500 text-xs font-semibold text-right">
                Eliminar
              </button>
            </div>
          }

          @if (!globalVars.length) {
            <div class="text-xs text-muted border border-app rounded-lg p-4">
              No hay variables globales configuradas.
            </div>
          }
        </div>
      </div>

      <div class="flex justify-end">
        <button (click)="save()" class="btn-primary">💾 Guardar Variables</button>
      </div>
    </div>
  `
})
export class SettingsComponent implements OnInit {
  globalVars: any[] = []; systemSettings: any[] = []; adminPin = '';
  constructor(public svc: PyflowService, public themes: ThemeService) {}
  ngOnInit() { this.loadVariables(); }
  loadVariables() { this.svc.loadSettings(); setTimeout(() => { this.globalVars = this.svc.envParams().map((x: any) => ({ id: x.id, key: x.key, value: x.value, isSecret: x.isSecret, description: x.description || '' })); this.systemSettings = this.svc.systemSettings().map((x:any)=>({ ...x })); }, 300); }
  addVar() { this.globalVars.push({ id: null, key: '', value: '', isSecret: false, description: '' }); }
  removeVar(v: any, index: number) { if (!v.id) { this.globalVars.splice(index, 1); return; } if (!confirm(`¿Deseas eliminar la variable ${v.key}?`)) return; this.svc.deleteGlobalVariable(v.id).subscribe({ next: () => { this.svc.showToast('Variable eliminada.', 'info'); this.globalVars.splice(index, 1); this.svc.loadSettings(); }, error: err => this.svc.showToast(`Error eliminando variable: ${err?.error?.message || err.message}`, 'error') }); }
  saveSystem() { this.svc.saveSystemSettings(this.systemSettings, this.adminPin).subscribe({ next: () => { this.svc.showToast('Configuración guardada.'); this.adminPin=''; this.svc.loadSettings(); }, error: err => this.svc.showToast(`Error guardando configuración: ${err?.error?.message || err.message}`, 'error') }); }
  save() { const variables = this.globalVars.filter(v => String(v.key || '').trim()).map(v => ({ id: v.id, var_key: String(v.key || '').trim(), var_value: String(v.value ?? ''), is_secret: !!v.isSecret, description: v.description || null })); this.svc.saveGlobalVariables(variables).subscribe({ next: () => { this.svc.showToast('Variables globales guardadas correctamente.'); this.svc.loadSettings(); }, error: err => this.svc.showToast(`Error guardando variables: ${err?.error?.message || err.message}`, 'error') }); }
  selectedEnvironment = 3;

  environments = [
    { id: 1, name: 'DEV' },
    { id: 2, name: 'QA' },
    { id: 3, name: 'PROD' }
  ];

  get filteredSystemSettings() {
    return this.systemSettings.filter(s => Number(s.environment_id) === this.selectedEnvironment);
  }
}
