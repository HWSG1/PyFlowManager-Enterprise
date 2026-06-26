import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HeaderComponent } from './components/header/header.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { ScriptsComponent } from './components/scripts/scripts.component';
import { ScriptDetailComponent } from './components/script-detail/script-detail.component';
import { SchedulesComponent } from './components/schedules/schedules.component';
import { LogsComponent } from './components/logs/logs.component';
import { SettingsComponent } from './components/settings/settings.component';
import { ImportModalComponent } from './components/import-modal/import-modal.component';
import { ToastComponent } from './components/toast/toast.component';
import { LoginComponent } from './components/login/login.component';
import { UsersComponent } from './components/users/users.component';
import { ChangePasswordComponent } from './components/change-password/change-password.component';
import { AuthService } from './services/auth.service';
import { PyflowService } from './services/pyflow.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    HeaderComponent,
    SidebarComponent,
    DashboardComponent,
    ScriptsComponent,
    ScriptDetailComponent,
    SchedulesComponent,
    LogsComponent,
    SettingsComponent,
    ImportModalComponent,
    ToastComponent,
    LoginComponent,
    UsersComponent,
    ChangePasswordComponent
  ],
  template: `
    @if (!auth.isAuthenticated()) {
      <app-login />
    } @else {
    <div class="bg-app text-app h-screen flex flex-col overflow-hidden">
      <app-header />

      <div class="flex flex-1 min-h-0 overflow-hidden">
        <app-sidebar />

        <main class="flex-1 min-h-0 overflow-y-auto p-6 custom-scrollbar bg-slate-900/50">
          @switch (svc.activeTab()) {
            @case ('dashboard') { <app-dashboard /> }
            @case ('scripts') { <app-scripts /> }
            @case ('script-detail') { <app-script-detail /> }
            @case ('schedules') { <app-schedules /> }
            @case ('logs') { <app-logs /> }
            @case ('settings') { <app-settings /> }
            @case ('users') { <app-users /> }
          }
        </main>
      </div>

      <app-import-modal />
      <app-change-password />
      <app-toast />
    </div>
    }
  `
})
export class AppComponent {
  constructor(public svc: PyflowService, public auth: AuthService) {}
}
