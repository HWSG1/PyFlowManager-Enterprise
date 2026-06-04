import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { ThemeService } from '../../services/theme.service';

@Component({ selector: 'app-users', standalone: true, imports: [CommonModule, FormsModule], template: `
<div class="flex flex-col gap-6">
  <div class="flex justify-between items-start">
    <div><h1 class="text-2xl font-bold text-app">Usuarios, roles y permisos</h1><p class="text-sm text-muted">Administra usuarios, método de autenticación, estado y tema visual.</p></div>
    <button class="btn-primary" (click)="newUser()">+ Nuevo usuario</button>
  </div>

  <div class="card rounded-xl overflow-hidden">
    <table class="w-full text-sm"><thead><tr class="border-b border-app text-muted text-left"><th class="p-3">Usuario</th><th>Correo</th><th>Roles</th><th>Auth</th><th>Estado</th><th>Tema</th><th></th></tr></thead>
    <tbody>@for (u of users; track u.id) {<tr class="border-b border-app"><td class="p-3 font-semibold">{{u.display_name}}<br><span class="text-xs text-muted">{{u.username}}</span></td><td>{{u.email}}</td><td>{{u.roles}}</td><td>{{u.auth_provider}}</td><td>{{u.is_active}}</td><td>{{u.theme_key}}</td><td><button class="text-accent text-xs" (click)="edit(u)">Editar</button></td></tr>}</tbody></table>
  </div>

  @if (form) { <div class="card rounded-xl p-5">
    <h3 class="font-semibold mb-4">{{form.id ? 'Editar usuario' : 'Nuevo usuario'}}</h3>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <input class="input" [(ngModel)]="form.username" placeholder="Usuario" [disabled]="!!form.id">
      <input class="input" [(ngModel)]="form.display_name" placeholder="Nombre completo">
      <input class="input" [(ngModel)]="form.email" placeholder="Correo">
      <select class="input" [(ngModel)]="form.auth_provider"><option value="local">Local</option><option value="entra">Microsoft Entra ID</option><option value="mixed">Mixta</option></select>
      <select class="input" [(ngModel)]="form.is_active"><option value="true">Activo</option><option value="false">Inactivo</option></select>
      <select class="input" [(ngModel)]="form.theme_key">@for (t of themes.themes(); track t.theme_key) {<option [value]="t.theme_key">{{t.theme_name}}</option>}</select>
      @if (!form.id) { <input class="input" [(ngModel)]="form.password" type="password" placeholder="Contraseña inicial"> }
    </div>
    <div class="flex justify-end gap-2 mt-4"><button class="btn-secondary" (click)="form=null">Cancelar</button><button class="btn-primary" (click)="save()">Guardar</button></div>
  </div> }
</div>`})
export class UsersComponent implements OnInit {
  users: any[] = []; form: any = null;
  constructor(public svc: PyflowService, public themes: ThemeService) {}
  ngOnInit() { this.load(); }
  load() { this.svc.getUsers().subscribe({ next: (r:any) => this.users = r, error: e => this.svc.showToast(`Error cargando usuarios: ${e?.error?.message || e.message}`, 'error') }); }
  newUser() { this.form = { username:'', display_name:'', email:'', password:'PyFlow123*', is_active:'ACTIVE', auth_provider:'local', theme_key:'dark-blue' }; }
  edit(u:any) { this.form = { ...u }; }
  save() { const req = this.form.id ? this.svc.updateUser(this.form.id, this.form) : this.svc.createUser(this.form); req.subscribe({ next: () => { this.svc.showToast('Usuario guardado.'); this.form=null; this.load(); }, error: e => this.svc.showToast(`Error guardando usuario: ${e?.error?.message || e.message}`, 'error') }); }
}
