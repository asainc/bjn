/** Configuração lida antes de iniciar Angular, sem recompilar por ambiente. */
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

interface RuntimeConfiguration {apiBaseUrl: string; pollIntervalMs: number;}

@Injectable({providedIn: 'root'})
export class ApiConfiguration {
  private readonly http = inject(HttpClient);
  private configuration: RuntimeConfiguration | null = null;

  /** Um erro impede inicialização com um endpoint presumido. */
  async load(): Promise<void> {
    const value = await firstValueFrom(this.http.get<RuntimeConfiguration>('app-config.json'));
    const url = new URL(value.apiBaseUrl, window.location.origin);
    if (!['http:', 'https:'].includes(url.protocol) || !Number.isInteger(value.pollIntervalMs) || value.pollIntervalMs < 500) {
      throw new Error('Configuração da aplicação inválida.');
    }
    this.configuration = {...value, apiBaseUrl: value.apiBaseUrl.replace(/\/$/, '')};
  }

  get baseUrl(): string { if (!this.configuration) throw new Error('Configuração indisponível.'); return this.configuration.apiBaseUrl; }
  get pollInterval(): number { return this.configuration?.pollIntervalMs ?? 1500; }
}
