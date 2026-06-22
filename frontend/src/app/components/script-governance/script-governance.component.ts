import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';

type GovernanceView = 'policy' | 'versions' | 'access';

@Component({
  selector: 'app-script-governance',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="bg-slate-950 border border-slate-800 p-5 rounded-lg shrink-0">
      <div class="flex items-center justify-between gap-2 mb-4">
        <h4 class="font-semibold text-white text-sm">Gobierno y automatización</h4>
        <button type="button" (click)="load()" title="Actualizar" class="text-accent text-sm">↻</button>
      </div>

      <div class="grid grid-cols-3 gap-1 bg-slate-900 border border-slate-800 rounded-md p-1 mb-4">
        <button type="button" (click)="view='policy'" [class]="tabClass('policy')">Política</button>
        <button type="button" (click)="view='versions'" [class]="tabClass('versions')">Versiones</button>
        <button type="button" (click)="view='access'" [class]="tabClass('access')">Accesos</button>
      </div>

      @if (loading) {
        <p class="text-xs text-muted py-4 text-center">Cargando configuración...</p>
      } @else if (view === 'policy') {
        <div class="grid grid-cols-2 gap-3 text-xs">
          <label class="text-muted">Reintentos
            <input class="input mt-1" type="number" min="0" max="10" [(ngModel)]="policy.max_retries">
          </label>
          <label class="text-muted">Espera inicial (s)
            <input class="input mt-1" type="number" min="1" [(ngModel)]="policy.retry_delay_seconds">
          </label>
          <label class="text-muted col-span-2">Factor de incremento
            <input class="input mt-1" type="number" min="1" max="10" step="0.25" [(ngModel)]="policy.retry_backoff_factor">
          </label>
        </div>
        <div class="flex gap-4 mt-3 text-xs text-app">
          <label class="flex items-center gap-2"><input type="checkbox" [(ngModel)]="policy.alert_on_success"> Avisar éxito</label>
          <label class="flex items-center gap-2"><input type="checkbox" [(ngModel)]="policy.alert_on_failure"> Avisar fallo final</label>
        </div>
        <label class="text-xs text-muted block mt-3">Destinatarios
          <textarea class="input mt-1" rows="2" [(ngModel)]="policy.alert_recipients" placeholder="correo1@empresa.com; correo2@empresa.com"></textarea>
        </label>
        <button type="button" class="btn-primary w-full mt-3" (click)="savePolicy()">Guardar política</button>
      } @else if (view === 'versions') {
        <div class="flex flex-col gap-2 mb-4">
          <input class="input text-xs" type="file" accept=".py" (change)="selectVersionFile($event)">
          <input class="input text-xs" [(ngModel)]="newVersion" placeholder="Versión, por ejemplo 1.1.0">
          <input class="input text-xs" [(ngModel)]="versionNotes" placeholder="Descripción del cambio">
          <button type="button" class="btn-primary" [disabled]="!versionFile || !newVersion" (click)="uploadVersion()">Publicar versión</button>
        </div>
        <div class="flex flex-col gap-2 max-h-52 overflow-y-auto custom-scrollbar">
          @for (version of versions; track version.id) {
            <div class="border border-app rounded-md p-2 text-xs">
              <div class="flex justify-between gap-2"><strong>{{version.version}}</strong><span class="text-muted">{{version.created_at | date:'dd/MM/yyyy HH:mm'}}</span></div>
              <p class="text-muted truncate">{{version.change_notes || 'Sin notas'}}</p>
              @if (version.is_current) { <span class="text-emerald-400 font-semibold">Actual</span> }
              @else { <button type="button" class="text-accent font-semibold" (click)="restore(version)">Restaurar</button> }
            </div>
          } @empty { <p class="text-xs text-muted">Aún no hay versiones registradas.</p> }
        </div>
      } @else {
        <p class="text-[11px] text-muted mb-3">Si no asignas usuarios, aplican los permisos generales del rol.</p>
        <div class="flex flex-col gap-2 max-h-64 overflow-y-auto custom-scrollbar">
          @for (entry of accessRows; track entry.user_id) {
            <div class="border border-app rounded-md p-2 text-xs">
              <label class="flex items-center gap-2 font-semibold"><input type="checkbox" [(ngModel)]="entry.enabled"> {{entry.display_name || entry.username}}</label>
              @if (entry.enabled) {
                <div class="grid grid-cols-4 gap-1 mt-2 text-[10px] text-muted">
                  <label><input type="checkbox" [(ngModel)]="entry.can_view"> Ver</label>
                  <label><input type="checkbox" [(ngModel)]="entry.can_execute"> Ejecutar</label>
                  <label><input type="checkbox" [(ngModel)]="entry.can_edit"> Editar</label>
                  <label><input type="checkbox" [(ngModel)]="entry.can_schedule"> Programar</label>
                </div>
              }
            </div>
          }
        </div>
        <button type="button" class="btn-primary w-full mt-3" (click)="saveAccess()">Guardar accesos</button>
      }
    </div>
  `
})
export class ScriptGovernanceComponent implements OnChanges {
  @Input({ required: true }) scriptId!: number;
  view: GovernanceView = 'policy';
  loading = false;
  policy: any = {};
  versions: any[] = [];
  accessRows: any[] = [];
  versionFile: File | null = null;
  newVersion = '';
  versionNotes = '';

  constructor(private svc: PyflowService) {}
  ngOnChanges() { if (this.scriptId) this.load(); }

  tabClass(view: GovernanceView) {
    return `px-2 py-1.5 rounded text-[10px] font-semibold ${this.view === view ? 'bg-accent text-white' : 'text-muted'}`;
  }

  load() {
    this.loading = true;
    this.svc.getScriptGovernance(this.scriptId).subscribe({
      next: data => {
        this.policy = { ...data.policy };
        this.versions = data.versions || [];
        const access = new Map((data.access || []).map((item: any) => [Number(item.user_id), item]));
        this.accessRows = (data.users || []).map((user: any) => {
          const current: any = access.get(Number(user.id));
          return {
            user_id: user.id,
            username: user.username,
            display_name: user.display_name,
            enabled: !!current,
            can_view: current?.can_view ?? true,
            can_execute: current?.can_execute ?? false,
            can_edit: current?.can_edit ?? false,
            can_schedule: current?.can_schedule ?? false
          };
        });
        this.loading = false;
      },
      error: error => { this.loading = false; this.svc.showToast(error?.error?.message || 'No se pudo cargar gobierno.', 'error'); }
    });
  }

  savePolicy() {
    this.svc.updateScriptPolicy(this.scriptId, this.policy).subscribe({
      next: () => this.svc.showToast('Política guardada.'),
      error: error => this.svc.showToast(error?.error?.message || 'No se pudo guardar la política.', 'error')
    });
  }

  saveAccess() {
    const entries = this.accessRows.filter(item => item.enabled);
    this.svc.updateScriptAccess(this.scriptId, entries).subscribe({
      next: () => { this.svc.showToast('Accesos guardados.'); this.load(); },
      error: error => this.svc.showToast(error?.error?.message || 'No se pudieron guardar accesos.', 'error')
    });
  }

  selectVersionFile(event: Event) {
    this.versionFile = (event.target as HTMLInputElement).files?.[0] || null;
  }

  uploadVersion() {
    if (!this.versionFile || !this.newVersion) return;
    this.svc.uploadScriptVersion(this.scriptId, this.versionFile, this.newVersion, this.versionNotes).subscribe({
      next: () => {
        this.svc.showToast('Nueva versión publicada.');
        this.versionFile = null; this.newVersion = ''; this.versionNotes = '';
        this.svc.loadScripts(); this.load();
      },
      error: error => this.svc.showToast(error?.error?.message || 'No se pudo publicar la versión.', 'error')
    });
  }

  restore(version: any) {
    if (!confirm(`¿Restaurar la versión ${version.version}?`)) return;
    this.svc.restoreScriptVersion(this.scriptId, version.id).subscribe({
      next: () => { this.svc.showToast(`Versión ${version.version} restaurada.`); this.svc.loadScripts(); this.load(); },
      error: error => this.svc.showToast(error?.error?.message || 'No se pudo restaurar la versión.', 'error')
    });
  }
}
