
import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { interval, Subscription } from 'rxjs';
import { Script, Execution, Schedule, Toast, TabName, EnvParam } from '../models/models';
import { environment } from '../../environments/environment';

function formatDate(value: any): string {
  if (!value) return 'Nunca';

  const raw = String(value).trim();
  const sqlDateWithoutTimezone = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}(?:\.\d+)?)$/.exec(raw);
  const normalized = sqlDateWithoutTimezone
    ? `${sqlDateWithoutTimezone[1]}T${sqlDateWithoutTimezone[2]}Z`
    : raw;
  const date = value instanceof Date ? value : new Date(normalized);

  if (Number.isNaN(date.getTime())) {
    return raw;
  }

  return new Intl.DateTimeFormat('es-HN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'America/Tegucigalpa'
  }).format(date);
}

function formatDuration(seconds: any): string {
  if (seconds === null || seconds === undefined || isNaN(Number(seconds))) return '--';
  const s = Number(seconds);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${r}s`;
}

@Injectable({ providedIn: 'root' })
export class PyflowService {
  private apiUrl = environment.apiUrl;
  private updatingFromHistory = false;
  private readonly tabs = new Set<TabName>([
    'dashboard',
    'scripts',
    'script-detail',
    'schedules',
    'logs',
    'settings',
    'users'
  ]);
  private pendingScriptDetailId: number | null = null;

  activeTab = signal<TabName>('dashboard');
  selectedScript = signal<Script | null>(null);
  toasts = signal<Toast[]>([]);
  showImportModal = signal(false);
  toastCounter = 0;

  scripts = signal<Script[]>([]);
  executions = signal<Execution[]>([]);
  schedules = signal<Schedule[]>([]);
  envParams = signal<EnvParam[]>([]);
  systemSettings = signal<any[]>([]);
  autoRefreshIntervalSeconds = signal(30);
  private autoRefreshSub: Subscription | null = null;
  selectedExecutionParameters = signal<any[]>([]);
  showExecutionParametersModal = signal(false);
  selectedExecutionLogId = signal<number | null>(null);
  editingScheduleId = signal<number | null>(null);
  editingScheduleData = signal<any>(null);

  runningExecutions = computed(() => this.executions().filter(e => e.status === 'Ejecutando').length);
  totalScripts = computed(() => this.scripts().length);
  activeScripts = computed(() => this.scripts().filter(s => s.status === 'active').length);
  errorScripts = computed(() => this.scripts().filter(s => s.lastStatus === 'Error').length);

  constructor(private http: HttpClient) {
    this.setupBrowserHistory();
    this.refreshAll();
    this.startAutoRefresh();
  }

  uploadScript(
    file: File,
    name: string,
    description: string,
    category: string
  ) {
    const formData = new FormData();

    formData.append('file', file);
    formData.append('name', name);
    formData.append('description', description);
    formData.append('category', category);
    formData.append('version', '1.0.0');

    return this.http.post(`${this.apiUrl}/scripts`, formData);
  }

  refreshAll() {
    this.loadDashboard();
    this.loadScripts();
    this.loadExecutions();
    this.loadSchedules();
    this.loadSettings();
  }

  loadScripts() {
    this.http.get<any[]>(`${this.apiUrl}/scripts`).subscribe({
      next: rows => {
        this.scripts.set(rows.map(this.mapScript));
        this.resolvePendingScriptDetail();
      },
      error: err => this.showToast(`Error cargando scripts: ${err?.error?.message || err.message}`, 'error')
    });
  }

  loadExecutions() {
    this.http.get<any[]>(`${this.apiUrl}/executions`).subscribe({
      next: rows => this.executions.set(rows.map(this.mapExecution)),
      error: err => this.showToast(`Error cargando ejecuciones: ${err?.error?.message || err.message}`, 'error')
    });
  }

  loadSchedules() {
    this.http.get<any[]>(`${this.apiUrl}/schedules`).subscribe({
      next: rows => this.schedules.set(rows.map(this.mapSchedule)),
      error: err => this.showToast(`Error cargando schedules: ${err?.error?.message || err.message}`, 'error')
    });
  }

  loadSettings() {
    this.http.get<any>(`${this.apiUrl}/settings`).subscribe({
      next: data => {
        const vars = (data?.globalVars || []).map((x: any) => ({
          id: x.id,
          key: x.var_key,
          value: x.var_value,
          isSecret: !!x.is_secret,
          description: x.description || ''
        }));

        this.envParams.set(vars);

        const settings = data?.systemSettings || [];
        this.systemSettings.set(settings);
        const refresh = Number(settings.find((x: any) => x.setting_key === 'AUTO_REFRESH_INTERVAL_SECONDS')?.setting_value || 30);
        if (refresh !== this.autoRefreshIntervalSeconds()) {
          this.autoRefreshIntervalSeconds.set(refresh);
          this.startAutoRefresh();
        }
      },
      error: () => {}
    });
  }

  mapScript(row: any): Script {
    return {
      id: row.id,
      name: row.name,
      category: row.category || 'ETL',
      path: row.file_path || '',
      status: row.is_active ? 'active' : 'inactive',
      lastRun: formatDate(row.last_execution_start_time),
      nextRun: formatDate(row.next_run_at),
      lastStatus: row.last_execution_status || 'Nunca',
      description: row.description || '',
      author: row.created_by || 'Admin_User',
      version: row.current_version || '1.0.0',
      successCount: row.total_success || 0,
      errorCount: row.total_errors || 0,
      avgDuration: formatDuration(row.last_duration_seconds)
    };
  }

  mapExecution(row: any): Execution {
    return {
      id: `EX-${row.id}`,
      script: row.script_name,
      status: row.status,
      start: formatDate(row.start_time),
      end: row.end_time ? formatDate(row.end_time) : '--',
      duration: formatDuration(row.duration_seconds),
      user: row.triggered_by || 'Sistema',
      message: row.error_message || row.trigger_type || ''
    };
  }

  mapSchedule(row: any): Schedule {
    return {
      id: row.id,
      scriptId: row.script_id,
      scriptName: row.script_name,
      frequency: row.frequency_label || 'Personalizado',
      cronExpression: row.cron_expression || '',
      nextRun: formatDate(row.next_run_at),
      status: row.is_active ? 'active' : 'paused'
    };
  }

  switchTab(tab: TabName) {
    this.activeTab.set(tab);
    this.selectedScript.set(tab === 'script-detail' ? this.selectedScript() : null);
    this.pushBrowserState(tab);
  }

  openScriptDetail(script: Script, executionId?: string | number) {
    const cleanExecutionId = executionId === undefined
      ? null
      : Number(String(executionId).replace('EX-', ''));

    this.selectedExecutionLogId.set(
      cleanExecutionId !== null && Number.isFinite(cleanExecutionId)
        ? cleanExecutionId
        : null
    );
    this.selectedScript.set(script);
    this.activeTab.set('script-detail');
    this.pushBrowserState('script-detail', script.id);
  }

  consumeSelectedExecutionLogId(): number | null {
    const executionId = this.selectedExecutionLogId();
    this.selectedExecutionLogId.set(null);
    return executionId;
  }

  private setupBrowserHistory() {
    if (typeof window === 'undefined') return;

    const initial = this.getBrowserStateFromHash();
    if (initial) {
      this.applyBrowserState(initial.tab, initial.scriptId);
    }

    const currentTab = this.activeTab();
    const currentScriptId = this.selectedScript()?.id;
    window.history.replaceState(
      { pyflow: true, tab: currentTab, scriptId: currentScriptId },
      '',
      this.browserUrl(currentTab, currentScriptId)
    );
    window.history.pushState(
      { pyflow: true, tab: currentTab, scriptId: currentScriptId },
      '',
      this.browserUrl(currentTab, currentScriptId)
    );

    window.addEventListener('popstate', event => {
      const state = event.state?.pyflow
        ? event.state
        : this.getBrowserStateFromHash();

      if (!state?.tab) {
        this.pushBrowserState(this.activeTab(), this.selectedScript()?.id, true);
        return;
      }

      this.applyBrowserState(state.tab, state.scriptId);
    });
  }

  private pushBrowserState(tab: TabName, scriptId?: number, replace = false) {
    if (typeof window === 'undefined' || this.updatingFromHistory) return;

    const state = { pyflow: true, tab, scriptId };
    const url = this.browserUrl(tab, scriptId);

    if (replace) {
      window.history.replaceState(state, '', url);
      return;
    }

    window.history.pushState(state, '', url);
  }

  private applyBrowserState(tab: TabName, scriptId?: number) {
    if (!this.tabs.has(tab)) return;

    this.updatingFromHistory = true;
    this.activeTab.set(tab);

    if (tab === 'script-detail' && scriptId) {
      const script = this.scripts().find(item => item.id === Number(scriptId));
      this.selectedScript.set(script || this.selectedScript());
      this.pendingScriptDetailId = script ? null : Number(scriptId);
    } else {
      this.selectedScript.set(null);
      this.pendingScriptDetailId = null;
    }

    this.updatingFromHistory = false;
  }

  private resolvePendingScriptDetail() {
    if (!this.pendingScriptDetailId || this.activeTab() !== 'script-detail') return;

    const script = this.scripts().find(item => item.id === this.pendingScriptDetailId);
    if (!script) return;

    this.selectedScript.set(script);
    this.pendingScriptDetailId = null;
  }

  private browserUrl(tab: TabName, scriptId?: number) {
    if (tab === 'script-detail' && scriptId) {
      return `#/scripts/${scriptId}`;
    }

    return `#/${tab}`;
  }

  private getBrowserStateFromHash(): { tab: TabName; scriptId?: number } | null {
    if (typeof window === 'undefined') return null;

    const hash = window.location.hash.replace(/^#\/?/, '');
    const [section, id] = hash.split('/');

    if (section === 'scripts' && id) {
      return { tab: 'script-detail', scriptId: Number(id) };
    }

    const tab = (section || 'dashboard') as TabName;
    return this.tabs.has(tab) ? { tab } : null;
  }

  addScript(partial: Partial<Script>) {
    const scriptName = partial.name || 'new_script.py';

    const payload = {
      name: scriptName,
      category: partial.category || 'ETL',
      description: partial.description || 'Sin descripción.',
      file_path: (partial as any).file_path || partial.path || `runtime/scripts/${scriptName}`,
      path: (partial as any).file_path || partial.path || `runtime/scripts/${scriptName}`,
      version: partial.version || '1.0.0'
    };

    this.http.post(`${this.apiUrl}/scripts`, payload).subscribe({
      next: () => {
        this.showToast('Script registrado correctamente.');
        this.loadScripts();
      },
      error: err =>
        this.showToast(
          `Error registrando script: ${err?.error?.message || err.message}`,
          'error'
        )
    });
  }
  toggleScriptStatus(id: number) {
    this.http.patch(`${this.apiUrl}/scripts/${id}/toggle`, {}).subscribe({
      next: () => {
        this.showToast('Estado del script actualizado.', 'info');
        this.loadScripts();
      },
      error: err => this.showToast(`Error actualizando estado: ${err?.error?.message || err.message}`, 'error')
    });
  }

  deleteScript(id: number) {
    this.http.delete(`${this.apiUrl}/scripts/${id}`).subscribe({
      next: () => {
        this.showToast('Script desactivado.', 'warning');
        this.loadScripts();
      },
      error: err => this.showToast(`Error eliminando script: ${err?.error?.message || err.message}`, 'error')
    });
  }

  addSchedule(schedule: Partial<Schedule>) {
    return this.http.post(`${this.apiUrl}/schedules`, schedule);
  }

  deleteSchedule(id: number) {
    this.http.delete(`${this.apiUrl}/schedules/${id}`).subscribe({
      next: () => {
        this.showToast('Programación eliminada.', 'info');
        this.loadSchedules();
      },
      error: err => this.showToast(`Error eliminando programación: ${err?.error?.message || err.message}`, 'error')
    });
  }

  executeScript(script: Script, parameters: Record<string, string> = {}) {
    this.showToast(`Ejecutando: ${script.name}`, 'info');

    this.http.post<any>(`${this.apiUrl}/scripts/${script.id}/run`, {
      parameters
    }).subscribe({
      next: result => {
        this.showToast(`Ejecución iniciada: EX-${result.executionId}`, 'info');
        this.loadExecutions();
        this.watchExecution(result.executionId);
      },
      error: err => this.showToast(`Error ejecutando script: ${err?.error?.message || err.message}`, 'error')
    });
  }

  watchExecution(executionId: number) {
    const token = encodeURIComponent(localStorage.getItem('pyflow_token') || '');
    const source = new EventSource(`${this.apiUrl}/executions/${executionId}/stream?access_token=${token}`);

    source.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.done) {
        this.showToast(`Ejecución EX-${executionId}: ${payload.status}`, payload.status === 'Exitoso' ? 'success' : 'error');
        source.close();
        this.loadExecutions();
        this.loadScripts();
      }
    };

    source.onerror = () => {
      source.close();
    };
  }

  getExecutionLogs(executionId: string | number) {
    const id = String(executionId).replace('EX-', '');
    return this.http.get<any[]>(`${this.apiUrl}/executions/${id}/logs`);
  }

  getExecutionParameters(executionId: string | number) {
    const id = String(executionId).replace('EX-', '');

    return this.http.get<any[]>(
      `${this.apiUrl}/executions/${id}/parameters`
    );
  }

  openExecutionParameters(executionId: string | number) {
    this.getExecutionParameters(executionId).subscribe({
      next: rows => {
        this.selectedExecutionParameters.set(rows || []);
        this.showExecutionParametersModal.set(true);
      },
      error: err => {
        this.showToast(
          `Error cargando parámetros: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  showToast(message: string, type: Toast['type'] = 'success') {
    const id = ++this.toastCounter;
    this.toasts.update(t => [...t, { id, message, type }]);
    setTimeout(() => this.removeToast(id), 4000);
  }

  removeToast(id: number) {
    this.toasts.update(t => t.filter(toast => toast.id !== id));
  }

  cancelExecution(executionId: number) {
    return this.http.post(`${this.apiUrl}/scripts/executions/${executionId}/cancel`, {});
  }

  getScriptParameters(scriptId: number) {
    return this.http.get<any[]>(`${this.apiUrl}/scripts/${scriptId}/parameters`);
  }

  getScriptGovernance(scriptId: number) {
    return this.http.get<any>(`${this.apiUrl}/governance/scripts/${scriptId}`);
  }

  updateScriptPolicy(scriptId: number, policy: any) {
    return this.http.put(`${this.apiUrl}/governance/scripts/${scriptId}/policy`, policy);
  }

  updateScriptAccess(scriptId: number, entries: any[]) {
    return this.http.put(`${this.apiUrl}/governance/scripts/${scriptId}/access`, { entries });
  }

  uploadScriptVersion(scriptId: number, file: File, version: string, notes: string) {
    const form = new FormData();
    form.append('file', file);
    form.append('version', version);
    form.append('notes', notes);
    return this.http.post(`${this.apiUrl}/governance/scripts/${scriptId}/versions`, form);
  }

  restoreScriptVersion(scriptId: number, versionId: number) {
    return this.http.post(`${this.apiUrl}/governance/scripts/${scriptId}/versions/${versionId}/restore`, {});
  }

  getAuditEvents() {
    return this.http.get<any[]>(`${this.apiUrl}/governance/audit`);
  }

  toggleScheduleStatus(id: number) {
    this.http.patch(`${this.apiUrl}/schedules/${id}/toggle`, {}).subscribe({
      next: () => {
        this.showToast('Estado de la programación actualizado.', 'info');
        this.loadSchedules();
        this.loadScripts();
      },
      error: err =>
        this.showToast(
          `Error actualizando programación: ${err?.error?.message || err.message}`,
          'error'
        )
    });
  }

  getSchedule(id: number) {
    return this.http.get<any>(
      `${this.apiUrl}/schedules/${id}`
    );
  }

  loadScheduleForEdit(id: number) {
    this.getSchedule(id).subscribe({
      next: data => {
        this.editingScheduleId.set(id);
        this.editingScheduleData.set(data);
      },
      error: err => {
        this.showToast(
          `Error cargando programación: ${err?.error?.message || err.message}`,
          'error'
        );
      }
    });
  }

  updateSchedule(
    id: number,
    payload: any
  ) {
    return this.http.put(
      `${this.apiUrl}/schedules/${id}`,
      payload
    );
  }

  clearEditingSchedule() {
    this.editingScheduleId.set(null);
    this.editingScheduleData.set(null);
  }


  saveGlobalVariables(variables: any[]) {
    return this.http.post(`${this.apiUrl}/settings/global-variables`, {
      variables
    });
  }

  deleteGlobalVariable(id: number) {
    return this.http.delete(`${this.apiUrl}/settings/global-variables/${id}`);
  }

  private authHeaders() {
    return { Authorization: `Bearer ${localStorage.getItem('pyflow_token') || ''}` };
  }

  saveSystemSettings(settings: any[], adminPin: string) {
    return this.http.post(`${this.apiUrl}/settings/system`, { settings, adminPin }, { headers: this.authHeaders() });
  }

  getUsers() {
    return this.http.get(`${this.apiUrl}/users`, { headers: this.authHeaders() });
  }

  createUser(payload: any) {
    return this.http.post(`${this.apiUrl}/users`, payload, { headers: this.authHeaders() });
  }

  updateUser(id: number, payload: any) {
    return this.http.put(`${this.apiUrl}/users/${id}`, payload, { headers: this.authHeaders() });
  }

  startAutoRefresh() {
    this.autoRefreshSub?.unsubscribe();
    const seconds = Math.max(10, Number(this.autoRefreshIntervalSeconds() || 30));
    this.autoRefreshSub = interval(seconds * 1000).subscribe(() => this.refreshCurrentTab());
  }

  refreshCurrentTab() {
    switch (this.activeTab()) {
      case 'dashboard': this.loadDashboard(); break;
      case 'scripts': this.loadScripts(); break;
      case 'schedules': this.loadSchedules(); break;
      case 'logs': this.loadExecutions(); break;
      case 'settings': this.loadSettings(); break;
      case 'users': break;
      default: this.refreshAll(); break;
    }
  }
  
  deleteScriptDefinitively(scriptId: number) {
    return this.http.delete(`${this.apiUrl}/scripts/${scriptId}/definitive`);
  }

  dashboard = signal<any | null>(null);
  private dashboardChartRange: { dateFrom: string; dateTo: string } | null = null;

  async loadDashboard(dateFrom?: string, dateTo?: string) {
    if (dateFrom && dateTo) {
      this.dashboardChartRange = { dateFrom, dateTo };
    }

    const query = this.dashboardChartRange
      ? `?dateFrom=${encodeURIComponent(this.dashboardChartRange.dateFrom)}&dateTo=${encodeURIComponent(this.dashboardChartRange.dateTo)}`
      : '';
    const res = await fetch(`${this.apiUrl}/dashboard/summary${query}`, { headers: this.authHeaders() });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || 'Error obteniendo dashboard');
    }
    this.dashboard.set(data);
    return data;
  }

}
