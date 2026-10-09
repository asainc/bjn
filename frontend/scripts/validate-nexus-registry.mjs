/**
 * Confere a origem corporativa e o caminho EXATO do registry npm configurado.
 * Entrada: URL do `npm config get registry` ou NPM_CONFIG_REGISTRY.
 * Saída: URL canônica segura ou erro identificável, sem expor credenciais.
 * Motivo: aceitar repositórios corporativos diferentes sem repetir /repository/.../.
 */
import {spawnSync} from 'node:child_process';

const CORPORATE_HOST = 'nexusrepository.bradesco.com.br';

/** Normaliza somente a barra final; não cria nem duplica segmentos do repositório. */
export function normalizeRegistry(value) {
  let url;
  try { url = new URL(String(value ?? '').trim()); }
  catch { throw new Error('Registry npm inválido: informe uma URL HTTPS corporativa.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) {
    throw new Error('O registry deve ser HTTPS e não deve conter credenciais, query ou fragmento.');
  }
  const segments = url.pathname.split('/').filter(Boolean);
  if (segments.length !== 2 || segments[0] !== 'repository' || !/^[\w.-]+$/.test(segments[1])) {
    throw new Error('Caminho do Nexus inválido: esperado /repository/<repositorio>/, sem prefixos duplicados.');
  }
  url.pathname = `/repository/${segments[1]}/`;
  return url;
}

/** Rejeita o npm público e confere o repositório exato quando declarado pela organização. */
export function validateCorporateRegistry(value, {
  expectedHost = process.env.CORPORATE_NPM_HOST || CORPORATE_HOST,
  expectedPath = process.env.CORPORATE_NPM_PATH || '',
} = {}) {
  const url = normalizeRegistry(value);
  if (url.hostname.toLowerCase() !== expectedHost.toLowerCase()) {
    throw new Error('Registry fora do domínio corporativo autorizado.');
  }
  if (expectedPath && url.pathname !== normalizeRegistry(`https://${expectedHost}${expectedPath}`).pathname) {
    throw new Error('O repositório npm configurado difere do caminho esperado pela organização.');
  }
  return url.toString();
}

/** Usa o próprio CLI npm carregado, evitando npm.cmd via execFile no Windows. */
export function npmCommand(args, options = {}) {
  const cli = process.env.npm_execpath;
  const command = cli && cli.endsWith('.js') ? process.execPath : process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const prefix = cli && cli.endsWith('.js') ? [cli] : [];
  const result = spawnSync(command, [...prefix, ...args], {
    encoding: 'utf8', timeout: 30000, windowsHide: true,
    shell: process.platform === 'win32' && !(cli && cli.endsWith('.js')),
    ...options,
  });
  if (result.error || result.status !== 0) {
    throw new Error('O comando npm não pôde consultar a configuração corporativa. Execute via npm run.');
  }
  return result.stdout?.trim() ?? '';
}

/** Obtém o registry efetivo após composição de configurações globais e locais. */
export function readConfiguredRegistry() {
  if (process.env.NPM_CONFIG_REGISTRY?.trim()) return process.env.NPM_CONFIG_REGISTRY.trim();
  return npmCommand(['config', 'get', 'registry']);
}

if (process.argv[1]?.endsWith('validate-nexus-registry.mjs')) {
  console.log(`Registry corporativo validado: ${validateCorporateRegistry(readConfiguredRegistry())}`);
}
