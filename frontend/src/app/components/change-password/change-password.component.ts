import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    @if (auth.showChangePasswordModal()) {
      <div class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[70] p-4">
        <div class="card w-full max-w-md rounded-lg p-6 border border-app shadow-2xl">
          <div class="mb-5">
            <h2 class="text-xl font-bold text-app">Cambiar contraseña</h2>
            <p class="text-sm text-muted mt-1">
              @if (auth.mustChangePassword()) {
                Debes actualizar tu contraseña para continuar.
              } @else {
                Actualiza tu contraseña local de PyFlow.
              }
            </p>
          </div>

          <form (ngSubmit)="save()" class="space-y-3">
            <div>
              <label class="text-xs text-muted">Contraseña actual</label>
              <input class="input mt-1" [(ngModel)]="currentPassword" name="currentPassword" type="password" autocomplete="current-password">
            </div>

            <div>
              <label class="text-xs text-muted">Nueva contraseña</label>
              <input class="input mt-1" [(ngModel)]="newPassword" name="newPassword" type="password" autocomplete="new-password">
            </div>

            <div>
              <label class="text-xs text-muted">Confirmar nueva contraseña</label>
              <input class="input mt-1" [(ngModel)]="confirmPassword" name="confirmPassword" type="password" autocomplete="new-password">
            </div>

            @if (message) {
              <div class="rounded-lg border border-app p-3 text-xs" [ngClass]="error ? 'text-red-300' : 'text-emerald-300'">
                {{ message }}
              </div>
            }

            <div class="flex justify-end gap-2 pt-2">
              @if (!auth.mustChangePassword()) {
                <button type="button" class="btn-secondary" (click)="close()">Cancelar</button>
              } @else {
                <button type="button" class="btn-secondary" (click)="auth.logout()">Salir</button>
              }
              <button type="submit" class="btn-primary" [disabled]="saving">
                {{ saving ? 'Guardando...' : 'Guardar contraseña' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    }
  `
})
export class ChangePasswordComponent {
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';
  message = '';
  error = false;
  saving = false;

  constructor(public auth: AuthService) {}

  close() {
    this.auth.showChangePasswordModal.set(false);
    this.reset();
  }

  save() {
    this.message = '';
    this.error = false;

    if (!this.currentPassword || !this.newPassword) {
      this.error = true;
      this.message = 'Ingresa la contraseña actual y la nueva contraseña.';
      return;
    }

    if (this.newPassword.length < 8) {
      this.error = true;
      this.message = 'La nueva contraseña debe tener al menos 8 caracteres.';
      return;
    }

    if (this.newPassword !== this.confirmPassword) {
      this.error = true;
      this.message = 'La confirmación no coincide con la nueva contraseña.';
      return;
    }

    this.saving = true;
    this.auth.changePassword(this.currentPassword, this.newPassword).subscribe({
      next: res => {
        this.saving = false;
        this.auth.completePasswordChange(res);
        this.reset();
      },
      error: err => {
        this.saving = false;
        this.error = true;
        this.message = err?.error?.message || err.message || 'No se pudo cambiar la contraseña.';
      }
    });
  }

  private reset() {
    this.currentPassword = '';
    this.newPassword = '';
    this.confirmPassword = '';
    this.message = '';
    this.error = false;
  }
}
