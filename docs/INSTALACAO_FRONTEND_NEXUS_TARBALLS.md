# Frontend no computador corporativo: Nexus + pacotes `.tgz` locais

**Baseline documentado:** Windows x64; Node.js 22.12.0; npm 10.9.0; Angular 21.2.19. Os valores são requisitos deste pacote, não uma declaração de homologação pelo banco.

## 1. Por que este fluxo existe

Na execução relatada, o Nexus devolveu URLs contendo duas vezes `/repository/jurianl-npm-central/` e o Angular falhou ao iniciar sem `@rollup/rollup-win32-x64-msvc`. Os prints mostram vários `.tgz` já baixados no computador corporativo. O arquivo `.tgz` e o registro de aprovação **não foram fornecidos aqui**; por isso, o projeto inclui inspeção local, sem embutir esses binários ou inventar SHA-512.

O `package-lock.json` **não está no pacote** e não deve ser fabricado com URLs do Nexus ou hashes não conferidos. O responsável deve usar um lock corporativo existente e íntegro, gerado dentro do ambiente autorizado, ou gerar um novo pelo Nexus quando a resolução de metadados estiver funcionando. Se `ajv` ou outra dependência não estiver disponível no catálogo, o lock *não poderá ser gerado integralmente* apenas a partir dos poucos `.tgz` baixados. Nesse caso, é necessário o pacote oficial e o metadado correspondente no repositório aprovado, ou um lock corporativo já validado pela TI.

## 2. Modificações deliberadas no frontend

| Componente | Valor | Justificativa | Condição de validação |
|---|---|---|---|
| Angular (pacotes diretos) | `21.2.19` | Alinhar versões Angular à máquina informada. | Resolver e compilar no Nexus. |
| Node / npm | `22.12.0` / `10.9.0` | Reproduzir ambiente. | `npm run env:check`. |
| Rollup | `4.60.1` (override oficial) | Versão efetivamente instalada, conforme captura `npm ls rollup`. | Conferir compatibilidade do Vite resolvido. |
| Binding Windows Rollup | `@rollup/rollup-win32-x64-msvc@4.60.1` (devDependency direta) | Evitar omissão acidental da dependência opcional necessária ao Windows. | Confirmar pacote oficial e hash idêntico ao lock. |
| readdirp | `4.1.2` somente sob `chokidar` | Usar a versão 4.x informada, sem forçar outros consumidores. | Confirmar faixas declaradas no lock. |
| PostCSS | `8.5.25` (override) | Versão informada como disponível. | Confirmar faixas declaradas pelos consumidores. |

**Atenção:** declarar o binding Windows como dependência direta torna este procedimento específico para Windows x64. Não use este mesmo manifesto para instalação Linux/macOS sem rever a dependência específica da plataforma. Os overrides são exceções documentadas, não evidência de aprovação corporativa.

## 3. Passo a passo (CMD, sem permissões administrativas)

Na pasta raiz extraída do projeto, abra o CMD e execute:

```cmd
cd frontend
node --version
npm --version
npm run env:check
npm config get registry
npm run nexus:check
```

Verifique o repositório **realmente autorizado** por sua organização. O `.npmrc` do frontend deixou de usar `replace-registry-host=always`: agora usa `never` para não reescrever URLs Nexus já resolvidas. Se metadados do próprio Nexus contiverem o caminho duplicado, a configuração do servidor ainda precisará ser corrigida; a aplicação não contorna permissões.

Se você tem um `package-lock.json` corporativo da mesma árvore, coloque-o em `frontend/package-lock.json` e execute:

```cmd
npm run verify:lock
npm run nexus:diagnose
```

A validação exige que os artefatos estejam no Nexus correto, sem a duplicação `/repository/.../repository/.../`, com integridade SHA-512 e com a versão do Rollup igual à do binding. **Não execute `npm ci` com um lock antigo divergente.**

Se não houver lockfile, a TI deve disponibilizar o catálogo de metadados para todas as dependências; quando estiver íntegro, gere o lock através do Nexus:

