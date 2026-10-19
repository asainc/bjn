/** Contratos do módulo de demandas BJN, separados do questionário de minutas. */
import {HttpClient,HttpHeaders} from '@angular/common/http';
import {inject, Injectable} from '@angular/core';
import {ApiConfiguration} from './config';

export type DemandGuidance = {
  resumo:string;orientacao:string;passos_sugeridos:string[];
  encaminhamento:'POSSIVEL_AUTOATENDIMENTO'|'ATENDIMENTO_HUMANO';
  aviso?:string;created_at?:string;
};
export type DocumentAISuggestion = {nature:string;text:string;kind:string;prompt_version:string;source_version:string;documents_analyzed:number;warnings:string[];created_at?:string};
export type LawyerOption = {email:string;name:string;demo:boolean};
export type DemandStatus = 'RECEBIDA' | 'EM_TRIAGEM' | 'EM_ANALISE' | 'AGUARDANDO_INFORMACOES' | 'CONCLUIDA' | 'CANCELADA' | 'RESOLVIDA_IA' | 'TRIAGEM_ADMINISTRATIVA' | 'ENCAMINHADA_AREA' | 'PARECER_EM_REVISAO';
export type InvolvedPerson = {type:string; name:string; document:string; period:string};
export type DemandInput = {
  requesting_department:string;
  consult_area:string;
  service_nature:string;
  title:string;
  description:string;
  involved:InvolvedPerson[];
  triage_type:string;triage_proof:string;branch:string;requester_email:string;client_name:string;client_document:string;
};
export type TriageCategory = 'PROCESSO_COM_BANCO'|'OFICIO_DELEGACIA'|'INTIMACAO_DELEGACIA'|'OFICIO_SEM_BANCO'|'OUTRAS';
export type TriageDecision = {category:TriageCategory;label:string;destination:string;requires_registration:boolean;external_action_performed:boolean;notice:string;proof?:string};
export type DemandRegistration = {triage_type:string;triage_proof:string;branch:string;requester_email:string;client_name:string;document_mask:string;competence:string;destination_area:string};
export type DemandOpinion = {draft_text:string;final_text:string;published_at:string|null;reviewer_id:string|null;draft_at:string|null;version:number};
export type DemandSummary = {
  id:string; title:string; consult_area:string; service_nature:string;
  status:DemandStatus; lawyer_email:string|null; requester_name:string;
  created_at:string; updated_at:string;
};
export type DemandDocument = {
  id:string; original_name:string; media_type:string; file_size:number;
  sha256:string; category:'ANEXO'|'DOCUMENTO_ENVIADO'; uploaded_by:string; created_at:string;
};
export type DemandEvent = {event_type:string; description:string; actor_id:string; created_at:string};
export type DemandDetail = DemandSummary & {
  requesting_department:string; description:string; requester_id:string;
  involved:InvolvedPerson[]; documents:DemandDocument[]; events:DemandEvent[];
  can_manage:boolean; can_assign:boolean; can_resolve_ai:boolean; ai_guidance:DemandGuidance|null;
  registration:DemandRegistration|null;opinion:DemandOpinion|null;can_review_opinion:boolean;can_review_competence:boolean;
  document_ai_suggestion:DocumentAISuggestion|null;
  document_analysis_error?:string;
  notification_dispatch?:{status:string;count:number};
};
export type DemandConfiguration = {
  actor:{name:string;role:string;email:string}; allowed_lawyers:string[];lawyer_options:LawyerOption[];ai_available:boolean;
  max_file_size_mb:number; max_files:number; accepted_formats:string[];
  available_natures:string[];opinion_ai_available:boolean;demo_session_available:boolean;
  ai_configuration?:{code:string;message:string};
};

