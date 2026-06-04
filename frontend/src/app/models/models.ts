export interface Script {
  id: number;
  name: string;
  category: string;
  path: string;
  status: 'active' | 'inactive';
  lastRun: string;
  nextRun: string;
  lastStatus: 'Exitoso' | 'Error' | 'Ejecutando' | 'Cancelado' | 'Nunca';
  description: string;
  author: string;
  version: string;
  successCount: number;
  errorCount: number;
  avgDuration: string;
}

export interface Execution {
  id: string;
  script: string;
  status: 'Exitoso' | 'Error' | 'Cancelado' | 'Ejecutando';
  start: string;
  end: string;
  duration: string;
  user: string;
  message: string;
}

export interface Schedule {
  id: number;
  scriptId: number;
  scriptName: string;
  frequency: string;
  cronExpression: string;
  nextRun: string;
  status: 'active' | 'paused';
}

export interface EnvParam {
  id?: number;
  key: string;
  value: string;
  isSecret?: boolean;
  description?: string;
}

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

export type TabName =
  | 'dashboard'
  | 'scripts'
  | 'script-detail'
  | 'schedules'
  | 'logs'
  | 'settings'
  | 'users';
