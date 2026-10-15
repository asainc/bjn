/** Acompanhamento da demanda com evidências incorporadas e timeline de alterações. */
import {CommonModule} from '@angular/common';
import {Component,inject,OnDestroy,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DomSanitizer,SafeResourceUrl} from '@angular/platform-browser';
import {ActivatedRoute,RouterLink} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {BjnDemandApiService,DemandConfiguration,DemandDetail,DemandDocument,DemandStatus} from '../../core/bjn-demand-api.service';
import {demandStatusLabels,friendlyApiError,readableDate,readableSize,selectableStatuses} from './demand-ui';

@Component({selector:'app-bjn-demand-detail',standalone:true,imports:[CommonModule,FormsModule,RouterLink],styleUrl:'./demands.scss',template:`
<main class="demand-shell demand-detail-shell">
  <nav class="demand-crumb" aria-label="Navegação"><a routerLink="/bjn/demandas">Demandas</a><span>/</span><strong>{{record()?.id || 'Acompanhamento'}}</strong></nav>
  @if(busy() && !record()){<div class="surface demand-card">Carregando demanda...</div>}
  @else if(error() && !record()){<div class="surface demand-card"><p class="demand-error" role="alert">{{error()}}</p><a routerLink="/bjn/demandas" class="demand-outlined">Voltar às demandas</a></div>}
  @else if (record(); as demand){
    <header class="demand-heading demand-detail-heading"><div><span class="eyebrow">BJN · ACOMPANHAMENTO</span><div class="demand-title-row"><h1>{{demand.title}}</h1><span class="demand-pill" [attr.data-status]="demand.status">{{labels[demand.status]}}</span></div>
      <p>Demanda {{demand.id}} · Aberta em {{date(demand.created_at)}}</p></div>
      <a routerLink="/bjn/demandas" class="demand-outlined">Todas as demandas</a>
    </header>
    @if(api.isDemoReviewerActive || (configuration()?.demo_session_available && demand.lawyer_email && !demand.opinion?.published_at)){
      <div class="surface demand-demo-review" role="region" aria-label="Simulação de perfil jurídico">
        <div><strong>Simulação local de aprovação jurídica</strong><p>Perfil atual: {{configuration()?.actor?.role==='advogado'?'advogado fictício':'administrador'}}. A publicação é restrita ao advogado designado.</p></div>
        @if(api.isDemoReviewerActive){
          <button type="button" class="demand-outlined" (click)="stopDemoReviewer()">Voltar ao administrador</button>
        } @else if(canSwitchToDemoReviewer(demand.lawyer_email)) {
          <button type="button" class="demand-outlined" (click)="startDemoReviewer(demand.lawyer_email)">Testar como advogado designado</button>
        }
      </div>
    }
    <div class="demand-metrics">
      <div class="surface demand-metric"><span>Status atual</span><strong>{{labels[demand.status]}}</strong><small>Atualizado em {{date(demand.updated_at)}}</small></div>
      <div class="surface demand-metric"><span>Advogado responsável</span><strong>{{demand.lawyer_email || 'Aguardando distribuição'}}</strong><small>{{demand.lawyer_email ? 'Responsável atribuído' : 'Ainda não distribuída'}}</small></div>
      <div class="surface demand-metric"><span>Solicitante</span><strong>{{demand.requester_name}}</strong><small>{{demand.legal_department}}</small></div>
      <div class="surface demand-metric"><span>Documentos</span><strong>{{demand.documents.length}}</strong><small>Anexos e documentos enviados</small></div>
    </div>
    @if(error()){<p class="demand-error" role="alert">{{error()}}</p>}
    <ol class="bjn-journey-steps" aria-label="Etapas de atendimento">
      @for(step of journeySteps;track $index;let index=$index){<li [class.active]="index===currentStage(demand.status)" [attr.aria-current]="index===currentStage(demand.status)?'step':null"><span>{{index+1}}</span>{{step}}</li>}
    </ol>
    <div class="demand-detail-layout">
      <div class="demand-detail-main">
        <section class="surface demand-card" aria-labelledby="detail-resumo"><div class="demand-card-heading"><h2 id="detail-resumo">Resumo da solicitação</h2><span class="demand-subtle">Informações do cadastro</span></div>
          <div class="demand-facts"><div><span>Área de consulta</span><strong>{{demand.consult_area}}</strong></div><div><span>Natureza do serviço</span><strong>{{demand.service_nature}}</strong></div><div><span>Departamento jurídico</span><strong>{{demand.legal_department}}</strong></div></div>
          <div class="demand-description"><h3>Descrição da consulta</h3><p>{{demand.description}}</p></div>
        </section>
        @if(demand.registration;as registration){
          <section class="surface demand-card" aria-labelledby="registration-summary"><div class="demand-card-heading"><h2 id="registration-summary">Dados do cadastro</h2></div>
            <div class="demand-facts"><div><span>Agência</span><strong>{{registration.branch}}</strong></div><div><span>E-mail do solicitante</span><strong>{{registration.requester_email}}</strong></div><div><span>Cliente</span><strong>{{registration.client_name}}</strong></div><div><span>CPF</span><strong>{{registration.document_mask}}</strong></div></div>
          </section>
        }
        @if(demand.opinion?.published_at){
          <section class="surface demand-card bjn-final-opinion" aria-labelledby="final-opinion"><span class="eyebrow">RETORNO PUBLICADO</span><h2 id="final-opinion">Parecer jurídico disponível</h2>
            <p class="demand-muted">Publicado em {{date(demand.opinion!.published_at!)}} por {{demand.opinion!.reviewer_id}}.</p>
            <div class="bjn-opinion-text">{{demand.opinion!.final_text}}</div>
            @if(demand.notification_dispatch;as dispatch){<p class="demand-muted" role="status">{{dispatch.status==='ENVIADO'?'Notificação enviada por e-mail.':dispatch.status==='SEM_EMAIL_CADASTRADO'?'Parecer publicado. Cadastro anterior sem e-mail de notificação; retorno disponível no portal.':'Parecer publicado. A notificação por e-mail permanece pendente de configuração ou reenvio.'}}</p>}
          </section>
        } @else {<section class="surface demand-card bjn-final-opinion"><h2>Parecer jurídico</h2><p class="demand-muted">Ainda não publicado. Você poderá consultá-lo aqui após validação e finalização pelo advogado responsável.</p></section>}
        @if(demand.lawyer_email && !demand.can_review_opinion && !demand.opinion?.published_at){
          <p class="demand-muted" role="status">O parecer somente pode ser publicado pelo advogado designado ({{demand.lawyer_email}}), com a sessão desse profissional. Um administrador pode distribuir, mas não publicar em nome dele.</p>
        }
        @if(demand.can_review_opinion){
          <section class="surface demand-card bjn-opinion-editor" aria-labelledby="opinion-editor-title"><span class="eyebrow">EXCLUSIVO DO ADVOGADO RESPONSÁVEL</span><h2 id="opinion-editor-title">Elaboração e validação do parecer</h2>
            <p>A IA pode sugerir um rascunho, mas somente você pode revisar, ajustar e publicar o parecer.</p>
            <button type="button" class="demand-outlined" (click)="generateDraft()" [disabled]="generatingOpinion() || !configuration()?.opinion_ai_available">{{generatingOpinion()?'Preparando rascunho...':'Preparar rascunho com text_generator'}}</button>
            @if(!configuration()?.opinion_ai_available){<p class="demand-muted">IA indisponível. O parecer ainda pode ser escrito manualmente.</p>}
            <div class="demand-field"><label for="opinion-text">Texto final do parecer <span class="required">*</span></label><textarea id="opinion-text" class="bjn-opinion-input" rows="12" maxlength="18000" [(ngModel)]="finalOpinion" placeholder="Revise a proposta de IA ou redija o parecer completo"></textarea></div>
            <label class="bjn-confirm"><input type="checkbox" [(ngModel)]="humanReviewed"/> Li e revisei integralmente o parecer; assumo sua publicação como advogado responsável.</label>
            @if(opinionError()){<p class="demand-error" role="alert">{{opinionError()}}</p>}
            @if(finalOpinion.trim().length<40){<p class="demand-muted" role="status">Informe ao menos 40 caracteres no parecer para habilitar a publicação.</p>}
            @if(!humanReviewed){<p class="demand-muted">Marque a confirmação de revisão humana antes de publicar.</p>}
            <button type="button" class="primary" [disabled]="publishingOpinion()||finalOpinion.trim().length<40||!humanReviewed" (click)="publishOpinion()">{{publishingOpinion()?'Publicando...':'Publicar parecer e disponibilizar retorno'}}</button>
            <p class="demand-muted">Após a publicação, a demanda será concluída e o sistema tentará notificar o solicitante por e-mail, se estiver configurado.</p>
          </section>
        }
        <section class="surface demand-card demand-ai-detail" aria-labelledby="detail-ai-title">
          <div class="demand-card-heading"><div><span class="eyebrow">ASSISTENTE BJN</span><h2 id="detail-ai-title">Sugestão da IA</h2><p>Orientação baseada exclusivamente na descrição cadastrada, sem consultar os anexos.</p></div></div>
          @if(demand.ai_guidance;as guidance){
            <div class="demand-ai-result" aria-live="polite"><strong>{{guidance.encaminhamento==='POSSIVEL_AUTOATENDIMENTO'?'Possível autoatendimento':'Avaliação humana recomendada'}}</strong>
              <h3>{{guidance.resumo}}</h3><p>{{guidance.orientacao}}</p>
              @if(guidance.passos_sugeridos.length){<ol>@for(step of guidance.passos_sugeridos;track $index){<li>{{step}}</li>}</ol>}
              <small>Conteúdo gerado por IA; não substitui parecer ou aprovação jurídica.</small>
            </div>
            @if(demand.can_resolve_ai){
              @if(!confirmAIResolution()){
                <button type="button" class="demand-outlined" [disabled]="sending()" (click)="confirmAIResolution.set(true)">Esta orientação resolveu minha dúvida</button>
              } @else {
                <div class="demand-ai-confirm"><p>Confirma que sua dúvida foi resolvida sem atendimento jurídico? A demanda será encerrada como autoatendimento e não poderá ser distribuída.</p>
                  <button type="button" class="primary" [disabled]="sending()" (click)="resolveAI()">{{sending()?'Confirmando...':'Confirmar autoatendimento'}}</button>
                  <button type="button" class="demand-outlined" (click)="confirmAIResolution.set(false)">Voltar</button>
                </div>
              }
            }
          } @else {<p class="demand-muted">Ainda não foi solicitada análise para esta demanda.</p>}
          @if(demand.status!=='RESOLVIDA_IA'){
            <button type="button" class="demand-outlined" [disabled]="analyzing() || !configuration()?.ai_available || sending()" (click)="analyzeDemand()">{{analyzing()?'Analisando...':(demand.ai_guidance?'Atualizar sugestão':'Gerar sugestão com IA')}}</button>
          }
          @if(!configuration()?.ai_available){<p class="demand-muted">Serviço corporativo text_generator não configurado.</p>}
          @if(aiError()){<p class="demand-error" role="alert">{{aiError()}}</p>}
        </section>
        @if(demand.involved.length){<section class="surface demand-card" aria-labelledby="detail-env"><div class="demand-card-heading"><h2 id="detail-env">Envolvidos</h2><span class="demand-subtle">{{demand.involved.length}} registro(s)</span></div>
          <div class="demand-table-scroll"><table class="demand-table"><thead><tr><th>Tipo</th><th>Nome / razão social</th><th>Documento</th><th>Período</th></tr></thead><tbody>
            @for(person of demand.involved;track $index){<tr><td>{{person.type}}</td><td>{{person.name}}</td><td>{{person.document || '—'}}</td><td>{{person.period || '—'}}</td></tr>}
          </tbody></table></div></section>}
        <section class="surface demand-card" aria-labelledby="detail-timeline"><div class="demand-card-heading"><h2 id="detail-timeline">Histórico de acompanhamento</h2><span class="demand-subtle">Linha do tempo</span></div>
          <ol class="demand-timeline">@for(event of demand.events;track $index){<li><span class="demand-timeline-dot" aria-hidden="true"></span><div><strong>{{event.description}}</strong><small>{{date(event.created_at)}} · {{event.actor_id}}</small></div></li>}</ol>
        </section>
      </div>
      <aside class="demand-detail-side">
        <section class="surface demand-documents" aria-labelledby="detail-documents">
          <div class="demand-card-heading demand-document-heading"><div><h2 id="detail-documents">Central de documentos</h2><p>Visualize anexos sem sair da demanda.</p></div>
            <div class="demand-document-actions"><span class="demand-doc-count">{{demand.documents.length}}</span><button type="button" class="demand-outlined demand-toggle-docs" [attr.aria-expanded]="documentsExpanded()" aria-controls="bjn-document-panel" (click)="toggleDocuments()">{{documentsExpanded()?'− Minimizar':'+ Expandir'}}</button></div>
          </div>
          @if(documentsExpanded()){
          <div id="bjn-document-panel">
          <div class="demand-document-tabs" role="group" aria-label="Filtrar documentos">
            <button type="button" [class.active]="documentTab()==='ALL'" (click)="changeDocumentTab('ALL')">Todos</button>
            <button type="button" [class.active]="documentTab()==='ANEXO'" (click)="changeDocumentTab('ANEXO')">Anexos</button>
            <button type="button" [class.active]="documentTab()==='DOCUMENTO_ENVIADO'" (click)="changeDocumentTab('DOCUMENTO_ENVIADO')">Enviados</button>
          </div>
          @if(visibleDocuments().length){<div class="demand-document-list" aria-label="Documentos disponíveis">
            @for(doc of visibleDocuments();track doc.id){<button type="button" [class.active]="selected()?.id===doc.id" (click)="preview(doc)">
              <span class="demand-file-square">{{doc.media_type==='application/pdf'?'PDF':'IMG'}}</span>
              <span class="demand-document-name"><strong>{{doc.original_name}}</strong><small>{{size(doc.file_size)}} · {{doc.category==='ANEXO'?'Anexo':'Documento enviado'}}</small></span>
              <span class="demand-document-chevron">›</span></button>}
          </div>} @else{<p class="demand-muted">Nenhum documento nesta categoria.</p>}
          <div class="demand-viewer" aria-label="Visualização do documento selecionado">
            @if(viewing()){<p class="demand-viewer-placeholder">Carregando documento...</p>}
            @else if(viewError()){<div class="demand-viewer-placeholder" role="alert">{{viewError()}}</div>}
            @else if(selected() && previewUrl()){
              <div class="demand-viewer-header"><strong>{{selected()!.original_name}}</strong><button type="button" (click)="downloadSelected()">Baixar</button></div>
              @if(selected()!.media_type==='application/pdf'){
                <iframe title="Visualizador de PDF da demanda" [src]="trustedPreviewUrl()" class="demand-pdf-frame"></iframe>
              } @else {
                <div class="demand-image-area"><img [src]="previewUrl()" [alt]="'Documento '+selected()!.original_name" /></div>
              }
            } @else {<div class="demand-viewer-placeholder">Selecione um documento acima para visualizar aqui.</div>}
          </div>
          <div class="demand-send-documents"><h3>Enviar mais documentos</h3>
            <label for="detail-upload" class="demand-outlined">Selecionar arquivos
              <input id="detail-upload" type="file" class="demand-file-input" multiple accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" (change)="selectAttachments($event)" />
            </label>
            @if(pendingFiles().length){<p>{{pendingFiles().length}} arquivo(s) selecionado(s)</p><button class="primary" type="button" [disabled]="sending()" (click)="sendAttachments()">{{sending()?'Enviando...':'Enviar documentos'}}</button>}
          </div>
          </div>
          } @else {<p class="demand-muted demand-doc-collapsed">Documentos recolhidos. Selecione “Expandir” para voltar a visualizar e anexar arquivos.</p>}
        </section>
        @if(demand.can_review_competence){
          <section class="surface demand-card bjn-competence" aria-labelledby="competence-heading"><span class="eyebrow">TRIAGEM ADMINISTRATIVA</span><h2 id="competence-heading">Competência da equipe</h2>
            <p>A demanda de “Pareceres em geral” precisa ser analisada antes da distribuição.</p>
            <div class="demand-field"><label for="competence-select">Esta demanda é de competência da equipe?</label><select id="competence-select" [(ngModel)]="competenceChoice"><option value="">Selecione</option><option value="SIM">Sim, pertence à equipe</option><option value="NAO">Não, encaminhar à outra área</option></select></div>
            @if(competenceChoice==='NAO'){<div class="demand-field"><label for="destination-area">Área competente</label><input id="destination-area" maxlength="120" [(ngModel)]="destinationArea" placeholder="Informe a área de destino"/></div>}
            <button type="button" class="primary" [disabled]="sending()||!competenceChoice||(competenceChoice==='NAO'&&destinationArea.trim().length<3)" (click)="confirmCompetence()">Confirmar triagem</button>
            <p class="demand-muted">Encaminhamento externo é registrado para atuação humana; não envia documentos automaticamente.</p>
          </section>
        }
        @if(demand.can_assign || demand.can_manage){<section class="surface demand-card demand-management" aria-labelledby="manage-title"><h2 id="manage-title">Gestão da demanda</h2><p>Alterações ficam registradas no histórico.</p>
          @if(demand.can_assign){<label for="assign-lawyer">Distribuir para advogado</label>
            <select id="assign-lawyer" [(ngModel)]="selectedLawyer"><option value="">Selecione um advogado autorizado</option>@for(lawyer of configuration()?.lawyer_options || [];track lawyer.email){<option [value]="lawyer.email">{{lawyer.name}}{{lawyer.demo?' (teste)':''}} — {{lawyer.email}}</option>}</select>
            <button type="button" [disabled]="sending() || !selectedLawyer" (click)="assign()">Atribuir responsável</button>
            @if(!configuration()?.allowed_lawyers?.length){<small>Configure BJN_ALLOWED_LAWYERS no backend para habilitar distribuição.</small>}
          }
          @if(demand.can_manage){<label for="new-status">Atualizar status</label><select id="new-status" [(ngModel)]="newStatus"><option value="">Selecione o novo status</option>
            @for(s of availableTransitions(demand.status);track s){<option [value]="s">{{labels[s]}}</option>}
          </select><label for="status-note">Observação (opcional)</label><textarea id="status-note" class="demand-management-note" [(ngModel)]="statusNote" maxlength="300" rows="2" placeholder="Descreva brevemente a atualização"></textarea><button type="button" [disabled]="sending() || !newStatus" (click)="updateStatus()">Atualizar andamento</button>}
        </section>}
      </aside>
    </div>
  }
</main>`})
export class BjnDemandDetailComponent implements OnInit,OnDestroy {
  readonly api=inject(BjnDemandApiService);
  private readonly route=inject(ActivatedRoute);
  private readonly sanitizer=inject(DomSanitizer);
  readonly record=signal<DemandDetail|null>(null);
  readonly configuration=signal<DemandConfiguration|null>(null);
  readonly busy=signal(true);readonly sending=signal(false);readonly error=signal('');
  readonly viewing=signal(false);readonly viewError=signal('');
  readonly documentTab=signal<'ALL'|'ANEXO'|'DOCUMENTO_ENVIADO'>('ALL');
  readonly selected=signal<DemandDocument|null>(null);
  readonly previewUrl=signal('');readonly trustedPreviewUrl=signal<SafeResourceUrl|null>(null);
  readonly pendingFiles=signal<File[]>([]);
  readonly documentsExpanded=signal(true);
  readonly analyzing=signal(false);
  readonly aiError=signal('');
  readonly confirmAIResolution=signal(false);
  readonly labels=demandStatusLabels;readonly date=readableDate;readonly size=readableSize;
  readonly journeySteps=['Triagem','Cadastro','Distribuição','Parecer','Consulta'];
  readonly generatingOpinion=signal(false);readonly publishingOpinion=signal(false);readonly opinionError=signal('');
  finalOpinion='';humanReviewed=false;competenceChoice='';destinationArea='';
  currentStage(status:DemandStatus):number {
    if(status==='CONCLUIDA'||status==='RESOLVIDA_IA'||status==='ENCAMINHADA_AREA')return 4;
    if(status==='PARECER_EM_REVISAO'||status==='EM_ANALISE'||status==='AGUARDANDO_INFORMACOES')return 3;
    if(status==='RECEBIDA'||status==='EM_TRIAGEM'||status==='TRIAGEM_ADMINISTRATIVA')return 2;
    return 1;
  }
  selectedLawyer='';newStatus='';statusNote='';
  private disposed=false;
  private previewGeneration=0;
  private get demandId():string{return this.route.snapshot.paramMap.get('id') || '';}
  // A troca existe exclusivamente para verificar o fluxo com perfis sintéticos locais.
  canSwitchToDemoReviewer(email:string|null):boolean {
    return !!email && !!this.configuration()?.demo_session_available &&
      !!this.configuration()?.lawyer_options.some(option=>option.demo && option.email===email);
  }
  startDemoReviewer(email:string|null):void {
    if(!email || !this.configuration() || !this.api.enableDemoReviewer(email,this.configuration()!))return;
    this.resetForActorChange();void this.load();
  }
  stopDemoReviewer():void {
    this.api.disableDemoReviewer();this.resetForActorChange();void this.load();
  }
  private resetForActorChange():void {
    // Descartar documentos e rascunhos anteriores impede vazamento entre perfis.
    this.previewGeneration++;this.cleanupPreview();this.selected.set(null);
    this.record.set(null);this.configuration.set(null);this.finalOpinion='';this.humanReviewed=false;
    this.opinionError.set('');this.error.set('');
  }
  ngOnInit():void {void this.load();}
  ngOnDestroy():void {this.disposed=true;this.previewGeneration++;this.cleanupPreview();}
  private cleanupPreview():void {if(this.previewUrl())URL.revokeObjectURL(this.previewUrl());this.previewUrl.set('');this.trustedPreviewUrl.set(null);}
  async load():Promise<void>{
    this.busy.set(true);this.error.set('');
    try{const [demand,config]=await Promise.all([firstValueFrom(this.api.detail(this.demandId)),firstValueFrom(this.api.configuration())]);
      if(this.disposed)return;
      this.record.set(demand);this.configuration.set(config);
      if(demand.can_review_opinion)this.finalOpinion=demand.opinion?.draft_text||demand.opinion?.final_text||'';
      if(!this.selected() && demand.documents.length)void this.preview(demand.documents[0]);
    }catch(error){if(!this.disposed)this.error.set(friendlyApiError(error));}
    finally{this.busy.set(false);}
  }
  /** Recolher descarrega a prévia em memória, mas preserva a seleção do documento. */
  toggleDocuments():void {
    const opening = !this.documentsExpanded();
    this.documentsExpanded.set(opening);
    if (!opening) {
      this.previewGeneration++;
      this.viewing.set(false);
      this.cleanupPreview();
    } else if (this.selected()) {
      void this.preview(this.selected()!);
    }
  }
  visibleDocuments():DemandDocument[]{return this.record()?.documents.filter(doc=>this.documentTab()==='ALL' || doc.category===this.documentTab()) || [];}
  changeDocumentTab(tab:'ALL'|'ANEXO'|'DOCUMENTO_ENVIADO'):void {
    // Mantém prévia coerente com o filtro selecionado, sem exibir arquivo de outra categoria.
    this.documentTab.set(tab);
    const first=this.visibleDocuments()[0];
    if(first && !this.visibleDocuments().some(doc=>doc.id===this.selected()?.id))void this.preview(first);
    if(!first){this.previewGeneration++;this.selected.set(null);this.cleanupPreview();}
  }
  async preview(document:DemandDocument):Promise<void>{
    this.previewGeneration++;const generation=this.previewGeneration;
    this.selected.set(document);this.cleanupPreview();this.viewing.set(true);this.viewError.set('');
    try{const file=await firstValueFrom(this.api.document(this.demandId,document.id));
      if(this.disposed || generation!==this.previewGeneration)return;
      if(file.type!==document.media_type)throw new Error('Formato de arquivo incompatível.');
      const url=URL.createObjectURL(file);this.previewUrl.set(url);
      // Somente blob retornado de uma rota autenticada pode ser usado como recurso embutido.
      this.trustedPreviewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    }catch{if(!this.disposed && generation===this.previewGeneration)this.viewError.set('Documento indisponível para visualização. Verifique a permissão ou tente novamente.');}
    finally{if(!this.disposed && generation===this.previewGeneration)this.viewing.set(false);}
  }
  downloadSelected():void {
    const document=this.selected(),url=this.previewUrl();if(!document||!url)return;
    const anchor=window.document.createElement('a');anchor.href=url;anchor.download=document.original_name;
    window.document.body.appendChild(anchor);anchor.click();anchor.remove();
  }
  selectAttachments(event:Event):void {
    const input=event.target as HTMLInputElement;
    const files=Array.from(input.files||[]);input.value='';
    if(files.some(file=>file.size>15*1024*1024 || !['application/pdf','image/png','image/jpeg'].includes(file.type))){this.error.set('Utilize PDF, PNG ou JPEG de até 15 MB.');return;}
    if(files.length+(this.record()?.documents.length||0)>20){this.error.set('Limite de 20 arquivos por demanda.');return;}
    this.error.set('');this.pendingFiles.set(files);
  }
  async sendAttachments():Promise<void>{
    if(this.sending()||!this.pendingFiles().length)return;this.sending.set(true);this.error.set('');
    try{const updated=await firstValueFrom(this.api.attach(this.demandId,this.pendingFiles()));this.record.set(updated);this.pendingFiles.set([]);
      this.documentTab.set('ALL');
      const recent=updated.documents.at(-1);
      if(recent)void this.preview(recent);}
    catch(error){this.error.set(friendlyApiError(error));}finally{this.sending.set(false);}
  }
  /** Solicitação explícita para text_generator, registrada no histórico da demanda. */
  async analyzeDemand():Promise<void>{
    if(this.analyzing() || !this.record())return;
    this.analyzing.set(true);this.aiError.set('');this.confirmAIResolution.set(false);
    try {this.record.set(await firstValueFrom(this.api.analyzeDemand(this.demandId)));}
    catch(cause){this.aiError.set(friendlyApiError(cause));}
    finally {this.analyzing.set(false);}
  }
  /** Usuário confirma que não precisa de distribuição; o backend revalida as regras. */
  async resolveAI():Promise<void>{
    if(!this.confirmAIResolution() || this.sending())return;
    this.sending.set(true);this.aiError.set('');
    try{this.record.set(await firstValueFrom(this.api.resolveByAI(this.demandId)));this.confirmAIResolution.set(false);}
    catch(cause){this.aiError.set(friendlyApiError(cause));}
    finally{this.sending.set(false);}
  }
  async confirmCompetence():Promise<void>{
    if(!this.competenceChoice||this.sending())return;
    this.sending.set(true);this.error.set('');
    try{this.record.set(await firstValueFrom(this.api.reviewCompetence(this.demandId,this.competenceChoice==='SIM',this.destinationArea)));this.competenceChoice='';this.destinationArea='';}
    catch(cause){this.error.set(friendlyApiError(cause));}finally{this.sending.set(false);}
  }
  async generateDraft():Promise<void>{
    if(this.generatingOpinion())return;this.generatingOpinion.set(true);this.opinionError.set('');
    try{const updated=await firstValueFrom(this.api.generateOpinionDraft(this.demandId));this.record.set(updated);this.finalOpinion=updated.opinion?.draft_text||'';this.humanReviewed=false;}
    catch(cause){this.opinionError.set(friendlyApiError(cause));}finally{this.generatingOpinion.set(false);}
  }
  async publishOpinion():Promise<void>{
    if(this.publishingOpinion()||!this.humanReviewed||this.finalOpinion.trim().length<40)return;
    this.publishingOpinion.set(true);this.opinionError.set('');
    try{this.record.set(await firstValueFrom(this.api.publishOpinion(this.demandId,this.finalOpinion,true)));this.humanReviewed=false;}
    catch(cause){this.opinionError.set(friendlyApiError(cause));}finally{this.publishingOpinion.set(false);}
  }
  async assign():Promise<void>{if(!this.selectedLawyer||this.sending())return;this.sending.set(true);this.error.set('');
    try{this.record.set(await firstValueFrom(this.api.assign(this.demandId,this.selectedLawyer)));this.selectedLawyer='';}
    catch(error){this.error.set(friendlyApiError(error));}finally{this.sending.set(false);}
  }
  availableTransitions(status:DemandStatus):DemandStatus[]{
    const map:Record<DemandStatus,DemandStatus[]>={
      RECEBIDA:['EM_TRIAGEM','CANCELADA'],EM_TRIAGEM:['EM_ANALISE','AGUARDANDO_INFORMACOES','CANCELADA'],
      TRIAGEM_ADMINISTRATIVA:['CANCELADA'],ENCAMINHADA_AREA:[],PARECER_EM_REVISAO:['AGUARDANDO_INFORMACOES','CANCELADA'],
      EM_ANALISE:['AGUARDANDO_INFORMACOES','CONCLUIDA','CANCELADA'],
      AGUARDANDO_INFORMACOES:['EM_ANALISE','CANCELADA'],CONCLUIDA:[],CANCELADA:[],RESOLVIDA_IA:[],
    };return map[status];
  }
  async updateStatus():Promise<void>{if(!this.newStatus||this.sending())return;this.sending.set(true);this.error.set('');
    try{this.record.set(await firstValueFrom(this.api.changeStatus(this.demandId,this.newStatus as DemandStatus,this.statusNote)));this.newStatus='';this.statusNote='';}
    catch(error){this.error.set(friendlyApiError(error));}finally{this.sending.set(false);}
  }
}
