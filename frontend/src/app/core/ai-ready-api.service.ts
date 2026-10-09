/** Acesso HTTP único às funcionalidades documentais e ao chat do AI Ready. */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { ApiConfiguration } from './config';
import { AiReadyConfiguration, ChatResponse, Health, ProcessWorkspaceResponse } from './contracts';

@Injectable({providedIn: 'root'})
export class AiReadyApiService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  health() {
    return this.http.get<Health>(`${this.config.baseUrl}/saude`);
  }

  configuration() {
    return this.http.get<AiReadyConfiguration>(`${this.config.baseUrl}/ai-ready/configuracao`);
  }

  analyze(files: File[]) {
    const data = new FormData();
    files.forEach(file => data.append('files', file, file.name));
    return this.http.post<ProcessWorkspaceResponse>(`${this.config.baseUrl}/ai-ready/analisar`, data);
  }

  chat(pergunta: string) {
    return this.http.post<ChatResponse>(`${this.config.baseUrl}/ai-ready/chat`, {pergunta});
  }

  discard(workspaceId: string) {
    return this.http.delete<void>(`${this.config.baseUrl}/ai-ready/${encodeURIComponent(workspaceId)}`);
  }
}
