import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

export interface ThemeItem { theme_key: string; theme_name: string; is_dark: boolean; }

@Injectable({ providedIn: 'root' })
export class ThemeService {
  themes = signal<ThemeItem[]>([]);
  activeTheme = signal(localStorage.getItem('pyflow_theme') || 'dark-blue');

  constructor(private http: HttpClient) { this.applyTheme(this.activeTheme()); this.loadThemes(); }

  loadThemes() {
    this.http.get<ThemeItem[]>(`${environment.apiUrl}/themes`).subscribe({
      next: rows => this.themes.set(rows || []),
      error: () => this.themes.set(this.defaultThemes())
    });
  }

  setTheme(themeKey: string, persist = true) {
    this.activeTheme.set(themeKey);
    this.applyTheme(themeKey);
    localStorage.setItem('pyflow_theme', themeKey);
    if (persist && localStorage.getItem('pyflow_token')) {
      this.http.post(`${environment.apiUrl}/themes/me`, { theme_key: themeKey }, { headers: { Authorization: `Bearer ${localStorage.getItem('pyflow_token')}` } }).subscribe({ error: () => {} });
    }
  }

  applyTheme(themeKey: string) { document.documentElement.setAttribute('data-theme', themeKey); }

  defaultThemes(): ThemeItem[] {
    return ['dark-blue','light','corporate-gray','banking-blue','navy','emerald','purple','crimson','ocean','aurora','matrix','cyberpunk','dracula','nord','monokai','github-dark','vscode-dark','gold','titanium','obsidian']
      .map(x => ({ theme_key: x, theme_name: x.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), is_dark: x !== 'light' }));
  }
}
