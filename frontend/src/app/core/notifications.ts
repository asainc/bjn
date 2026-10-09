/** Notificações simples e sem HTML vindo do backend. */
import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';

interface Notice { id: number; message: string; kind: 'error' | 'info'; }

@Injectable({providedIn: 'root'})
export class Notifications {
  readonly items = signal<Notice[]>([]);
  private sequence = 0;

  show(message: string, kind: Notice['kind'] = 'info'): void {
    this.items.update(items => [...items.slice(-3), {id: ++this.sequence, message, kind}]);
  }

  dismiss(id: number): void {
    this.items.update(items => items.filter(item => item.id !== id));
  }

  error(error: unknown): void {
    let message = 'A operação não foi concluída. Tente novamente.';
    if (error instanceof HttpErrorResponse) {
      const payload = error.error as {message?: string; detail?: string} | null;
      if (typeof payload?.message === 'string') message = payload.message;
      else if (typeof payload?.detail === 'string') message = payload.detail;
      else if (error.status === 0) message = 'Não foi possível acessar o backend. Confirme se a API está em execução.';
    } else if (error instanceof Error) {
      message = error.message;
    }
    this.show(message, 'error');
  }
}
