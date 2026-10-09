/** Região acessível de avisos com fechamento individual. */
import { Component, inject } from '@angular/core';
import { Notifications } from '../core/notifications';

@Component({selector:'app-notifications', standalone:true, template:`
  <div class="notices" aria-live="polite">
    @for (notice of notifications.items(); track notice.id) {
      <div class="notice" [class.error]="notice.kind === 'error'" [attr.role]="notice.kind === 'error' ? 'alert' : 'status'">
        <span>{{ notice.message }}</span><button type="button" aria-label="Fechar notificação" (click)="notifications.dismiss(notice.id)">×</button>
      </div>
    }
  </div>`})
export class NotificationsComponent { readonly notifications = inject(Notifications); }
