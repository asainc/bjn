/** Contratos HTTP do AI Ready. Mantidos explícitos para facilitar revisão e manutenção. */
export type Party = {
  nome: string;
  papel: string;
};

export type TimelineEvent = {
  data: string | null;
  titulo: string;
  descricao: string;
  categoria: 'ajuizamento' | 'citacao' | 'manifestacao' | 'prova' | 'audiencia' | 'decisao' | 'recurso' | 'cumprimento' | 'outro';
  documento: string;
  pagina: number | null;
  confianca: 'alta' | 'media' | 'baixa';
};

export type DocumentSummary = {
  identificador: string;
  nome: string;
  paginas: number;
  paginas_utilizaveis: number;
  tamanho_bytes: number;
  qualidade_textual: 'boa' | 'parcial' | 'insuficiente';
  alertas: string[];
};

export type ProcessOverview = {
  numero_processo: string | null;
  classe_processual: string | null;
  tribunal: string | null;
  unidade_judicial: string | null;
  fase_processual: string | null;
  assunto_principal: string | null;
  valor_causa: string | null;
  ultima_data_relevante: string | null;
  partes: Party[];
  resumo: string;
  pedidos: string[];
  fatos_controvertidos: string[];
  pontos_atencao: string[];
  proximas_acoes_sugeridas: string[];
};

export type ProcessWorkspaceResponse = {
  workspace_id: string;
  gerado_em: string;
  processo: ProcessOverview;
  linha_tempo: TimelineEvent[];
  documentos: DocumentSummary[];
  aviso: string;
};

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type ChatResponse = {
  resposta: string;
  aviso: string;
};

export type AiReadyConfiguration = {
  provedor: 'bradesco_iagen';
  geracao_texto_configurada: boolean;
  chat_qa_configurado: boolean;
  limite_arquivos: number;
  limite_mb_por_arquivo: number;
  limite_total_mb: number;
};

export type Health = {
  status: string;
  versao_api: string;
};