@Injectable({providedIn:'root'})
export class BjnDemandApiService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);
  private get endpoint():string {return `${this.config.baseUrl}/bjn/demandas`;}
  // Sessão fictícia em memória, habilitada exclusivamente pela configuração local da API.
  // Em produção, as identidades continuam sendo definidas pelo gateway corporativo.
  private demoReviewerEmail='';
  private demoEnabled=false;
  get isDemoReviewerActive():boolean{return Boolean(this.demoReviewerEmail);}
  enableDemoReviewer(email:string,configuration:DemandConfiguration):boolean {
    const allowed=configuration.demo_session_available && configuration.actor.role==='admin' &&
      configuration.lawyer_options.some(option=>option.demo && option.email===email);
    if(!allowed)return false;
    this.demoEnabled=true;this.demoReviewerEmail=email;return true;
  }
  disableDemoReviewer():void{this.demoReviewerEmail='';this.demoEnabled=false;}
  private headers():{headers:HttpHeaders}{
    const headers=this.demoEnabled && this.demoReviewerEmail ?
      new HttpHeaders({'X-Authenticated-Role':'advogado','X-Authenticated-User':this.demoReviewerEmail,
        'X-Authenticated-Name':'Advogado ficticio de testes'}) : new HttpHeaders();
    return {headers};
  }

  /** Mantém a autenticação sob responsabilidade do gateway, sem credenciais no frontend. */
  configuration() {return this.http.get<DemandConfiguration>(`${this.endpoint}/configuracao`,this.headers());}
  list(search='',status='',filters:{branch?:string;registered_email?:string;from_date?:string;client_cpf?:string}={}) {
    // Os documentos de identificação nunca são enviados como parâmetros de URL.
    return this.http.post<{items:DemandSummary[]}>(`${this.endpoint}/consulta`,{search,status,...filters},this.headers());
  }
  /** Triagem inicial baseada nas alternativas do fluxo, sem disparos externos. */
  triage(category:TriageCategory,bank_role:string|null,has_gcpj:boolean|null){
    return this.http.post<TriageDecision>(`${this.endpoint}/triagem`,{category,bank_role,has_gcpj},this.headers());
  }
  reviewCompetence(id:string,isTeamCompetence:boolean,destinationArea:string){
    return this.http.patch<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/competencia`,{is_team_competence:isTeamCompetence,destination_area:destinationArea},this.headers());
  }
  generateOpinionDraft(id:string){
    return this.http.post<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/parecer/rascunho`,{},this.headers());
  }
  publishOpinion(id:string,finalText:string,confirmed:boolean){
    return this.http.post<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/parecer/publicar`,{final_text:finalText,human_review_confirmed:confirmed},this.headers());
  }
  /** Prévia efêmera: um upload inicia text_generator com prompt da natureza selecionada. */
  analyzeUploadedDocuments(nature:string,description:string,files:File[]){
    const form=new FormData();form.append('nature',nature);form.append('description',description);
    for(const file of files)form.append('files',file,file.name);
    return this.http.post<DocumentAISuggestion>(`${this.endpoint}/assistente/analisar-documentos`,form,this.headers());
  }
  /** Reprocessa documentos já associados ao protocolo, sem novos uploads. */
  analyzeAttachedDocuments(id:string){
    return this.http.post<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/assistente/analisar-documentos`,{},this.headers());
  }
  /** A análise do rascunho não cria demanda nem encaminha a advogado. */
  analyzeDraft(description:string) {
    return this.http.post<DemandGuidance>(`${this.endpoint}/assistente/analisar`,{description},this.headers());
  }
  /** Em demanda existente, a sugestão passa a integrar o histórico autorizado. */
  analyzeDemand(id:string) {
    return this.http.post<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/assistente/analisar`,{},this.headers());
  }
  /** A decisão de autoatendimento é do solicitante, nunca da IA. */
  resolveByAI(id:string) {
    return this.http.patch<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/assistente/resolver`,{},this.headers());
  }
  detail(id:string) {return this.http.get<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}`,this.headers());}

  /** FormData permite enviar os anexos originais com os campos da demanda na mesma transação. */
  create(payload:DemandInput,files:File[]) {
    const form = new FormData();
    form.append('payload',JSON.stringify(payload));
    for(const file of files) form.append('files',file,file.name);
    return this.http.post<DemandDetail>(`${this.endpoint}/fluxo`,form,this.headers());
  }
  attach(id:string,files:File[]) {
    const form = new FormData();
    for(const file of files) form.append('files',file,file.name);
    return this.http.post<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/documentos`,form,this.headers());
  }
  assign(id:string,email:string) {
    return this.http.patch<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/atribuicao`,{lawyer_email:email},this.headers());
  }
  changeStatus(id:string,status:DemandStatus,note='') {
    return this.http.patch<DemandDetail>(`${this.endpoint}/${encodeURIComponent(id)}/status`,{status,note},this.headers());
  }
  /** O blob é lido pela API autenticada, sem link público para o diretório privado. */
  document(id:string,documentId:string) {
    return this.http.get(`${this.endpoint}/${encodeURIComponent(id)}/documentos/${encodeURIComponent(documentId)}/arquivo`,{responseType:'blob',...this.headers()});
  }
}
