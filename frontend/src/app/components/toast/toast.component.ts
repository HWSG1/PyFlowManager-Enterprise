import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PyflowService } from '../../services/pyflow.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="fixed bottom-6 right-6 flex flex-col gap-2 z-50">
      @for (toast of svc.toasts(); track toast.id) {
        <div [class]="toastClass(toast.type)"
             class="flex items-center gap-3 px-4 py-3 rounded-xl shadow-xl border text-sm font-medium max-w-sm transition-all animate-in">
          <span class="text-lg">{{ toastIcon(toast.type) }}</span>
          <span>{{ toast.message }}</span>
          <button (click)="svc.removeToast(toast.id)" class="ml-auto opacity-60 hover:opacity-100 text-lg leading-none">×</button>
        </div>
      }
    </div>
  `
})
export class ToastComponent {
  constructor(public svc: PyflowService) {}

  toastClass(type: string): string {
    const map: Record<string, string> = {
      'success': 'bg-emerald-950 border-emerald-800 text-emerald-300',
      'error': 'bg-rose-950 border-rose-800 text-rose-300',
      'warning': 'bg-amber-950 border-amber-800 text-amber-300',
      'info': 'bg-blue-950 border-blue-800 text-blue-300',
    };
    return map[type] ?? map['info'];
  }

  toastIcon(type: string): string {
    const map: Record<string, string> = {
      'success': '✅', 'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'
    };
    return map[type] ?? 'ℹ️';
  }
}
