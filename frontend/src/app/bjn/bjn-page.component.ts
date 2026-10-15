/** Questionário BJN: perguntas e opções publicadas pela API a partir do script_bjn. */
import {CommonModule} from '@angular/common';
import {Component, computed, inject, OnInit, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {firstValueFrom} from 'rxjs';
import {Assessment,BjnApiService,ScriptQuestion,ScriptWorkflow} from '../core/bjn-api.service';

@Component({selector:'app-bjn-page',standalone:true,imports:[CommonModule,FormsModule],styleUrl:'./bjn-page.component.scss',template:`
<main class="bjn-page">
 <header class="bjn-header"><div><span class="eyebrow">BJN · Contratos</span><h1>Elaboração de minutas</h1><p>Questionário conforme script_bjn, com cláusulas exclusivamente do book jurídico.</p></div><span class="bjn-status">Rastreabilidade do script</span></header>
 <div class="bjn-layout"><section class="bjn-main surface">
 @if (loading()){<p>Carregando questionário do script BJN...</p>}
 @else if (error() && !workflow()){<p role="alert" class="bjn-error">{{error()}}</p>}
 @else if (!result()) {
  <div class="bjn-progress"><span>Página {{page()}} de {{workflow()?.source_pages}}</span><strong>Questionário de contratação</strong><div class="bjn-progress-track"><span [style.width.%]="page()*100/8"></span></div></div>
  @for(question of visibleQuestions();track question.id){<div class="bjn-question">
   <label [attr.for]="question.id">{{question.label}}</label>
   @if(question.type==='choice' || question.type==='boolean'){
    <div class="bjn-options" role="group" [attr.aria-label]="question.label">
    @for(option of question.options || [];track option.value){<button type="button" [class.selected]="answers()[question.id]===option.value" (click)="setAnswer(question,option.value)">{{option.label}}</button>}
    </div>
   } @else if(question.type==='multi') {
    <div class="bjn-options" role="group" [attr.aria-label]="question.label">
    @for(option of question.options || [];track option.value){<button type="button" [class.selected]="isSelected(question.id,option.value)" (click)="toggleAnswer(question,option.value)">{{option.label}}</button>}
    </div>
   } @else {
    <input [id]="question.id" [type]="question.type==='number'?'number':'text'" [min]="question.type==='number'?1:null" [value]="answers()[question.id] || ''" (input)="setAnswer(question,$any($event.target).value)" />
   }
   <small>Referência: script_bjn · página {{question.source_page}}</small>
  </div>}
  <div class="bjn-actions"><button class="bjn-secondary" type="button" [disabled]="page()===1 || busy()" (click)="page.set(page()-1)">Voltar</button><button class="bjn-primary" type="button" [disabled]="!canContinue() || busy()" (click)="next()">{{page()===8?'Avaliar solicitação':'Continuar'}}</button></div>
  @if(error()){<p role="alert" class="bjn-error">{{error()}}</p>}
 } @else {<div class="bjn-result"><div class="bjn-result-symbol">!</div><span class="eyebrow">Atendimento especializado</span><h2>A minuta não será gerada automaticamente</h2>
  <p>As regras e cláusulas ainda aguardam homologação integral. Não é permitido inventar uma alternativa.</p>
  <h3>Motivos</h3><ul>@for(reason of result()!.reasons;track reason){<li>{{reason}}</li>}</ul>
  <p>Canal indicado pelo script: {{workflow()?.human_channel}}. Nenhum chamado foi aberto automaticamente.</p>
  <div class="bjn-actions"><button class="bjn-secondary" type="button" (click)="restart()">Nova solicitação</button><button class="bjn-primary" type="button" (click)="copySummary()">Copiar resumo</button></div></div>}
 </section>
 <aside class="bjn-side" aria-label="Pré-visualização da minuta">
  <section class="surface bjn-preview">
    <div class="bjn-preview-head"><div><span class="eyebrow">Visualização em tempo real</span><h3>Prévia da minuta</h3></div><span class="bjn-preview-status">Não homologada</span></div>
    <p class="bjn-preview-note">Atualização automática a cada resposta. Nenhuma cláusula é exibida sem correspondência literal aprovada no book.</p>
    <div class="bjn-paper" aria-live="polite" aria-atomic="false">
      <h4>MINUTA CONTRATUAL</h4>
      <p class="bjn-paper-subtitle">Prévia estrutural — não constitui documento contratual</p>
      <div class="bjn-paper-section"><strong>2.2 Contratada</strong><p class="bjn-paper-placeholder">Dados da Contratada pendentes de preenchimento e validação.</p></div>
      <div class="bjn-paper-section"><strong>Contexto informado no questionário</strong>
        @if(answerSummary().length){
          @for(item of answerSummary();track item.id){<div class="bjn-preview-answer"><span>{{item.label}}</span><p>{{item.value}}</p></div>}
        } @else {<p class="bjn-paper-placeholder">Preencha o questionário para visualizar as informações selecionadas.</p>}
      </div>
      <div class="bjn-paper-section"><strong>Cláusulas contratuais</strong><p class="bjn-paper-placeholder">@if(bookClauses().length){Os trechos textuais transcritos estão exibidos abaixo, com indicação de conferência pendente.}@else{Nenhuma cláusula vinculada às respostas atuais.}</p></div>
    </div>
    @for(clause of bookClauses();track clause.clause_id){<section class="bjn-book-evidence"><h4>{{clause.title}}</h4><p class="bjn-preview-warning">Extração OCR preliminar vinculada à página {{clause.source_page}} do book; conferência literal pendente. Os demais trechos do book ainda não estão vinculados a esta resposta.</p>@for(section of clause.sections;track $index){<div class="bjn-paper-section"><strong>{{section.heading}}</strong><p class="bjn-clause-text">{{section.text}}</p></div>}</section>}
    <p class="bjn-preview-warning">O painel não inventa cláusulas nem antecipa regras de seleção. A emissão do PDF permanece bloqueada até homologação.</p>
  </section>
 </aside></div>
 <div class="bjn-chat-widget">@if(chatOpen()){<section class="bjn-chat-panel" aria-label="Chatbot BJN"><header><div><strong>Assistente BJN</strong><small>API corporativa · atendimento independente</small></div><button type="button" (click)="chatOpen.set(false)" aria-label="Fechar assistente">×</button></header><div class="bjn-chat-messages" role="log" aria-live="polite">@if(!messages().length){<p>Como posso ajudar com o questionário?</p>}@for(message of messages();track $index){<p [class.from-user]="message.role==='user'"><strong>{{message.role==='user'?'Você':'Assistente'}}</strong>{{message.content}}</p>}</div><form (ngSubmit)="sendMessage()"><input name="question" [(ngModel)]="chatInput" maxlength="4000" placeholder="Digite sua pergunta" aria-label="Sua pergunta"/><button [disabled]="chatBusy() || !chatInput.trim()" type="submit">Enviar</button></form></section>}
 <button class="bjn-chat-toggle" type="button" [attr.aria-expanded]="chatOpen()" (click)="chatOpen.set(!chatOpen())">{{chatOpen()?'Fechar chat':'Assistente BJN'}}</button></div>
</main>`})
export class BjnPageComponent implements OnInit {
 readonly api=inject(BjnApiService);
 readonly bookClauses=signal<{clause_id:string;title:string;sections:{heading:string;text:string}[];source_page:number;remaining_pages:number}[]>([]);
 private previewSequence=0;
 async refreshBookPreview():Promise<void>{const seq=++this.previewSequence;try{const response=await firstValueFrom(this.api.bookPreview(this.answers()));if(seq===this.previewSequence)this.bookClauses.set(response.clauses);}catch{if(seq===this.previewSequence){this.bookClauses.set([]);this.error.set("Não foi possível validar a transcrição do book para a prévia.");}}}
 readonly workflow=signal<ScriptWorkflow|null>(null);readonly page=signal(1);readonly answers=signal<Record<string,string|string[]|number>>({});
 readonly loading=signal(true);readonly busy=signal(false);readonly error=signal('');readonly result=signal<Assessment|null>(null);
 readonly chatOpen=signal(false);readonly chatBusy=signal(false);readonly messages=signal<{role:'user'|'assistant';content:string}[]>([]);chatInput='';
 readonly answerSummary=computed(()=>{const schema=this.workflow();if(!schema)return [];return schema.questions.filter(q=>this.answers()[q.id]!==undefined&&this.isVisible(q)).map(q=>({id:q.id,label:q.label,value:Array.isArray(this.answers()[q.id])?(this.answers()[q.id] as string[]).join(', '):String(this.answers()[q.id])}));});
 readonly visibleQuestions=computed(()=>this.workflow()?.questions.filter(q=>q.source_page===this.page()&&this.isVisible(q))??[]);
 async ngOnInit():Promise<void>{try{this.workflow.set(await firstValueFrom(this.api.questionnaire()));}catch{this.error.set('Não foi possível carregar o questionário oficial.');}finally{this.loading.set(false);}}
 isVisible(q:ScriptQuestion):boolean{return Object.entries(q.when||{}).every(([k,v])=>Array.isArray(this.answers()[k])?(this.answers()[k] as string[]).includes(v):this.answers()[k]===v);}
 setAnswer(q:ScriptQuestion,value:string):void{this.answers.update(a=>({...a,[q.id]:value}));this.pruneHidden();this.error.set('');void this.refreshBookPreview();}
 isSelected(id:string,value:string):boolean{return ((this.answers()[id]||[]) as string[]).includes(value);}
 toggleAnswer(q:ScriptQuestion,value:string):void{const current=(this.answers()[q.id]||[]) as string[];this.answers.update(a=>({...a,[q.id]:current.includes(value)?current.filter(v=>v!==value):[...current,value]}));this.pruneHidden();this.error.set('');void this.refreshBookPreview();}
 pruneHidden():void{const schema=this.workflow();if(!schema)return;this.answers.update(old=>{const next={...old};let changed=true;while(changed){changed=false;for(const q of schema.questions){if(q.id in next && !Object.entries(q.when||{}).every(([k,v])=>Array.isArray(next[k])?(next[k] as string[]).includes(v):next[k]===v)){delete next[q.id];changed=true;}}}return next;});}
 canContinue():boolean{return this.visibleQuestions().every(q=>{const v=this.answers()[q.id];return v!==undefined && v!=='' && (!Array.isArray(v)||v.length>0) && (q.type!=='number'||(Number.isInteger(Number(v))&&Number(v)>0));});}
 async next():Promise<void>{if(!this.canContinue()||this.busy())return;if(this.page()<8){this.page.update(p=>p+1);return;}this.busy.set(true);this.error.set('');try{this.result.set(await firstValueFrom(this.api.evaluate(this.answers())));}catch(e){this.error.set('A API recusou respostas inconsistentes com o script BJN. Verifique o preenchimento.');}finally{this.busy.set(false);}}
 restart():void{this.page.set(1);this.answers.set({});this.bookClauses.set([]);this.result.set(null);this.error.set('');}
 copySummary():void{const value=['Solicitação BJN',...Object.entries(this.answers()).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`),...(this.result()?.reasons||[])].join('\n');void navigator.clipboard.writeText(value).catch(()=>this.error.set('Não foi possível copiar o resumo.'));}
 async sendMessage():Promise<void>{const question=this.chatInput.trim();if(!question||this.chatBusy())return;this.messages.update(v=>[...v,{role:'user',content:question}]);this.chatInput='';this.chatBusy.set(true);try{const r=await firstValueFrom(this.api.chat(question));this.messages.update(v=>[...v,{role:'assistant',content:r.resposta}]);}catch{this.messages.update(v=>[...v,{role:'assistant',content:'Não foi possível obter resposta da API corporativa.'}]);}finally{this.chatBusy.set(false);}}
}
