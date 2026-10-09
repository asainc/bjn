# Dependências npm corporativas — Windows x64 / Nexus / tarballs locais

O frontend utiliza Node.js `22.12.0`, npm `10.9.0`, Angular `21.2.19`, TypeScript `5.9.3` e RxJS `7.8.2`. O `package.json` fixa dependências diretas oficiais, um binding nativo Windows do Rollup e três exceções de resolução documentadas. **Isto não equivale à homologação pelo banco.**

## Exceções explícitas documentadas

- `rollup@4.60.1`, igual ao Rollup observado na captura `npm ls rollup`;
- `@rollup/rollup-win32-x64-msvc@4.60.1` como dependência de desenvolvimento direta para reduzir o risco de omissão pelo npm no Windows;
- `readdirp@4.1.2` somente na subárvore de `chokidar`;
- `postcss@8.5.25`.

Todas essas versões devem continuar dentro das faixas de dependência/peer efetivamente exigidas pela árvore que for resolvida. Outros pacotes (inclusive AJV, Browserslist, negociator e content-type) **não recebem versões substitutas inventadas**.

## Origem, integridade e cache

Os `.tgz` devem ser obtidos por meio do procedimento autorizado para o Nexus corporativo. O ZIP **não inclui os arquivos mostrados nas fotografias**, pois seus bytes não foram disponibilizados. Copie-os em `frontend/local-packages/`. Um `package-lock.json` completo, referente ao `package.json` atualizado, precisa ser obtido ou gerado pelo Nexus. Sem esse lock, não é possível verificar o SHA-512 dos `.tgz` ou usar `npm ci --offline` com garantia de reprodutibilidade. A ausência de metadados de `ajv` no Nexus, conforme relatado, pode impedir a criação de um lock novo mesmo quando há um tarball local.

Para não repetir o caminho `/repository/.../`, o arquivo `.npmrc` usa `replace-registry-host=never`, e `npm run verify:lock` rejeita tarballs com repositório duplicado. O script de validação aceita o caminho do Nexus que estiver oficialmente configurado (`/repository/jurianl-npm-central/` ou outro caminho corporativo), sem impor o caminho antigo.

**Fluxo completo, validações, comandos CMD, tratamento de erro e limitações:** [INSTALACAO_FRONTEND_NEXUS_TARBALLS.md](INSTALACAO_FRONTEND_NEXUS_TARBALLS.md).

Nenhuma versão publicada no npm é presumida aprovada pela governança. Confirme licença, vulnerabilidades, scripts de instalação, origem e disponibilidade de toda a árvore com a equipe responsável.
