/** Verificações estruturais, inclusive quando o Angular ainda não está instalado. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const file=(relative)=>fs.readFileSync(path.join(root,relative),'utf8');

test('rotas de demandas não substituem as rotas de minutas e AI Ready',()=>{
  const routes=file('src/app/app.routes.ts');
  for(const route of ["path: 'bjn'", "path: 'ai-ready'", "path: 'bjn/demandas/nova'", "path: 'bjn/demandas/:id'", "path: 'bjn/demandas'"]){assert.ok(routes.includes(route),route);}
});
test('cadastro valida campos, permite envolvidos e mantém anexos com a demanda',()=>{
  const view=file('src/app/bjn/demands/demand-new.component.ts');
  for(const text of ['Departamento Solicitante','Área de consulta','Natureza do serviço','Descrição da consulta','Envolvidos','Anexos','Resumo da demanda','this.api.create']) assert.ok(view.includes(text),text);
});
test('acompanhamento exibe responsável, histórico, visualizador e novos documentos',()=>{
  const view=file('src/app/bjn/demands/demand-detail.component.ts');
  for(const text of ['Aguardando distribuição','Histórico de acompanhamento','Central de documentos','demand-pdf-frame','demand-image-area','this.api.attach','this.api.assign','this.api.changeStatus']) assert.ok(view.includes(text),text);
});
test('upload e prévia usam API autenticada e não endereço público de diretório',()=>{
  const client=file('src/app/core/bjn-demand-api.service.ts');
  assert.ok(client.includes('responseType:\'blob\''));
  assert.ok(client.includes('FormData()'));
  assert.ok(!client.includes('localhost:8000'));
});

test('cadastro não fica desabilitado silenciosamente e exibe pendências acionáveis',()=>{
  const view=file('src/app/bjn/demands/demand-new.component.ts');
  assert.ok(view.includes('[disabled]="sending()"'), 'envio só é desabilitado durante o processamento');
  assert.ok(!view.includes('[disabled]="sending() || !valid()"'), 'restrições invisíveis devem ser removidas');
  for(const fragment of ['validationIssues()', 'demand-validation-box', 'focusField(issue.fieldId)', 'error.set(friendlyApiError(cause))']){
    assert.ok(view.includes(fragment),fragment);
  }
});
test('envolvidos opcionais em branco são excluídos da requisição e os incompletos são explicados',()=>{
  const view=file('src/app/bjn/demands/demand-new.component.ts');
  assert.ok(view.includes('completedInvolved()'));
  assert.ok(view.includes('this.completedInvolved().map(person=>({...person}))'));
  assert.ok(view.includes('anyContent&&person.name.trim().length<2'));
  assert.ok(view.includes('informe o nome ou remova a linha incompleta'));
});
test('mensagens de falhas HTTP diferenciam autorização, conexão e serviços desatualizados',()=>{
  const errors=file('src/app/bjn/demands/demand-ui.ts');
  for(const fragment of ['status===0','status===401||status===403','status===404','status===415','status===422']){
    assert.ok(errors.includes(fragment),fragment);
  }
});

test('central de documentos tem minimizar e expandir com conteúdo condicionado', () => {
  const source = file('src/app/bjn/demands/demand-detail.component.ts');
  assert.match(source, /documentsExpanded=signal\(true\)/);
  assert.match(source, /aria-expanded/);
  assert.match(source, /Minimizar/);
  assert.match(source, /Expandir/);
  assert.match(source, /@if\(documentsExpanded\(\)\)/);
});

test('IA usa descrição do rascunho e não cadastra demanda automaticamente', () => {
  const component = file('src/app/bjn/demands/demand-new.component.ts');
  const api = file('src/app/core/bjn-demand-api.service.ts');
  assert.match(component, /analyzeDescription\(\)/);
  assert.match(component, /analyzeDraft\(text\)/);
  assert.match(component, /Minha dúvida foi resolvida — não cadastrar/);
  assert.match(api, /\/assistente\/analisar/);
  assert.match(api, /resolveByAI/);
});

test('distribuição contém opção de advogado de testes e resolução depende de confirmação', () => {
  const source = file('src/app/bjn/demands/demand-detail.component.ts');
  assert.match(source, /lawyer_options/);
  assert.match(source, /confirmAIResolution/);
  assert.match(source, /resolveByAI/);
});


test('upload dispara análise de documentos e usa natureza para o prompt, sem publicação automática',()=>{
  const create=file('src/app/bjn/demands/demand-new.component.ts');
  const detail=file('src/app/bjn/demands/demand-detail.component.ts');
  const api=file('src/app/core/bjn-demand-api.service.ts');
  for(const expected of ['onNatureChanged', 'analyzeSelectedDocuments', 'this.api.analyzeUploadedDocuments', 'documentSuggestion()', 'Sugestão da IA']) assert.ok(create.includes(expected),expected);
  assert.ok(detail.includes('document_ai_suggestion'));
  assert.ok(detail.includes('reanalisar') || detail.includes('Reanalisar'));
  assert.ok(api.includes('/assistente/analisar-documentos'));
  assert.ok(api.includes('requesting_department:string'));
  assert.ok(!create.includes('Departamento jurídico'));
});
