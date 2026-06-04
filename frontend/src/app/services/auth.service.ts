import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ThemeService } from './theme.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  token = signal<string | null>(localStorage.getItem('pyflow_token'));
  user = signal<any>(JSON.parse(localStorage.getItem('pyflow_user') || 'null'));
  loading = signal(false);

  constructor(private http: HttpClient, private themes: ThemeService) {
    const theme = this.user()?.theme;
    if (theme) this.themes.setTheme(theme, false);
  }

  isAuthenticated() { return !!this.token(); }
  authHeaders() { return { Authorization: `Bearer ${this.token() || ''}` }; }

  login(username: string, password: string, provider = 'local') {
    this.loading.set(true);
    return this.http.post<any>('/api/auth/login', { username, password, provider });
  }

  completeLogin(res: any) {
    this.loading.set(false);
    if (!res?.token) return;
    localStorage.setItem('pyflow_token', res.token);
    localStorage.setItem('pyflow_user', JSON.stringify(res.user));
    this.token.set(res.token);
    this.user.set(res.user);
    if (res.user?.theme) this.themes.setTheme(res.user.theme, false);
  }

  logout() {
    localStorage.removeItem('pyflow_token');
    localStorage.removeItem('pyflow_user');
    this.token.set(null); this.user.set(null);
  }

  forgotPassword(email: string, channel = 'email') { return this.http.post<any>('/api/auth/forgot-password', { email, channel }); }
  resetPassword(token: string, password: string) { return this.http.post<any>('/api/auth/reset-password', { token, password }); }
}
