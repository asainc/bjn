/** Testes estruturais sem navegador ou dependências npm corporativas. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=(p)=>fs.readFileSync(path.join(root,'src/app',p),'utf8');

test('cadastro exige triagem e apresenta cinco opções de encaminhamento',()=>{
  const view=source('bjn/demands/demand-new.component.ts');
  for(const option of ['PROCESSO_COM_BANCO','OFICIO_DELEGACIA','INTIMACAO_DELEGACIA','OFICIO_SEM_BANCO','OUTRAS'])assert.ok(view.includes(option),option);
  assert.ok(view.includes('triageComplete()'));
  assert.ok(view.includes('validateTriage()'));
  assert.ok(view.includes('triage_proof'));
});

test('formulário replica naturezas e comunica obrigatoriedade de anexo',()=>{
  const view=source('bjn/demands/demand-new.component.ts');
  for(const label of ['Inventário','Alvará','Curatela','Procuração','Pareceres em geral'])assert.ok(view.includes(label));
  for(const field of ['client-cpf','client-name','agency','requester-email'])assert.ok(view.includes(field));
  assert.ok(view.includes('exige pelo menos um documento anexo'));
});

test('parecer exige confirmação humana antes de publicar',()=>{
  const detail=source('bjn/demands/demand-detail.component.ts');
  for(const fragment of ['generateDraft()','publishOpinion()','humanReviewed','can_review_opinion','can_review_competence','Central de documentos'])assert.ok(detail.includes(fragment),fragment);
});

test('busca protege identificador pessoal com requisição POST',()=>{
  const api=source('core/bjn-demand-api.service.ts');
  assert.ok(api.includes('http.post<{items:DemandSummary[]}>'));
  assert.ok(api.includes('/consulta'));
  assert.ok(!api.includes('HttpParams'));
});

test('componentes Angular modificados preservam sintaxe Typescript',()=>{
  const ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript');
  for(const item of ['core/bjn-demand-api.service.ts','bjn/demands/demand-ui.ts','bjn/demands/demand-new.component.ts','bjn/demands/demand-detail.component.ts','bjn/demands/demand-list.component.ts']){
    const output=ts.transpileModule(source(item),{fileName:item,reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}});
    const errors=(output.diagnostics||[]).filter(e=>e.category===ts.DiagnosticCategory.Error);
    assert.equal(errors.length,0,`${item}: ${errors.map(e=>e.messageText).join('; ')}`);
  }
});

test('publicação em desenvolvimento oferece troca de perfil apenas ao advogado fictício designado',()=>{
  const detail=source('bjn/demands/demand-detail.component.ts');
  const api=source('core/bjn-demand-api.service.ts');
  for(const fragment of ['Testar como advogado designado','Voltar ao administrador','startDemoReviewer(','stopDemoReviewer(','canSwitchToDemoReviewer(','demo_session_available']){
    assert.ok(detail.includes(fragment),fragment);
  }
  assert.ok(api.includes('option.demo && option.email===email'));
  assert.ok(api.includes('X-Authenticated-Role'));
  assert.ok(api.includes('disableDemoReviewer()'));
  assert.ok(!api.includes('localStorage'));
});

test('publicação é independente da geração por IA e orienta sobre revisão mínima',()=>{
  const detail=source('bjn/demands/demand-detail.component.ts');
  assert.ok(detail.includes('Informe ao menos 40 caracteres'));
  assert.ok(detail.includes('Marque a confirmação de revisão humana'));
  assert.ok(detail.includes('SEM_EMAIL_CADASTRADO'));
  assert.ok(detail.includes('this.api.publishOpinion(this.demandId,this.finalOpinion,true)'));
});
