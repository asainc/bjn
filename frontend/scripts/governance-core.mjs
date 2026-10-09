/**
 * Funções puras para inventário e homologação de dependências npm.
 * Entradas: conteúdo dos manifestos e do catálogo de aprovação.
 * Saídas: artefatos normalizados e pendências sem dados de autenticação.
 * Motivo: centralizar regras e permitir testes sem acessar o Nexus.
 */
import {createHash} from 'node:crypto';

/** Identifica o nome real mesmo quando uma biblioteca aparece aninhada no lockfile. */
export function packageNameFromPath(path) {
  const segments = path.split('/node_modules/').at(-1).replace(/^node_modules\//, '').split('/');
  return segments[0].startsWith('@') ? `${segments[0]}/${segments[1]}` : segments[0];
}

/** Preserva cada versão distinta; evita exigir duas aprovações para o mesmo tarball. */
export function collectArtifacts(lock, {includeOptional = true, platform = 'win32', architecture = 'x64'} = {}) {
  if (lock?.lockfileVersion !== 3 || !lock.packages?.['']) throw new Error('package-lock.json v3 inválido.');
  const unique = new Map();
  for (const [path, pkg] of Object.entries(lock.packages)) {
    if (!path) continue;
    const name = packageNameFromPath(path);
    if (!pkg.version || typeof pkg.integrity !== 'string' || !pkg.integrity.startsWith('sha512-')) {
      throw new Error(`Artefato sem versão ou integridade SHA-512: ${path}`);
    }
    if (!includeOptional && pkg.optional) continue;
    const supported = (values, current) => !Array.isArray(values) ||
      (!values.includes(`!${current}`) && (values.every(value => value.startsWith('!')) || values.includes(current)));
    if (!supported(pkg.os, platform) || !supported(pkg.cpu, architecture)) continue;
    const key = `${name}@${pkg.version}`;
    const previous = unique.get(key);
    if (previous && previous.integrity !== pkg.integrity) throw new Error(`Integridades divergentes para ${key}.`);
    if (previous) {
      previous.optional = previous.optional && Boolean(pkg.optional);
      previous.paths.push(path);
    } else {
      unique.set(key, {name, version: pkg.version, integrity: pkg.integrity, optional: Boolean(pkg.optional),
        hasInstallScript: Boolean(pkg.hasInstallScript), paths: [path]});
    }
  }
  return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
}

/** Gera checksum reprodutível do lockfile original (não de sua representação reconstruída). */
export function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

/**
 * Confere aprovação exata por pacote, versão e hash; um catálogo sem evidência não libera instalação.
 * Formato: {schema_version:1, packages:[{name,version,integrity,status:'approved'}]}.
 */
export function evaluateApprovals(artifacts, approvals) {
  if (approvals?.schema_version !== 1 || !Array.isArray(approvals.packages)) throw new Error('Catálogo de aprovações inválido.');
  const known = new Map();
  for (const row of approvals.packages) {
    if (typeof row.name !== 'string' || typeof row.version !== 'string' || typeof row.integrity !== 'string') {
      throw new Error('Aprovação com nome, versão ou integridade ausente.');
    }
    const key = `${row.name}@${row.version}`;
    if (known.has(key)) throw new Error(`Aprovação duplicada: ${key}`);
    known.set(key, row);
  }
  return artifacts.map(artifact => {
    const row = known.get(`${artifact.name}@${artifact.version}`);
    const status = !row ? 'PENDENTE' : row.status !== 'approved' ? 'NAO_APROVADO' :
      row.integrity !== artifact.integrity ? 'INTEGRIDADE_DIVERGENTE' : 'APROVADO';
    return {name: artifact.name, version: artifact.version, status, optional: artifact.optional};
  });
}

/** Codifica células de CSV sem permitir que planilhas executem fórmulas ao abrir o inventário. */
export function csvCell(value) {
  const text = String(value ?? '');
  const safe = /^[\s]*[=+@\-\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
}

/** Fornece um CSV explícito para envio controlado à governança. */
export function toCsv(rows, headers) {
  return [headers.map(csvCell).join(','), ...rows.map(row => headers.map(header => csvCell(row[header])).join(','))].join('\n') + '\n';
}
