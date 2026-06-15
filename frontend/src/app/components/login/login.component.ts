import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
  <div class="min-h-screen bg-app text-app flex items-center justify-center p-6">
    <div class="w-full max-w-md card p-7 rounded-2xl shadow-2xl">
      <div class="mb-6 text-center">
        <div class="mx-auto w-12 h-12 rounded-xl bg-accent text-white flex items-center justify-center font-bold text-xl">PF</div>
        <h1 class="mt-4 text-2xl font-bold">PyFlow Manager</h1>
        <p class="text-sm text-muted">Inicio de sesión empresarial</p>
      </div>

      @if (mode === 'login') {
        <form (ngSubmit)="loginLocal()">
          <label class="text-xs text-muted">Usuario o correo</label>
          <input [(ngModel)]="username" name="username" class="input mb-3" placeholder="admin" autocomplete="username">

          <label class="text-xs text-muted">Contraseña</label>
          <div class="relative mb-4">
            <input
              [(ngModel)]="password"
              name="password"
              [type]="showPassword ? 'text' : 'password'"
              class="input pr-24"
              placeholder="••••••••"
              autocomplete="current-password">
            <button
              type="button"
              (click)="showPassword = !showPassword"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-accent">
              {{ showPassword ? 'Ocultar' : 'Ver' }}
            </button>
          </div>

          <button type="submit" class="btn-primary w-full mb-3">Ingresar con usuario y contraseña</button>
        </form>

        <button type="button" (click)="loginEntra()" class="btn-secondary w-full">Microsoft Entra ID / Azure AD</button>
        <button type="button" (click)="mode='forgot'" class="text-accent text-xs mt-4 w-full">¿Olvidaste tu contraseña?</button>
      }

      @if (mode === 'forgot') {
        <p class="text-sm text-muted mb-4">Ingresa tu correo para generar un token temporal. El envío por SMTP/SMS queda preparado para configuración.</p>
        <input [(ngModel)]="email" class="input mb-3" placeholder="correo@dominio.com">
        <div class="grid grid-cols-2 gap-2 mb-3">
          <button (click)="forgot('email')" class="btn-primary">Correo</button>
          <button (click)="forgot('sms')" class="btn-secondary">SMS bajo costo</button>
        </div>
        <button (click)="mode='reset'" class="text-accent text-xs">Ya tengo token</button>
      }

      @if (mode === 'reset') {
        <input [(ngModel)]="resetToken" class="input mb-3" placeholder="Token temporal">
        <input [(ngModel)]="newPassword" type="password" class="input mb-3" placeholder="Nueva contraseña">
        <button (click)="reset()" class="btn-primary w-full">Cambiar contraseña</button>
      }

      @if (message) { <div class="mt-4 text-xs rounded-lg p-3 border border-app text-muted whitespace-pre-wrap">{{ message }}</div> }
    </div>
  </div>`
})
export class LoginComponent {
  mode: 'login' | 'forgot' | 'reset' = 'login';
  username = 'admin';
  password = '';
  email = '';
  resetToken = '';
  newPassword = '';
  message = '';
  showPassword = false;

  constructor(public auth: AuthService) {}

  loginLocal() {
    this.message = '';

    this.auth.login(this.username, this.password, 'local').subscribe({
      next: r => {
        if (r.token) {
          this.auth.completeLogin(r);
          return;
        }

        this.message = r.message || 'No se pudo iniciar sesión.';
      },
      error: e => this.message = e?.error?.message || e.message
    });
  }

  loginEntra() {
    this.message = '';

    this.auth.login('', '', 'entra').subscribe({
      next: r => {
        if (r.redirectUrl) {
          window.location.href = r.redirectUrl;
          return;
        }

        this.message = r.message || 'Proveedor externo preparado.';
      },
      error: e => this.message = e?.error?.message || e.message
    });
  }

  forgot(channel: string) {
    this.auth.forgotPassword(this.email, channel).subscribe({
      next: r => this.message = `${r.message || 'Solicitud procesada.'}${r.devToken ? '\nToken dev: ' + r.devToken : ''}`,
      error: e => this.message = e?.error?.message || e.message
    });
  }

  reset() {
    this.auth.resetPassword(this.resetToken, this.newPassword).subscribe({
      next: () => {
        this.message = 'Contraseña actualizada.';
        this.mode = 'login';
      },
      error: e => this.message = e?.error?.message || e.message
    });
  }
}
