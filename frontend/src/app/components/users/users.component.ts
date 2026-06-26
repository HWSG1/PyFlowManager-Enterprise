import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PyflowService } from '../../services/pyflow.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-6">
      <div class="flex justify-between items-start gap-4">
        <div>
          <h1 class="text-2xl font-bold text-app">Usuarios, roles y permisos</h1>
          <p class="text-sm text-muted">Administra usuarios, roles, método de autenticación, estado y tema visual.</p>
        </div>
        <button class="btn-primary" (click)="newUser()">+ Nuevo usuario</button>
      </div>

      <div class="card rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-app text-muted text-left">
              <th class="p-3">Usuario</th>
              <th>Correo</th>
              <th>Roles</th>
              <th>Auth</th>
              <th>Estado</th>
              <th>Contraseña</th>
              <th>Tema</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (u of users; track u.id) {
              <tr class="border-b border-app">
                <td class="p-3 font-semibold">
                  {{u.display_name || u.username}}<br>
                  <span class="text-xs text-muted">{{u.username}}</span>
                </td>
                <td>{{u.email}}</td>
                <td class="max-w-64">
                  <span class="text-xs text-muted">{{u.roles || 'Sin roles'}}</span>
                </td>
                <td>{{labelAuth(u.auth_provider)}}</td>
                <td>
                  <span class="text-xs px-2 py-1 rounded-full" [ngClass]="isActive(u) ? 'bg-emerald-500/15 text-emerald-300' : 'bg-red-500/15 text-red-300'">
                    {{isActive(u) ? 'Activo' : 'Inactivo'}}
                  </span>
                </td>
                <td>
                  @if (u.must_change_password) {
                    <span class="text-xs text-amber-300">Debe cambiarla</span>
                  } @else {
                    <span class="text-xs text-muted">Normal</span>
                  }
                </td>
                <td>{{u.theme_key}}</td>
                <td>
                  <button class="text-accent text-xs font-semibold" (click)="edit(u)">Editar</button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>

      @if (form) {
        <div class="card rounded-lg p-5">
          <div class="flex items-start justify-between mb-4">
            <div>
              <h3 class="font-semibold">{{form.id ? 'Editar usuario' : 'Nuevo usuario'}}</h3>
              <p class="text-xs text-muted">
                @if (!form.id) {
                  El usuario local deberá cambiar la contraseña inicial al ingresar por primera vez.
                } @else {
                  Los cambios de roles aplican al guardar.
                }
              </p>
            </div>
            <button class="text-muted hover:text-app" (click)="form=null">Cerrar</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label class="text-xs text-muted">Usuario</label>
              <input class="input mt-1" [(ngModel)]="form.username" placeholder="usuario" [disabled]="!!form.id">
            </div>
            <div>
              <label class="text-xs text-muted">Nombre completo</label>
              <input class="input mt-1" [(ngModel)]="form.display_name" placeholder="Nombre completo">
            </div>
            <div>
              <label class="text-xs text-muted">Correo</label>
              <input class="input mt-1" [(ngModel)]="form.email" placeholder="correo@empresa.com">
            </div>
            <div>
              <label class="text-xs text-muted">Autenticación</label>
              <select class="input mt-1" [(ngModel)]="form.auth_provider">
                <option value="local">Local</option>
                <option value="entra_id">Microsoft Entra ID</option>
                <option value="active_directory">Active Directory</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-muted">Estado</label>
              <select class="input mt-1" [(ngModel)]="form.is_active">
                <option [ngValue]="true">Activo</option>
                <option [ngValue]="false">Inactivo</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-muted">Tema</label>
              <select class="input mt-1" [(ngModel)]="form.theme_key">
                @for (t of themes.themes(); track t.theme_key) {
                  <option [value]="t.theme_key">{{t.theme_name}}</option>
                }
              </select>
            </div>
            @if (!form.id) {
              <div>
                <label class="text-xs text-muted">Contraseña inicial</label>
                <input class="input mt-1" [(ngModel)]="form.password" type="password" placeholder="Contraseña inicial">
              </div>
            }
            @if (form.id) {
              <label class="flex items-center gap-2 text-sm text-muted mt-7">
                <input type="checkbox" [(ngModel)]="form.must_change_password">
                Forzar cambio de contraseña en próximo login
              </label>
            }
          </div>

          <div class="mt-5">
            <p class="text-xs font-semibold text-muted mb-2">Roles</p>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
              @for (role of roles; track role.id) {
                <label class="border border-app rounded-lg px-3 py-2 flex items-start gap-2 cursor-pointer hover:bg-white/5">
                  <input type="checkbox" [checked]="hasRole(role.id)" (change)="toggleRole(role.id, $any($event.target).checked)">
                  <span>
                    <span class="block text-sm font-semibold text-app">{{role.role_name}}</span>
                    <span class="block text-xs text-muted">{{role.description || role.auth_method}}</span>
                  </span>
                </label>
              }
            </div>
          </div>

          @if (form.id) {
            <div class="mt-5 border-t border-app pt-4">
              <p class="text-xs font-semibold text-muted mb-2">Resetear contraseña</p>
              <div class="flex flex-col md:flex-row gap-2">
                <input class="input md:max-w-xs" [(ngModel)]="resetPassword" type="password" placeholder="Nueva contraseña temporal">
                <button class="btn-secondary" (click)="resetSelectedPassword()">Resetear y forzar cambio</button>
              </div>
            </div>
          }

          <div class="flex justify-end gap-2 mt-5">
            <button class="btn-secondary" (click)="form=null">Cancelar</button>
            <button class="btn-primary" (click)="save()">Guardar usuario</button>
          </div>
        </div>
      }
    </div>
  `
})
export class UsersComponent implements OnInit {
  users: any[] = [];
  roles: any[] = [];
  form: any = null;
  resetPassword = '';

  constructor(public svc: PyflowService, public themes: ThemeService) {}

  ngOnInit() {
    this.load();
    this.loadRoles();
  }

  load() {
    this.svc.getUsers().subscribe({
      next: (r: any) => this.users = r,
      error: e => this.svc.showToast(`Error cargando usuarios: ${e?.error?.message || e.message}`, 'error')
    });
  }

  loadRoles() {
    this.svc.getRoles().subscribe({
      next: roles => this.roles = roles || [],
      error: e => this.svc.showToast(`Error cargando roles: ${e?.error?.message || e.message}`, 'error')
    });
  }

  newUser() {
    this.resetPassword = '';
    this.form = {
      username: '',
      display_name: '',
      email: '',
      password: 'PyFlow123*',
      is_active: true,
      auth_provider: 'local',
      theme_key: 'dark-blue',
      role_ids: []
    };
  }

  edit(user: any) {
    this.resetPassword = '';
    this.form = {
      ...user,
      is_active: this.isActive(user),
      must_change_password: !!user.must_change_password,
      role_ids: this.parseRoleIds(user.role_ids)
    };
  }

  save() {
    const payload = {
      ...this.form,
      role_ids: this.form.role_ids || []
    };

    const request = payload.id
      ? this.svc.updateUser(payload.id, payload)
      : this.svc.createUser(payload);

    request.subscribe({
      next: () => {
        this.svc.showToast('Usuario guardado.');
        this.form = null;
        this.load();
      },
      error: e => this.svc.showToast(`Error guardando usuario: ${e?.error?.message || e.message}`, 'error')
    });
  }

  resetSelectedPassword() {
    if (!this.form?.id) return;
    if (!this.resetPassword || this.resetPassword.length < 8) {
      this.svc.showToast('La contraseña temporal debe tener al menos 8 caracteres.', 'warning');
      return;
    }

    this.svc.resetUserPassword(this.form.id, this.resetPassword).subscribe({
      next: () => {
        this.svc.showToast('Contraseña reseteada. El usuario deberá cambiarla al iniciar sesión.');
        this.resetPassword = '';
        this.form.must_change_password = true;
        this.load();
      },
      error: e => this.svc.showToast(`Error reseteando contraseña: ${e?.error?.message || e.message}`, 'error')
    });
  }

  hasRole(roleId: number) {
    return (this.form?.role_ids || []).includes(roleId);
  }

  toggleRole(roleId: number, checked: boolean) {
    const current = new Set<number>(this.form?.role_ids || []);
    checked ? current.add(roleId) : current.delete(roleId);
    this.form.role_ids = Array.from(current);
  }

  isActive(user: any) {
    return user?.is_active === true || user?.is_active === 1 || user?.is_active === '1' || user?.is_active === 'true';
  }

  labelAuth(value: string) {
    const labels: Record<string, string> = {
      local: 'Local',
      entra_id: 'Entra ID',
      azure_ad: 'Entra ID',
      active_directory: 'Active Directory'
    };
    return labels[value] || value || 'Local';
  }

  private parseRoleIds(value: any): number[] {
    if (Array.isArray(value)) return value.map(Number).filter(Number.isFinite);
    return String(value || '')
      .split(',')
      .map(item => Number(item.trim()))
      .filter(Number.isFinite);
  }
}
