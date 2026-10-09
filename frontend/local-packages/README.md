# Pacotes npm baixados pelo fluxo corporativo

Coloque aqui os arquivos `.tgz` baixados do **Nexus autorizado** usando o procedimento corporativo. Este projeto não fornece nem redistribui esses binários. Não renomeie os arquivos: o verificador lê `package/package.json` do pacote e ignora o nome externo para identificar nome e versão.

O fluxo seguro exige um `package-lock.json` corporativo previamente gerado ou fornecido pelo repositório aprovado. O script `npm run local:check` identifica pacotes, verifica SHA-512 contra esse lockfile e informa a cobertura; `npm run local:cache` somente adiciona ao cache do npm tarballs com nome, versão e integridade coincidentes. `npm run local:install` usa `npm ci --offline --include=optional`. Pacotes ausentes do conjunto local **e do cache** impedem a instalação offline; não se criam versões substitutas.

Não inclua arquivos de produção, credenciais, certificados pessoais ou quaisquer dados de processo nesta pasta. A governança corporativa deve validar os artefatos, licenças, CVEs e scripts de instalação antes do uso.
