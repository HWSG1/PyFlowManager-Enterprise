import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ThemeService } from './theme.service';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  token = signal<string | null>(localStorage.getItem('pyflow_token'));
  user = signal<any>(JSON.parse(localStorage.getItem('pyflow_user') || 'null'));
  mustChangePassword = signal(!!this.user()?.mustChangePassword);
  showChangePasswordModal = signal(false);
  loading = signal(false);

  constructor(private http: HttpClient, private themes: ThemeService) {
    const theme = this.user()?.theme;
    if (theme) this.themes.setTheme(theme, false);
  }

  isAuthenticated() { return !!this.token(); }
  authHeaders() { return { Authorization: `Bearer ${this.token() || ''}` }; }

  login(username: string, password: string, provider = 'local') {
    this.loading.set(true);
    return this.http.post<any>(`${environment.apiUrl}/auth/login`, { username, password, provider });
  }

  completeLogin(res: any) {
    this.loading.set(false);
    if (!res?.token) return;
    const user = {
      ...res.user,
      mustChangePassword: !!(res.mustChangePassword || res.user?.mustChangePassword)
    };
    localStorage.setItem('pyflow_token', res.token);
    localStorage.setItem('pyflow_user', JSON.stringify(user));
    this.token.set(res.token);
    this.user.set(user);
    this.mustChangePassword.set(user.mustChangePassword);
    this.showChangePasswordModal.set(user.mustChangePassword);
    if (user?.theme) this.themes.setTheme(user.theme, false);
  }

  logout() {
    localStorage.removeItem('pyflow_token');
    localStorage.removeItem('pyflow_user');
    this.token.set(null);
    this.user.set(null);
    this.mustChangePassword.set(false);
    this.showChangePasswordModal.set(false);
  }

  forgotPassword(email: string, channel = 'email') {
    return this.http.post<any>(`${environment.apiUrl}/auth/forgot-password`, { email, channel });
  }

  resetPassword(token: string, password: string) {
    return this.http.post<any>(`${environment.apiUrl}/auth/reset-password`, { token, password });
  }

  changePassword(currentPassword: string, newPassword: string) {
    return this.http.post<any>(
      `${environment.apiUrl}/auth/change-password`,
      { currentPassword, newPassword },
      { headers: this.authHeaders() }
    );
  }

  completePasswordChange(res: any) {
    if (res?.token) {
      localStorage.setItem('pyflow_token', res.token);
      this.token.set(res.token);
    }

    const nextUser = {
      ...(this.user() || {}),
      ...(res?.user || {}),
      mustChangePassword: false
    };
    localStorage.setItem('pyflow_user', JSON.stringify(nextUser));
    this.user.set(nextUser);
    this.mustChangePassword.set(false);
    this.showChangePasswordModal.set(false);
  }
}
