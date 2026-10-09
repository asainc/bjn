/** Workspace do AI Ready para leitura, síntese e consulta de processos cíveis. */
import { CommonModule } from '@angular/common';
import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AiReadyApiService } from '../core/ai-ready-api.service';
import { AiReadyConfiguration, ChatMessage, ProcessWorkspaceResponse, TimelineEvent } from '../core/contracts';
import { Notifications } from '../core/notifications';

type LocalDocument = {
  file: File;
  url: string;
};

type UiChatMessage = ChatMessage;

@Component({
  selector: 'app-ai-ready-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <main class="ai-ready-page">
      <header class="ai-ready-heading">
        <div>
          <span class="eyebrow">AI Ready · Processos cíveis</span>
          <h1>Visão inteligente dos autos</h1>
          <p>Envie documentos em PDF para obter síntese factual e linha do tempo. Use o assistente corporativo para perguntas e respostas.</p>
        </div>
        <div class="connection-pill" [attr.data-status]="connectionState()">
          <span class="connection-dot" aria-hidden="true"></span>
          <div>
            <strong>{{ connectionLabel() }}</strong>
            <small>{{ connectionDetail() }}</small>
          </div>
        </div>
      </header>

      <section class="ai-ready-layout">
        <aside class="document-rail surface">
          <div class="section-heading compact-heading">
            <div>
              <span class="eyebrow">Autos</span>
              <h2>Documentos do processo</h2>
            </div>
            @if (selectedFiles().length) {
              <span class="counter-badge">{{ selectedFiles().length }}</span>
            }
          </div>

          <label class="legal-upload-zone" [class.dragging]="isDragging()">
            <input
              type="file"
              accept="application/pdf,.pdf"
              multiple
              (change)="onFileInput($event)"
              (dragenter)="onDragEnter($event)"
              (dragover)="onDragOver($event)"
              (dragleave)="onDragLeave($event)"
              (drop)="onDrop($event)"
            />
            <span class="upload-symbol" aria-hidden="true">+</span>
            <strong>Adicionar PDFs</strong>
            <span>Arraste os documentos ou clique para selecionar</span>
            <small>Até {{ configuration()?.limite_arquivos ?? 12 }} arquivos · {{ configuration()?.limite_mb_por_arquivo ?? 25 }} MB por arquivo · {{ configuration()?.limite_total_mb ?? 80 }} MB no total</small>
          </label>

          <div class="selected-documents" aria-label="Documentos selecionados">
            @for (item of localDocuments(); track item.file.name + item.file.size) {
              <article class="selected-document">
                <button type="button" class="document-main" (click)="preview(item)">
                  <span class="pdf-badge">PDF</span>
                  <span class="document-copy">
                    <strong>{{ item.file.name }}</strong>
                    <small>{{ formatBytes(item.file.size) }}</small>
                  </span>
                </button>
                <button type="button" class="icon-button" aria-label="Remover documento" (click)="remove(item)">×</button>
              </article>
            }
          </div>

          <button class="primary analyze-button" type="button" [disabled]="!canAnalyze()" (click)="analyze()">
            @if (analyzing()) { Analisando documentos… } @else { Analisar processo }
          </button>

          <p class="privacy-note">O texto extraído fica apenas no workspace temporário do backend e não é persistido pela aplicação.</p>
        </aside>

        <section class="process-area">
          @if (workspace(); as result) {
            <section class="process-summary-grid">
              <article class="surface summary-card summary-card--wide">
                <div class="section-heading">
                  <div>
                    <span class="eyebrow">Resumo do processo</span>
                    <h2>{{ valueOrFallback(result.processo.numero_processo, 'Processo identificado nos autos') }}</h2>
                  </div>
                  <span class="status-chip">{{ valueOrFallback(result.processo.fase_processual, 'Fase não identificada') }}</span>
                </div>
                <p class="summary-text">{{ result.processo.resumo }}</p>
                <div class="case-meta-grid">
                  <div><small>Classe processual</small><strong>{{ valueOrFallback(result.processo.classe_processual) }}</strong></div>
                  <div><small>Assunto principal</small><strong>{{ valueOrFallback(result.processo.assunto_principal) }}</strong></div>
                  <div><small>Tribunal</small><strong>{{ valueOrFallback(result.processo.tribunal) }}</strong></div>
                  <div><small>Unidade judicial</small><strong>{{ valueOrFallback(result.processo.unidade_judicial) }}</strong></div>
                  <div><small>Valor da causa</small><strong>{{ valueOrFallback(result.processo.valor_causa) }}</strong></div>
                  <div><small>Última data relevante</small><strong>{{ valueOrFallback(result.processo.ultima_data_relevante) }}</strong></div>
                </div>
              </article>

              <article class="surface metric-card">
                <small>Documentos</small>
                <strong>{{ result.documentos.length }}</strong>
                <span>{{ totalPages() }} páginas no conjunto</span>
              </article>
              <article class="surface metric-card">
                <small>Fatos na linha do tempo</small>
                <strong>{{ result.linha_tempo.length }}</strong>
                <span>{{ highConfidenceEvents() }} com confiança alta</span>
              </article>
              <article class="surface metric-card">
                <small>Pontos de atenção</small>
                <strong>{{ result.processo.pontos_atencao.length }}</strong>
                <span>Itens para conferência jurídica</span>
              </article>
            </section>

            <section class="process-columns">
              <article class="surface timeline-panel">
                <div class="section-heading">
                  <div>
                    <span class="eyebrow">Cronologia</span>
                    <h2>Linha do tempo dos fatos</h2>
                  </div>
                  <span class="counter-badge">{{ result.linha_tempo.length }}</span>
                </div>
                @if (result.linha_tempo.length) {
                  <div class="timeline-list">
                    @for (event of result.linha_tempo; track event.documento + ':' + event.pagina + ':' + event.titulo) {
                      <article class="timeline-item">
                        <div class="timeline-rail"><span></span></div>
                        <div class="timeline-content">
                          <div class="timeline-topline">
                            <time>{{ event.data ?? 'Data não identificada' }}</time>
                            <span class="event-category">{{ categoryLabel(event.categoria) }}</span>
                          </div>
                          <h3>{{ event.titulo }}</h3>
                          <p>{{ event.descricao }}</p>
                          <div class="source-line">
                            <span>{{ event.documento }}@if (event.pagina) { · p. {{ event.pagina }} }</span>
                            <span class="confidence" [attr.data-confidence]="event.confianca">{{ confidenceLabel(event.confianca) }}</span>
                          </div>
                        </div>
                      </article>
                    }
                  </div>
                } @else {
                  <p class="empty-inline">Nenhum evento temporal suficientemente claro foi identificado nos documentos.</p>
                }
              </article>

              <div class="insight-column">
                <article class="surface insight-panel">
                  <div class="section-heading"><div><span class="eyebrow">Leitura rápida</span><h2>Partes identificadas</h2></div></div>
                  @if (result.processo.partes.length) {
                    <div class="party-list">
                      @for (party of result.processo.partes; track party.nome + party.papel) {
                        <div><strong>{{ party.nome }}</strong><small>{{ party.papel }}</small></div>
                      }
                    </div>
                  } @else { <p class="empty-inline">Não identificadas com segurança.</p> }
                </article>

                <article class="surface insight-panel accent-panel">
                  <div class="section-heading"><div><span class="eyebrow">Conferência</span><h2>Pontos de atenção</h2></div></div>
                  <ul class="clean-list">
                    @for (item of result.processo.pontos_atencao; track item) { <li>{{ item }}</li> }
                    @empty { <li>Nenhum ponto específico foi destacado pela análise.</li> }
                  </ul>
                </article>

                <article class="surface insight-panel">
                  <div class="section-heading"><div><span class="eyebrow">Organização</span><h2>Próximas verificações</h2></div></div>
                  <ul class="clean-list numbered-list">
                    @for (item of result.processo.proximas_acoes_sugeridas; track item; let index = $index) {
                      <li><span>{{ index + 1 }}</span>{{ item }}</li>
                    }
                    @empty { <li><span>1</span>Revise os documentos originais antes de definir a estratégia processual.</li> }
                  </ul>
                </article>
              </div>
            </section>

            <section class="surface details-panel">
              <div class="section-heading">
                <div><span class="eyebrow">Conteúdo extraído</span><h2>Pedidos e fatos controvertidos</h2></div>
              </div>
              <div class="detail-columns">
                <div>
                  <h3>Pedidos identificados</h3>
                  <ul class="clean-list">
                    @for (item of result.processo.pedidos; track item) { <li>{{ item }}</li> }
                    @empty { <li>Nenhum pedido foi identificado com segurança.</li> }
                  </ul>
                </div>
                <div>
                  <h3>Fatos controvertidos</h3>
                  <ul class="clean-list">
                    @for (item of result.processo.fatos_controvertidos; track item) { <li>{{ item }}</li> }
                    @empty { <li>Nenhum fato controvertido foi explicitamente identificado.</li> }
                  </ul>
                </div>
              </div>
              <p class="ai-disclaimer">{{ result.aviso }}</p>
            </section>
          } @else {
            <section class="empty-workspace surface">
              <div class="empty-document-icon" aria-hidden="true"><span></span><span></span><span></span></div>
              <span class="eyebrow">Workspace processual</span>
              <h2>Selecione os documentos para montar a visão do processo</h2>
              <p>O AI Ready organiza fatos, partes, pedidos e movimentações em uma única tela. O chatbot consulta a API corporativa de perguntas e respostas.</p>
              <div class="empty-features">
                <div><strong>01</strong><span>Resumo factual do processo</span></div>
                <div><strong>02</strong><span>Linha do tempo com fonte e página</span></div>
                <div><strong>03</strong><span>Chat corporativo de perguntas e respostas</span></div>
              </div>
            </section>
          }
        </section>
      </section>

      @if (previewDocument(); as previewItem) {
        <div class="preview-backdrop" (click)="closePreview()">
          <section class="preview-panel" role="dialog" aria-modal="true" aria-label="Visualização do PDF" (click)="$event.stopPropagation()">
            <header>
              <div><span class="eyebrow">Documento</span><strong>{{ previewItem.file.name }}</strong></div>
              <button type="button" class="icon-button" aria-label="Fechar PDF" (click)="closePreview()">×</button>
            </header>
            <iframe [src]="safePreviewUrl()" title="Documento PDF selecionado"></iframe>
          </section>
        </div>
      }

      <button
        type="button"
        class="chat-launcher"
        [class.open]="chatOpen()"
        (click)="toggleChat()"
        [attr.aria-expanded]="chatOpen()"
        aria-controls="ai-ready-chat-window"
        aria-label="Abrir assistente AI Ready"
      >
        <span>AI</span>
      </button>

      @if (chatOpen()) {
        <section id="ai-ready-chat-window" class="chat-window" aria-label="Assistente generativo AI Ready">
          <header class="chat-header">
            <div>
              <span class="chat-avatar">AI</span>
              <div><strong>Assistente processual</strong><small>Perguntas e respostas pela API corporativa</small></div>
            </div>
            <button type="button" class="icon-button" aria-label="Fechar chat" (click)="toggleChat()">×</button>
          </header>

          <div class="chat-body">
            @if (!chatMessages().length) {
              <div class="chat-welcome">
                <strong>O que você quer perguntar?</strong>
                <p>A pergunta é enviada ao <code>gpt_bradesco.agente_informacional</code> e a janela apresenta o campo <code>answer</code> retornado pela API corporativa.</p>
                <div class="suggestion-grid">
                  @for (question of suggestedQuestions; track question) {
                    <button type="button" [disabled]="!chatAvailable()" (click)="askSuggestion(question)">{{ question }}</button>
                  }
                </div>
              </div>
            }
            @for (message of chatMessages(); track $index) {
              <article class="chat-message" [class.user-message]="message.role === 'user'">
                <span>{{ message.role === 'user' ? 'Você' : 'AI Ready' }}</span>
                <p>{{ message.content }}</p>
              </article>
            }
            @if (chatLoading()) {
              <article class="chat-message typing-message"><span>AI Ready</span><p>Consultando a API corporativa…</p></article>
            }
          </div>

          <form class="chat-composer" (submit)="sendChat($event)">
            <textarea
              [(ngModel)]="chatDraft"
              name="chatDraft"
              rows="2"
              maxlength="8000"
              [placeholder]="chatAvailable() ? 'Digite sua pergunta para o assistente…' : 'Chat corporativo não configurado'"
              [disabled]="!chatAvailable() || chatLoading()"
              (keydown.enter)="onChatEnter($event)"
            ></textarea>
            <button class="primary" type="submit" [disabled]="!chatAvailable() || !chatDraft.trim() || chatLoading()">Enviar</button>
          </form>
        </section>
      }
    </main>
  `,
})
export class AiReadyPageComponent implements OnDestroy {
  private readonly api = inject(AiReadyApiService);
  private readonly notifications = inject(Notifications);
  private readonly sanitizer = inject(DomSanitizer);

  readonly configuration = signal<AiReadyConfiguration | null>(null);
  readonly connectionState = signal<'checking' | 'online' | 'offline'>('checking');
  readonly localDocuments = signal<LocalDocument[]>([]);
  readonly workspace = signal<ProcessWorkspaceResponse | null>(null);
  readonly analyzing = signal(false);
  readonly isDragging = signal(false);
  readonly previewDocument = signal<LocalDocument | null>(null);
  readonly chatOpen = signal(false);
  readonly chatLoading = signal(false);
  readonly chatMessages = signal<UiChatMessage[]>([]);
  chatDraft = '';

  readonly suggestedQuestions = [
    'Quais são os principais pedidos?',
    'Quais fatos ainda parecem controvertidos?',
    'Quais decisões aparecem nos documentos?',
    'Quais pontos devo conferir antes de elaborar a próxima peça?',
  ];

  readonly selectedFiles = computed(() => this.localDocuments().map(item => item.file));
  readonly canAnalyze = computed(() => this.selectedFiles().length > 0 && !this.analyzing() && Boolean(this.configuration()?.geracao_texto_configurada));
  readonly chatAvailable = computed(() => Boolean(this.configuration()?.chat_qa_configurado));
  readonly totalPages = computed(() => this.workspace()?.documentos.reduce((sum, item) => sum + item.paginas, 0) ?? 0);
  readonly highConfidenceEvents = computed(() => this.workspace()?.linha_tempo.filter(item => item.confianca === 'alta').length ?? 0);
  readonly connectionLabel = computed(() => this.connectionState() === 'online' ? 'IA corporativa disponível' : this.connectionState() === 'checking' ? 'Verificando conexão' : 'IA indisponível');
  readonly connectionDetail = computed(() => {
    if (this.connectionState() === 'checking') return 'Validando backend e configuração';
    if (this.connectionState() === 'offline') return 'Revise a configuração das APIs corporativas';
    const analysis = this.configuration()?.geracao_texto_configurada ? 'análise documental ativa' : 'análise documental indisponível';
    const chat = this.configuration()?.chat_qa_configurado ? 'chat Q&A ativo' : 'chat Q&A indisponível';
    return `${analysis} · ${chat}`;
  });

  constructor() {
    void this.checkConnection();
  }

  ngOnDestroy(): void {
    this.localDocuments().forEach(item => URL.revokeObjectURL(item.url));
    const workspaceId = this.workspace()?.workspace_id;
    if (workspaceId) this.api.discard(workspaceId).subscribe({error: () => undefined});
  }

  async checkConnection(): Promise<void> {
    this.connectionState.set('checking');
    try {
      const [health, configuration] = await Promise.all([
        firstValueFrom(this.api.health()),
        firstValueFrom(this.api.configuration()),
      ]);
      if (health.status !== 'ok' || health.versao_api !== '3.0.0') throw new Error('O frontend e o backend não estão na mesma versão.');
      this.configuration.set(configuration);
      this.connectionState.set(configuration.geracao_texto_configurada || configuration.chat_qa_configurado ? 'online' : 'offline');
    } catch (error) {
      this.connectionState.set('offline');
      this.notifications.error(error);
    }
  }

  onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(Array.from(input.files ?? []));
    input.value = '';
  }

  onDragEnter(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
    this.addFiles(Array.from(event.dataTransfer?.files ?? []));
  }

  private addFiles(files: File[]): void {
    const limit = this.configuration()?.limite_arquivos ?? 12;
    const maxBytes = (this.configuration()?.limite_mb_por_arquivo ?? 25) * 1024 * 1024;
    const maxTotalBytes = (this.configuration()?.limite_total_mb ?? 80) * 1024 * 1024;
    const current = [...this.localDocuments()];
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf') || !['application/pdf', ''].includes(file.type)) {
        this.notifications.show(`${file.name}: envie somente arquivos PDF.`, 'error');
        continue;
      }
      if (file.size > maxBytes) {
        this.notifications.show(`${file.name}: arquivo acima do limite permitido.`, 'error');
        continue;
      }
      if (current.some(item => item.file.name === file.name && item.file.size === file.size)) continue;
      const totalAfterAdd = current.reduce((sum, item) => sum + item.file.size, 0) + file.size;
      if (totalAfterAdd > maxTotalBytes) {
        this.notifications.show(`O conjunto selecionado excede o limite total de ${Math.round(maxTotalBytes / (1024 * 1024))} MB.`, 'error');
        break;
      }
      if (current.length >= limit) {
        this.notifications.show(`O limite atual é de ${limit} arquivos por análise.`, 'error');
        break;
      }
      current.push({file, url: URL.createObjectURL(file)});
    }
    this.localDocuments.set(current);
  }

  remove(item: LocalDocument): void {
    URL.revokeObjectURL(item.url);
    this.localDocuments.update(items => items.filter(candidate => candidate !== item));
    if (this.previewDocument() === item) this.previewDocument.set(null);
  }

  async analyze(): Promise<void> {
    if (!this.canAnalyze()) return;
    this.analyzing.set(true);
    const previousWorkspaceId = this.workspace()?.workspace_id;
    try {
      const result = await firstValueFrom(this.api.analyze(this.selectedFiles()));
      this.workspace.set(result);
      if (previousWorkspaceId && previousWorkspaceId !== result.workspace_id) {
        this.api.discard(previousWorkspaceId).subscribe({error: () => undefined});
      }
      this.notifications.show('Processo analisado. Revise a síntese e as referências nos autos.');
    } catch (error) {
      this.notifications.error(error);
    } finally {
      this.analyzing.set(false);
    }
  }

  preview(item: LocalDocument): void {
    this.previewDocument.set(item);
  }

  closePreview(): void {
    this.previewDocument.set(null);
  }

  safePreviewUrl(): SafeResourceUrl {
    const url = this.previewDocument()?.url ?? 'about:blank';
    // A URL foi criada localmente a partir do File selecionado pelo próprio usuário.
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  }

  toggleChat(): void {
    // O chat é independente do workspace local de PDFs e consulta a API Q&A corporativa.
    this.chatOpen.set(!this.chatOpen());
  }

  askSuggestion(question: string): void {
    this.chatDraft = question;
    void this.submitChat();
  }

  sendChat(event: SubmitEvent): void {
    event.preventDefault();
    void this.submitChat();
  }

  onChatEnter(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.shiftKey) return;
    keyboardEvent.preventDefault();
    void this.submitChat();
  }

  private async submitChat(): Promise<void> {
    const question = this.chatDraft.trim();
    if (!this.chatAvailable() || !question || this.chatLoading()) return;

    const previous = this.chatMessages();
    this.chatMessages.set([...previous, {role: 'user', content: question}]);
    this.chatDraft = '';
    this.chatLoading.set(true);
    try {
      const response = await firstValueFrom(this.api.chat(question));
      this.chatMessages.update(items => [...items, {role: 'assistant', content: response.resposta}]);
    } catch (error) {
      this.notifications.error(error);
      this.chatMessages.update(items => [...items, {role: 'assistant', content: 'Não foi possível consultar a API de perguntas e respostas agora. Verifique a conexão e tente novamente.'}]);
    } finally {
      this.chatLoading.set(false);
    }
  }

  valueOrFallback(value: string | null | undefined, fallback = 'Não identificado'): string {
    return value?.trim() || fallback;
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  categoryLabel(category: TimelineEvent['categoria']): string {
    const labels: Record<TimelineEvent['categoria'], string> = {
      ajuizamento: 'Ajuizamento', citacao: 'Citação', manifestacao: 'Manifestação', prova: 'Prova', audiencia: 'Audiência',
      decisao: 'Decisão', recurso: 'Recurso', cumprimento: 'Cumprimento', outro: 'Outro',
    };
    return labels[category];
  }

  confidenceLabel(confidence: TimelineEvent['confianca']): string {
    return confidence === 'alta' ? 'Confiança alta' : confidence === 'media' ? 'Confiança média' : 'Revisar fonte';
  }
}