```cmd
npm run nexus:lock
```

Se um lock já existir e você desejar substituí-lo deliberadamente após revisar as diferenças, execute `npm run nexus:lock -- --rebuild`. Caso a resolução falhe, o script restaura o lock anterior. Não apague o lockfile para tentar resolver erros `400`/`403` sem antes examinar a URL e o pacote.

## 4. Copiar os pacotes baixados localmente

Copie os **arquivos `.tgz` originais baixados pelo procedimento corporativo** para `frontend/local-packages/` (por exemplo, `ajv-8.20.0.tgz`, `rollup-4.60.1.tgz`, `rollup-rollup-win32-x64-msvc-4.60.1.tgz`). Esses nomes são apenas ilustrativos: o script extrai nome e versão de `package/package.json`, não do nome do arquivo.

```cmd
npm run local:check
```

O script produz `frontend/reports/local-tarballs.csv` e `frontend/reports/local-missing.csv`. Um tarball com **identidade e SHA-512 iguais ao lockfile** é marcado `VALIDADO`; um arquivo extra recebe `FORA_DO_LOCK` e é ignorado. Um tarball com hash divergente bloqueia a preparação. Sem lock, a inspeção não consegue atestar a integridade nem libera a instalação.

Depois:

```cmd
npm run local:cache
npm run local:install
npm run native:check
npm run build
npm start
```

`local:cache` adiciona somente tarballs validados ao cache npm (não altera `package.json`, não adiciona dependências diretas e não executa scripts de instalação). `local:install` faz `npm ci --offline --include=optional` e falha se faltar qualquer dependência necessária **no cache**, mesmo que alguns `.tgz` estejam disponíveis na pasta. A lista `local-missing.csv` mostra ausência **na pasta**, não necessariamente ausência no cache existente. A instalação pode executar scripts de pós-instalação dos pacotes oficiais: isso deve seguir a política de execução aprovada.

**Evite `npm install ./arquivo.tgz` na raiz do projeto:** o comando pode alterar `package.json`/`package-lock.json` e gerar dependências `file:` dependentes do caminho de uma máquina. O procedimento de cache mantém a resolução declarada no lock. O cache npm é transitório; não substitui o repositório corporativo, a aprovação ou o versionamento do lock.

## 5. Se algo ainda falhar

| Sintoma | Verificação / ação |
|---|---|
| `Module not found @rollup/rollup-win32-x64-msvc` | `npm run native:check`. Verificar tarball oficial **4.60.1** e presença do binding no lock; não misturar versões. |
| `E400` com `/repository/.../repository/.../` | `npm run nexus:diagnose`. Se a URL duplicada vier do `npm view ... dist.tarball`, acionar o administrador do Nexus. |
| `ajv` indisponível em qualquer versão | O lock não pode ser resolvido do zero somente com `npm view`; solicitar versão/metadados oficiais no Nexus ou lock corporativo completo aprovado. |
| `EPERM` ao limpar `node_modules` | Fechar `ng serve`, processos Node do projeto e editores; reiniciar se necessário. Não desativar proteções corporativas. |
| `ENOTCACHED` no `npm ci --offline` | Arquivo transitivo ainda não consta no cache; solicitar seu `.tgz` oficial autorizado. |
| `EINTEGRITY` | Não ignorar a checagem nem editar o hash. Verificar proveniência do download com a TI. |

## 6. Validação e governança

Use `npm run governance:check` apenas com um catálogo de aprovações por nome, versão e integridade **fornecido pelo banco**. Ser oficial, estar no cache ou ter o hash correto **não significa** estar homologado. Antes de publicar: avaliação de licenças, SCA/CVEs, scripts de instalação e teste `npm run build` no computador alvo.

Este procedimento altera somente a instalação de dependências do frontend. Não inclua PDFs reais de produção, credenciais ou outros dados sensíveis no repositório ou em pacotes locais.
