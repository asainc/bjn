/** Textos de apresentação; status emitidos apenas pelo backend. */
import {DemandStatus} from '../../core/bjn-demand-api.service';
export const demandStatusLabels:Record<DemandStatus,string> = {
  RECEBIDA:'Recebida', EM_TRIAGEM:'Em triagem', EM_ANALISE:'Em análise',
  AGUARDANDO_INFORMACOES:'Aguardando informações', CONCLUIDA:'Concluída', CANCELADA:'Cancelada', RESOLVIDA_IA:'Resolvida por autoatendimento',
  TRIAGEM_ADMINISTRATIVA:'Triagem administrativa',ENCAMINHADA_AREA:'Encaminhada à área competente',PARECER_EM_REVISAO:'Parecer em revisão',
};
export const selectableStatuses:DemandStatus[] = [
  'RECEBIDA','EM_TRIAGEM','EM_ANALISE','AGUARDANDO_INFORMACOES','CONCLUIDA','CANCELADA','RESOLVIDA_IA','TRIAGEM_ADMINISTRATIVA','ENCAMINHADA_AREA','PARECER_EM_REVISAO',
];
export function readableDate(value:string):string {
  if(!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short'}).format(parsed);
}
export function readableSize(bytes:number):string {
  return bytes < 1024*1024 ? `${Math.max(1,Math.round(bytes/1024))} KB` : `${(bytes/1024/1024).toFixed(1)} MB`;
}
export function friendlyApiError(error:unknown):string {
  /** Restringe os detalhes ao código HTTP e a mensagens controladas pela API. */
  const cause=error as {status?:number; error?:{message?:string; request_id?:string; fields?:{message?:string}[]}}|null;
  const status=cause?.status;
  const code=(cause?.error as {code?:string}|undefined)?.code;
  if(code?.startsWith('AI_'))return cause?.error?.message || 'A sugestão da IA não está disponível. O atendimento jurídico permanece acessível.';
  const serverMessage=cause?.error?.message;
  const requestId=cause?.error?.request_id;
  if(status===0) return 'Não foi possível conectar ao servidor. Verifique a conexão e se o backend está em execução.';
  if(status===401||status===403) return 'Sua sessão não está autorizada para esta operação. Refaça a autenticação ou solicite liberação de acesso.';
  if(status===404) return 'O serviço de demandas não foi encontrado. Verifique se a versão atualizada do backend está em execução.';
  if(status===413) return 'O arquivo excede o limite de tamanho permitido.';
  if(status===415) return 'O arquivo enviado não é válido. Utilize PDF, PNG ou JPEG de até 15 MB.';
  if(status===422){
    const details=cause?.error?.fields?.map(item=>item.message).filter((message):message is string=>Boolean(message)).slice(0,3);
    return details?.length ? `${serverMessage || 'Revise os campos informados.'} ${details.join(' ')}` : (serverMessage || 'Existem dados inválidos. Revise o preenchimento dos campos.');
  }
  if(status && status>=500) return `O servidor não conseguiu concluir o cadastro.${requestId ? ' Identificador: '+requestId : ''} Contate o suporte se persistir.`;
  return serverMessage || 'Não foi possível concluir a solicitação. Tente novamente ou contate o suporte.';
}
