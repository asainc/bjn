/** Cadastro assistido de demanda: clareza de campos, envio atômico e validação. */
import {CommonModule} from '@angular/common';
import {Component, inject, OnInit, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {Router, RouterLink} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {BjnDemandApiService, DemandConfiguration, DemandInput, InvolvedPerson, DemandGuidance, DocumentAISuggestion, TriageCategory, TriageDecision} from '../../core/bjn-demand-api.service';
import {friendlyApiError,readableSize} from './demand-ui';

/** Identifica o campo com problema para orientar a correção sem expor dados do usuário. */
type ValidationIssue = {fieldId:string; message:string};

@Component({
  selector:'app-bjn-demand-new',standalone:true,imports:[CommonModule,FormsModule,RouterLink],
  styleUrl:'./demands.scss',
  template:`
  <main class="demand-shell">
    <nav class="demand-crumb" aria-label="Navegação"><a routerLink="/bjn/demandas">Demandas</a><span>/</span><strong>Nova demanda</strong></nav>
    <header class="demand-heading">
      <div><span class="eyebrow">BJN · ATENDIMENTO JURÍDICO</span><h1>{{triageComplete()?'Cadastrar demanda':'Como podemos direcionar sua consulta?'}}</h1>
        <p>{{triageComplete()?'Informe os dados necessários para gerar seu protocolo.':'Uma triagem rápida identifica a equipe ou o canal responsável e evita cadastros desnecessários.'}}</p></div>
      <a routerLink="/bjn/demandas" class="demand-outlined">Consultar demandas</a>
    </header>
    <ol class="bjn-journey-steps" aria-label="Etapas da jornada">
      @for(step of journeySteps;track $index;let position=$index){<li [class.active]="position === (triageComplete()?1:0)" [attr.aria-current]="position === (triageComplete()?1:0)?'step':null"><span>{{position+1}}</span>{{step}}</li>}
    </ol>
    @if(!triageComplete()){
      <section class="surface demand-card bjn-triage" aria-labelledby="triage-heading">
        <div class="demand-section-heading"><span class="demand-step">01</span><div><h2 id="triage-heading">Identificação da demanda</h2><p>Escolha a opção que melhor descreve sua necessidade.</p></div></div>
        <div class="bjn-triage-options" role="group" aria-label="Tipo da demanda">
          @for(option of triageOptions;track option.code){
            <button type="button" class="bjn-triage-choice" [class.selected]="triageCategory()===option.code" (click)="chooseCategory(option.code)">
              <strong>{{option.title}}</strong><span>{{option.hint}}</span>
            </button>
          }
        </div>
        @if(triageCategory()==='PROCESSO_COM_BANCO'){
          <div class="bjn-triage-branch">
            <div class="demand-field"><label for="bank-role">Posição do Banco no processo</label>
              <select id="bank-role" [(ngModel)]="bankRole"><option value="">Selecione</option><option value="AUTOR">Banco autor</option><option value="REU">Banco réu</option></select></div>
            <div class="demand-field"><label for="gcpj">Há cadastro no GCPJ?</label>
              <select id="gcpj" [(ngModel)]="gcpj"><option value="">Selecione</option><option value="SIM">Sim</option><option value="NAO">Não</option></select></div>
          </div>
        }
        @if(triageResult();as result){
          <div class="bjn-route-result" aria-live="polite"><span class="eyebrow">ENCAMINHAMENTO IDENTIFICADO</span><h3>{{result.label}}</h3><p>{{result.destination}}</p>
            @if(!result.requires_registration){<p><strong>Esta solicitação segue um canal específico.</strong> O BJN não realizou envio ou integração externa.</p>}
            <small>{{result.notice}}</small>
          </div>
        }
        @if(triageError()){<p class="demand-error" role="alert">{{triageError()}}</p>}
        <div class="bjn-triage-actions">
          <button type="button" class="primary" [disabled]="!triageCategory()||triaging()" (click)="validateTriage()">{{triaging()?'Validando...':(triageResult()?.requires_registration?'Revalidar triagem':'Ver encaminhamento')}}</button>
          @if(triageResult()?.requires_registration){<button type="button" class="primary" (click)="triageComplete.set(true)">Prosseguir para cadastro →</button>}
        </div>
      </section>
    } @else {
      <div class="bjn-journey-return"><span>Triagem concluída: nenhuma opção de encaminhamento específico.</span><button type="button" class="demand-outlined" (click)="backToTriage()">Alterar resposta</button></div>
    <div class="demand-layout">
      <div class="demand-form-column">
        <section class="surface demand-card" aria-labelledby="cad-dados">
          <div class="demand-section-heading"><span class="demand-step">01</span><div><h2 id="cad-dados">Dados da solicitação</h2><p>Informações que ajudam a direcionar a demanda.</p></div></div>
          <div class="demand-fields">
            <div class="demand-field"><label for="dept">Departamento Solicitante <span class="required">*</span></label>
              <input id="dept" maxlength="120" [(ngModel)]="form.requesting_department" placeholder="Informe o departamento" autocomplete="organization" required />
            </div>
            <div class="demand-field"><label>Solicitante</label>
              <div class="demand-readonly"><strong>{{configuration()?.actor?.name || 'Validando sessão...'}}</strong><small>Identificação fornecida pela sessão autenticada.</small></div>
            </div>
            <div class="demand-grid-2">
              <div class="demand-field"><label for="area">Área de consulta <span class="required">*</span></label>
                <input id="area" maxlength="120" [(ngModel)]="form.consult_area" placeholder="Ex.: Negócios regionais" required />
              </div>
              <div class="demand-field"><label for="nature">Natureza do serviço <span class="required">*</span></label>
                <select id="nature" [(ngModel)]="form.service_nature" (ngModelChange)="onNatureChanged($event)" required>
                  <option value="">Selecione a natureza</option>
                  @for(nature of natures;track nature){<option [value]="nature">{{nature}}</option>}
                </select>
              </div>
            </div>
            <div class="demand-grid-2">
              <div class="demand-field"><label for="agency">Agência <span class="required">*</span></label><input id="agency" maxlength="40" [(ngModel)]="form.branch" placeholder="Identificação da agência" required /></div>
              <div class="demand-field"><label for="requester-email">E-mail do demandante <span class="required">*</span></label><input id="requester-email" maxlength="250" type="email" [(ngModel)]="form.requester_email" autocomplete="email" placeholder="E-mail corporativo da sessão" required /></div>
            </div>
            <div class="demand-grid-2">
              <div class="demand-field"><label for="client-name">Nome do cliente <span class="required">*</span></label><input id="client-name" maxlength="180" [(ngModel)]="form.client_name" placeholder="Cliente relacionado à consulta" required /></div>
              <div class="demand-field"><label for="client-cpf">CPF do cliente <span class="required">*</span></label><input id="client-cpf" maxlength="14" inputmode="numeric" [(ngModel)]="form.client_document" placeholder="Somente números" required /><small>CPF protegido por HMAC no armazenamento.</small></div>
            </div>
            @if(form.service_nature && form.service_nature!=='Pareceres em geral'){<p class="bjn-required-note">Para {{form.service_nature}}, é obrigatório anexar ao menos um documento.</p>}
            @if(form.service_nature==='Pareceres em geral'){<p class="bjn-required-note">Essa natureza passa por triagem administrativa antes de chegar à equipe jurídica. Anexo opcional.</p>}
            <div class="demand-field"><label for="title">Título da demanda <span class="required">*</span></label>
              <input id="title" maxlength="180" [(ngModel)]="form.title" placeholder="Escreva um título objetivo" required />
              <small>Use um título que permita localizar a demanda futuramente.</small>
            </div>
            <div class="demand-field"><div class="demand-label-line"><label for="description">Descrição da consulta <span class="required">*</span></label><small>{{form.description.length}} / 8.000</small></div>
              <textarea id="description" maxlength="8000" rows="6" [(ngModel)]="form.description" placeholder="Apresente o contexto, sua necessidade e as informações relevantes para o atendimento." required></textarea>
            </div>
            <div class="demand-ai-block" aria-labelledby="demand-ai-title">
              <div class="demand-ai-head"><div><span class="eyebrow">ORIENTAÇÃO INICIAL</span><h3 id="demand-ai-title" tabindex="-1">Consultar sugestão da IA</h3><p>Antes de abrir uma demanda, veja se há uma orientação inicial que possa ajudar.</p></div>
                <button type="button" class="demand-outlined" [disabled]="analyzing() || form.description.trim().length<15 || !configuration()?.ai_available" (click)="analyzeDescription()">{{analyzing()?'Analisando...':'Analisar descrição'}}</button>
              </div>
              <p class="demand-muted">A descrição pode ser analisada separadamente. Ao selecionar um PDF pesquisável, a IA também o analisa com o prompt da natureza escolhida. A sugestão não aciona nem substitui advogado.</p>
              @if(configuration() && !configuration()?.ai_available){<p class="demand-muted" role="status">{{configuration()?.ai_configuration?.message || 'Análise indisponível neste ambiente. O cadastro continua funcionando normalmente.'}}</p>}
              @if(analyzingDocument()){<p class="demand-muted" role="status">Analisando automaticamente o conteúdo dos anexos com o prompt de {{form.service_nature}}…</p>}
              @if(documentAnalysisError()){<p class="demand-error" role="alert">{{documentAnalysisError()}}</p>}
              @if(files().length && form.service_nature && form.service_nature!=='Pareceres em geral'){
                <button type="button" class="demand-outlined" (click)="analyzeSelectedDocuments()" [disabled]="analyzingDocument() || !configuration()?.ai_available">Reanalisar documentos</button>
              }
              @if(documentSuggestion();as suggestion){
                <div class="demand-ai-result bjn-document-suggestion" aria-live="polite">
                  <strong>Sugestão da IA — {{suggestion.nature}} (parecer preliminar)</strong>
                  <small>{{suggestion.documents_analyzed}} documento(s) analisado(s) · versão do prompt: {{suggestion.prompt_version}}</small>
                  <div class="bjn-opinion-text">{{suggestion.text}}</div>
                  @for(warning of suggestion.warnings;track $index){<p class="demand-muted">{{warning}}</p>}
                  <small>Texto gerado automaticamente para análise; somente o advogado responsável pode revisar e publicar o parecer jurídico.</small>
                </div>
              }
              @if(aiError()){<p class="demand-error" role="alert">{{aiError()}}</p>}
              @if(guidance() && isGuidanceCurrent()){
                <div class="demand-ai-result" aria-live="polite"><strong>Sugestão da IA — {{guidance()!.encaminhamento==='POSSIVEL_AUTOATENDIMENTO'?'Possível autoatendimento':'Avaliação humana recomendada'}}</strong>
                  <h4>{{guidance()!.resumo}}</h4><p>{{guidance()!.orientacao}}</p>
                  @if(guidance()!.passos_sugeridos.length){<ol>@for(step of guidance()!.passos_sugeridos;track $index){<li>{{step}}</li>}</ol>}
                  <small>Orientação informacional, não é parecer jurídico e pode conter imprecisões.</small>
                  @if(guidance()!.encaminhamento==='POSSIVEL_AUTOATENDIMENTO'){
                    <a routerLink="/bjn/demandas" class="demand-outlined">Minha dúvida foi resolvida — não cadastrar</a>
                  } @else {<p class="demand-ai-escalation">Você pode continuar o cadastro para atendimento de um advogado.</p>}
                </div>
              } @else if(guidance() && !isGuidanceCurrent()) {<p class="demand-ai-stale">A descrição mudou. Gere uma nova orientação para avaliar o texto atual.</p>}
            </div>
          </div>
        </section>
        <section class="surface demand-card" aria-labelledby="cad-env">
          <div class="demand-section-heading"><span class="demand-step">02</span><div><h2 id="cad-env">Envolvidos</h2><p>Adicione somente os dados necessários à consulta. Esta etapa é opcional.</p></div></div>
          @for(person of involved();track $index; let position=$index){
            <div class="demand-person">
              <div class="demand-person-head"><strong>Envolvido {{position+1}}</strong><button type="button" class="demand-text-button" (click)="removePerson(position)">Remover</button></div>
              <div class="demand-grid-2">
                <div class="demand-field"><label [for]="'person-type-'+position">Tipo</label>
                  <select [id]="'person-type-'+position" [(ngModel)]="person.type"><option value="Pessoa física">Pessoa física</option><option value="Pessoa jurídica">Pessoa jurídica</option><option value="Outro">Outro</option></select>
                </div>
                <div class="demand-field"><label [for]="'person-name-'+position">Nome / razão social <small>(obrigatório somente se houver envolvido)</small></label><input [id]="'person-name-'+position" [(ngModel)]="person.name" maxlength="150" placeholder="Nome do envolvido"/></div>
                <div class="demand-field"><label [for]="'person-doc-'+position">Documento <small>(opcional)</small></label><input [id]="'person-doc-'+position" [(ngModel)]="person.document" maxlength="32" placeholder="Preencha apenas se necessário"/></div>
                <div class="demand-field"><label [for]="'person-period-'+position">Período <small>(opcional)</small></label><input [id]="'person-period-'+position" [(ngModel)]="person.period" maxlength="100" placeholder="Período de referência"/></div>
              </div>
            </div>
          }
          <button type="button" class="demand-outlined" [disabled]="involved().length >= 20" (click)="addPerson()">+ Adicionar envolvido</button>
        </section>
        <section class="surface demand-card" aria-labelledby="cad-arq">
          <div class="demand-section-heading"><span class="demand-step">03</span><div><h2 id="cad-arq">Anexos</h2><p>Adicione evidências que ajudem o advogado a compreender a solicitação.</p></div></div>
          <label class="demand-dropzone" [class.drag-active]="dragging()" for="demand-upload" (dragover)="over($event)" (dragleave)="dragging.set(false)" (drop)="dropped($event)">
            <span class="demand-upload-icon" aria-hidden="true">↑</span>
            <strong>Selecione ou arraste documentos para anexar</strong><span>PDF, PNG ou JPEG · até 15 MB por arquivo · máximo de 20 arquivos</span>
            <input class="demand-file-input" id="demand-upload" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" multiple (change)="selectFiles($event)" />
          </label>
          @if(analyzingDocument()){<p class="bjn-upload-analysis-status" role="status">A IA está lendo os PDFs selecionados e preparando uma sugestão conforme a natureza da demanda.</p>}
          @if(documentSuggestion()){<p class="bjn-upload-analysis-status" role="status">Sugestão documental atualizada. <button type="button" class="demand-text-button" (click)="focusField('demand-ai-title')">Ver sugestão da IA</button></p>}
          @if(documentAnalysisError()){<p class="demand-muted" role="status">A análise documental não foi concluída. Você pode continuar o cadastro e solicitar avaliação humana.</p>}
          @if(files().length){<div class="demand-upload-list" aria-label="Documentos selecionados">
            @for(file of files();track $index;let index=$index){<div class="demand-upload-row"><span class="demand-file-square">{{file.name.toLowerCase().endsWith('.pdf')?'PDF':'IMG'}}</span><div><strong>{{file.name}}</strong><small>{{size(file.size)}}</small></div><button type="button" class="demand-icon-button" [attr.aria-label]="'Remover '+file.name" (click)="removeFile(index)">×</button></div>}
          </div>}
        </section>
      </div>
      <aside class="demand-side-panel">
        <div class="surface demand-summary-panel">
          <span class="eyebrow">REVISÃO ANTES DO ENVIO</span><h2>Resumo da demanda</h2>
          <div class="demand-summary-line"><span>Título</span><strong>{{form.title.trim() || 'Não informado'}}</strong></div>
          <div class="demand-summary-line"><span>Área de consulta</span><strong>{{form.consult_area.trim() || 'Não informada'}}</strong></div>
          <div class="demand-summary-line"><span>Natureza do serviço</span><strong>{{form.service_nature.trim() || 'Não informada'}}</strong></div>
          <div class="demand-summary-line"><span>Envolvidos preenchidos</span><strong>{{completedInvolved().length}}</strong></div>
          <div class="demand-summary-line"><span>Anexos</span><strong>{{files().length}} {{form.service_nature && form.service_nature!=='Pareceres em geral'?'(obrigatório)':''}}</strong></div>
          <div class="demand-hint">Protocolo gerado após o envio. {{form.service_nature==='Pareceres em geral'?'A solicitação passará por triagem administrativa.':'Após o cadastro, a equipe jurídica poderá distribuir a demanda.'}} Você acompanhará o parecer nesta aplicação.</div>
          @if(validationIssues().length){
            <div class="demand-validation-box" aria-label="Pendências do cadastro">
              <strong>{{validationIssues().length}} {{validationIssues().length===1?'pendência':'pendências'}} para cadastrar</strong>
              <ul>
                @for(issue of validationIssues();track issue.fieldId){
                  <li><button type="button" class="demand-validation-link" (click)="focusField(issue.fieldId)">{{issue.message}}</button></li>
                }
              </ul>
            </div>
          } @else if(configuration()) {
            <p class="demand-validation-ready">Dados obrigatórios preenchidos. Você pode cadastrar a demanda.</p>
          }
          @if(!configuration()){
            <p class="demand-validation-session">A identificação do solicitante ainda não foi confirmada. Você pode revisar os campos; ao enviar, a conexão será verificada novamente.</p>
          }
          @if(error()){<p class="demand-error" role="alert">{{error()}}</p>}
          <button class="primary demand-submit" type="button" [disabled]="sending()" (click)="submit()">{{sending()?'Enviando demanda...':'Cadastrar demanda'}}</button>
          <p class="demand-disclaimer">Ao enviar, os documentos ficarão associados à demanda e acessíveis apenas aos usuários autorizados.</p>
        </div>
      </aside>
    </div>
    }
  </main>`
})
export class BjnDemandNewComponent implements OnInit {
  private readonly api=inject(BjnDemandApiService);
  private readonly router=inject(Router);
  readonly configuration=signal<DemandConfiguration|null>(null);
  readonly files=signal<File[]>([]);
  readonly involved=signal<InvolvedPerson[]>([]);
  readonly dragging=signal(false);
  readonly sending=signal(false);
  readonly error=signal('');
  readonly aiError=signal('');
  readonly analyzing=signal(false);
  readonly analyzingDocument=signal(false);
  readonly documentSuggestion=signal<DocumentAISuggestion|null>(null);
  readonly documentAnalysisError=signal('');
  private analysisGeneration=0;
  readonly guidance=signal<DemandGuidance|null>(null);
  readonly analyzedDescription=signal('');
  readonly size=readableSize;
  readonly journeySteps=['Triagem','Cadastro','Distribuição','Parecer','Consulta'];
  readonly natures=['Inventário','Alvará','Curatela','Procuração','Pareceres em geral'];
  readonly triageOptions:{code:TriageCategory;title:string;hint:string}[]=[
    {code:'PROCESSO_COM_BANCO',title:'Processo judicial com o Banco como parte',hint:'Verifique a posição do Banco e o GCPJ.'},
    {code:'OFICIO_DELEGACIA',title:'Ofício de Delegacia de Polícia',hint:'Orientação de cadastro no WCPS.'},
    {code:'INTIMACAO_DELEGACIA',title:'Intimação de Delegacia de Polícia',hint:'Encaminhamento à Consultoria Criminal.'},
    {code:'OFICIO_SEM_BANCO',title:'Ofício judicial sem o Banco como parte',hint:'Atendimento operacional.'},
    {code:'OUTRAS',title:'Nenhuma das opções anteriores',hint:'Continuar para cadastro e triagem da equipe.'},
  ];
  readonly triageCategory=signal<TriageCategory|null>(null);
  readonly triageResult=signal<TriageDecision|null>(null);
  readonly triageError=signal('');readonly triaging=signal(false);readonly triageComplete=signal(false);
  bankRole='';gcpj='';
  form:DemandInput={requesting_department:'',consult_area:'',service_nature:'',title:'',description:'',involved:[],triage_type:'',triage_proof:'',branch:'',requester_email:'',client_name:'',client_document:''};
  chooseCategory(value:TriageCategory):void{this.triageCategory.set(value);this.triageResult.set(null);this.triageError.set('');this.bankRole='';this.gcpj='';}
  backToTriage():void {this.triageComplete.set(false);this.triageResult.set(null);this.form.triage_type='';this.form.triage_proof='';}
  async validateTriage():Promise<void>{
    const category=this.triageCategory();if(!category || this.triaging())return;
    if(category==='PROCESSO_COM_BANCO' && (!this.bankRole||!this.gcpj)){this.triageError.set('Informe a posição do Banco e se existe GCPJ.');return;}
    this.triaging.set(true);this.triageError.set('');this.triageResult.set(null);
    try {const result=await firstValueFrom(this.api.triage(category,this.bankRole||null,this.gcpj?this.gcpj==='SIM':null));
      this.triageResult.set(result);this.form.triage_type=result.requires_registration?'OUTRAS':'';this.form.triage_proof=result.proof||'';
    } catch(cause){this.triageError.set(friendlyApiError(cause));} finally{this.triaging.set(false);}
  }
  /** Alterar a natureza invalida a sugestão anterior e escolhe o prompt correspondente. */
  onNatureChanged(nature:string):void {
    this.form.service_nature=nature;
    void this.analyzeSelectedDocuments();
  }
  /** O envio é automático, mas sua falha nunca bloqueia o registro da demanda. */
  async analyzeSelectedDocuments():Promise<void> {
    const generation=++this.analysisGeneration;
    this.documentSuggestion.set(null);this.documentAnalysisError.set('');
    const nature=this.form.service_nature;
    const pdfs=this.files().filter(file=>file.type==='application/pdf').slice(0,4);
    if(!nature||nature==='Pareceres em geral'||!this.files().length){this.analyzingDocument.set(false);return;}
    if(!pdfs.length){this.analyzingDocument.set(false);this.documentAnalysisError.set('Análise automática disponível para PDF pesquisável. Imagens serão preservadas para avaliação humana.');return;}
    // Quando a configuração ainda está sendo consultada, a análise será iniciada
    // por loadActor assim que a API confirmar o estado. Não presumimos falha.
    if(!this.configuration()){this.analyzingDocument.set(false);return;}
    if(!this.configuration()?.ai_available){
      this.analyzingDocument.set(false);
      this.documentAnalysisError.set(this.configuration()?.ai_configuration?.message || 'Análise corporativa indisponível. É possível cadastrar a demanda normalmente.');
      return;
    }
    this.analyzingDocument.set(true);
    try{
      const result=await firstValueFrom(this.api.analyzeUploadedDocuments(nature,this.form.description,pdfs));
      if(generation===this.analysisGeneration)this.documentSuggestion.set(result);
    }catch(cause){if(generation===this.analysisGeneration)this.documentAnalysisError.set(friendlyApiError(cause));}
    finally{if(generation===this.analysisGeneration)this.analyzingDocument.set(false);}
  }
  isGuidanceCurrent():boolean {return this.analyzedDescription()===this.form.description.trim();}
  /** Análise apenas do texto explicitamente digitado, sem upload nem cadastro. */
  async analyzeDescription():Promise<void> {
    if(this.analyzing() || this.form.description.trim().length<15)return;
    this.analyzing.set(true);this.aiError.set('');this.guidance.set(null);
    const text=this.form.description.trim();
    try {
      const guidance=await firstValueFrom(this.api.analyzeDraft(text));
      this.analyzedDescription.set(text);this.guidance.set(guidance);
    } catch (cause) {
      this.aiError.set(friendlyApiError(cause));
    } finally {this.analyzing.set(false);}
  }
  /** A etapa de envolvidos é opcional: linhas totalmente em branco não integram o cadastro. */
  completedInvolved():InvolvedPerson[] {
    return this.involved().filter(person=>Boolean(person.name.trim()||person.document.trim()||person.period.trim()));
  }

  /** As mesmas restrições de tamanho existentes no backend são explicadas antes do envio. */
  validationIssues():ValidationIssue[] {
    const issues:ValidationIssue[]=[];
    const fields:[string,string,string,number][]=[
      ['dept','Departamento Solicitante',this.form.requesting_department,2],
      ['area','Área de consulta',this.form.consult_area,2],
      ['nature','Natureza do serviço',this.form.service_nature,2],
      ['title','Título da demanda',this.form.title,5],
      ['description','Descrição da consulta',this.form.description,15],
      ['agency','Agência',this.form.branch,2],
      ['requester-email','E-mail do demandante',this.form.requester_email,5],
      ['client-name','Nome do cliente',this.form.client_name,2],
      ['client-cpf','CPF do cliente',this.form.client_document.replace(/\D/g,''),11],
    ];
    for(const [fieldId,label,value,minLength] of fields){
      if(value.trim().length<minLength){
        issues.push({fieldId,message:`${label}: informe pelo menos ${minLength} caracteres.`});
      }
    }
    if(!this.natures.includes(this.form.service_nature))issues.push({fieldId:'nature',message:'Selecione uma das cinco naturezas disponíveis.'});
    if(this.form.service_nature && this.form.service_nature!=='Pareceres em geral' && !this.files().length)issues.push({fieldId:'demand-upload',message:'Esta natureza exige pelo menos um documento anexo.'});
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.form.requester_email.trim()))issues.push({fieldId:'requester-email',message:'Informe um e-mail válido.'});
    this.involved().forEach((person,index)=>{
      const anyContent=Boolean(person.name.trim()||person.document.trim()||person.period.trim());
      if(anyContent&&person.name.trim().length<2){
        issues.push({fieldId:`person-name-${index}`,message:`Envolvido ${index+1}: informe o nome ou remova a linha incompleta.`});
      }
    });
    return issues;
  }

  /** Leva o usuário ao campo com erro, inclusive quando está fora da tela. */
  focusField(fieldId:string):void {
    const element=document.getElementById(fieldId);
    element?.scrollIntoView({behavior:'smooth',block:'center'});
    element?.focus({preventScroll:true});
  }

  ngOnInit():void {void this.loadActor();}
  private async loadActor():Promise<void> {
    try {
      this.configuration.set(await firstValueFrom(this.api.configuration()));
      // A sessão determina o endereço inicial. O servidor verifica sua correspondência.
      this.form.requester_email=this.configuration()?.actor?.email || '';
      this.error.set('');
      // Analisa anexos já selecionados durante o carregamento da sessão.
      if(this.files().length && this.form.service_nature)void this.analyzeSelectedDocuments();
    } catch(cause){
      this.configuration.set(null);
      this.analyzingDocument.set(false);
      this.error.set(`Não foi possível validar a sessão: ${friendlyApiError(cause)}`);
    }
  }
  addPerson():void {if(this.involved().length<20)this.involved.update(v=>[...v,{type:'Pessoa física',name:'',document:'',period:''}]);}
  removePerson(index:number):void {this.involved.update(v=>v.filter((_,i)=>i!==index));}
  removeFile(index:number):void {this.files.update(v=>v.filter((_,i)=>i!==index));void this.analyzeSelectedDocuments();}
  over(event:DragEvent):void {event.preventDefault();this.dragging.set(true);}
  dropped(event:DragEvent):void {event.preventDefault();this.dragging.set(false);this.acceptFiles(Array.from(event.dataTransfer?.files||[]));}
  selectFiles(event:Event):void {const element=event.target as HTMLInputElement;this.acceptFiles(Array.from(element.files||[]));element.value='';}
  private acceptFiles(incoming:File[]):void {
    const existing=[...this.files()];
    let rejected=false;
    for(const file of incoming){
      if(!['application/pdf','image/png','image/jpeg'].includes(file.type) || file.size>15*1024*1024 || file.size===0){rejected=true;this.error.set(`Arquivo não aceito: ${file.name}. Utilize PDF, PNG ou JPEG de até 15 MB.`);continue;}
      if(existing.length>=20){rejected=true;this.error.set('O limite é de 20 arquivos por demanda.');break;}
      if(!existing.some(v=>v.name===file.name && v.size===file.size && v.lastModified===file.lastModified))existing.push(file);
    }
    this.files.set(existing);
    if(incoming.length && !rejected)this.error.set('');
    if(incoming.length)void this.analyzeSelectedDocuments();
  }
  /** Evita o silêncio do botão: valida, indica o campo e mantém dados em caso de falha. */
  async submit():Promise<void> {
    if(this.sending()) return;
    this.error.set('');
    if(!this.triageComplete() || this.form.triage_type!=='OUTRAS'){
      this.error.set('Conclua a triagem inicial antes de enviar a demanda.');return;
    }
    const issues=this.validationIssues();
    if(issues.length){
      this.error.set(`Existem ${issues.length} ${issues.length===1?'campo que precisa':'campos que precisam'} de correção. Selecione uma pendência para localizar o campo.`);
      this.focusField(issues[0].fieldId);
      return;
    }
    this.sending.set(true);
    try {
      // A sessão é confirmada pelo servidor antes do cadastro, sem criar identidade artificial.
      if(!this.configuration()) this.configuration.set(await firstValueFrom(this.api.configuration()));
      const payload:DemandInput={...this.form,involved:this.completedInvolved().map(person=>({...person}))};
      const created=await firstValueFrom(this.api.create(payload,this.files()));
      await this.router.navigate(['/bjn/demandas',created.id]);
    }catch(cause){
      this.error.set(friendlyApiError(cause));
    }finally{
      this.sending.set(false);
    }
  }
}
