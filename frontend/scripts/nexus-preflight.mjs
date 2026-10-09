/**
 * Consulta todas as versões exigidas pelo frontend no registry npm configurado.
 * Entradas: lockfile e configuração npm corporativa já existente no computador.
 * Saídas: CSV local com disponibilidade de metadados e, sob demanda, tarballs.
 * Segurança: nunca registra credenciais, não consulta registry público, não faz bypass do Nexus.
 */
import {spawnSync} from 'node:child_process';
import {readFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync, existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {collectArtifacts, toCsv} from './governance-core.mjs';
import {validateCorporateRegistry} from './validate-nexus-registry.mjs';

const root = resolve(fileURLToPath(new URL('../', import.meta.url)));
const mode = process.argv.includes('--artifacts') ? 'artifacts' : 'metadata';
const includeOptional = !process.argv.includes('--required-only');
const maxArg = process.argv.find(value => value.startsWith('--max='));
const max = maxArg ? Number(maxArg.split('=')[1]) : Infinity;
if (maxArg && (!Number.isSafeInteger(max) || max < 1)) throw new Error('--max deve ser inteiro positivo.');
// No Windows, npm.cmd requer shell; invocamos o CLI JS pelo Node para não abrir shell nem interpolar argumentos.
const npmExecutable = process.platform === 'win32' ? process.execPath : 'npm';
const npmPrefix = process.platform === 'win32' ? (() => {
  const cli = process.env.npm_execpath;
  if (!cli || !cli.endsWith('.js')) throw new Error('No Windows execute via npm run governance:probe ou governance:artifacts.');
  return [cli];
})() : [];
const cache = mkdtempSync(join(tmpdir(), 'nexus-preflight-'));

/** Executa npm sem shell e jamais devolve a saída bruta de erros potencialmente sensíveis. */
function runNpm(args, timeout = 45000) {
  const result = spawnSync(npmExecutable, [...npmPrefix, ...args], {
    encoding: 'utf8', cwd: root, timeout, maxBuffer: 1024 * 1024,
    env: {...process.env, npm_config_update_notifier: 'false'}, windowsHide: true,
  });
  return {ok: result.status === 0 && !result.error, stdout: result.stdout || '',
    status: classifyError(result)};
}

/** Classifica códigos conhecidos sem copiar mensagens do Nexus para artefatos. */
function classifyError(result) {
  if (result.error?.code === 'ETIMEDOUT' || result.signal) return 'TIMEOUT';
  const stderr = String(result.stderr || '');
  for (const code of ['E400', 'E401', 'E403', 'E404', 'ENOTFOUND', 'ECONNREFUSED', 'ECONNRESET', 'ETIMEDOUT', 'EINTEGRITY', 'CERT_HAS_EXPIRED', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE']) {
    if (stderr.includes(code) || stderr.includes(` ${code.slice(1)} `)) return code;
  }
  return 'ERRO_NAO_CLASSIFICADO';
}

/** Garante que o diagnóstico use exatamente o Nexus corporativo esperado. */
function checkedRegistry(raw) {
  return validateCorporateRegistry(raw);
}

/** Impede que um registry específico de escopo redirecione pacotes para fora do Nexus. */
function verifyScopeRegistries(artifacts, registry) {
  const scopes = [...new Set(artifacts.filter(row => row.name.startsWith('@')).map(row => row.name.split('/')[0]))];
  for (const scope of scopes) {
    const configured = runNpm(['config', 'get', `${scope}:registry`], 12000);
    if (!configured.ok) throw new Error(`Não foi possível verificar registry do escopo ${scope}.`);
    const value = configured.stdout.trim();
    if (value && value !== 'undefined' && value !== 'null' && checkedRegistry(value) !== registry) {
      throw new Error(`Registry do escopo ${scope} difere do registry corporativo. Revise a configuração npm.`);
    }
  }
}

/** Compara a integridade declarada no Nexus com a referência versionada no lockfile. */
function probe(artifact, registry) {
  const spec = `${artifact.name}@${artifact.version}`;
  const shared = ['--registry', registry, '--cache', cache, '--prefer-online', '--fetch-retries=0', '--fetch-timeout=15000'];
  const metadata = runNpm(['view', spec, 'dist.integrity', '--json', ...shared]);
  if (!metadata.ok) return {status: `METADATA_${metadata.status}`};
  let integrity;
  try { integrity = JSON.parse(metadata.stdout.trim()); } catch { return {status: 'METADATA_INVALIDA'}; }
  if (integrity !== artifact.integrity) return {status: 'INTEGRIDADE_DIVERGENTE'};
  if (mode === 'metadata') return {status: 'METADADOS_DISPONIVEIS'};
  // cache add baixa o pacote para um cache isolado, sem instalar no projeto nem executar lifecycle scripts.
  const tarball = runNpm(['cache', 'add', spec, ...shared], 90000);
  return {status: tarball.ok ? 'ARTEFATO_DISPONIVEL' : `ARTEFATO_${tarball.status}`};
}

try {
  const current = runNpm(['config', 'get', 'registry'], 12000);
  if (!current.ok) throw new Error('Não foi possível ler o registry npm configurado.');
  const registry = checkedRegistry(current.stdout);
  const lockPath = resolve(root, 'package-lock.json');
  if (!existsSync(lockPath)) throw new Error('package-lock.json ausente. Execute npm run nexus:lock antes do preflight.');
  const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
  const all = collectArtifacts(lock, {includeOptional});
  verifyScopeRegistries(all, registry);
  const selected = all.slice(0, max);
  const rows = [];
  console.log(`Iniciando consulta ${mode} de ${selected.length}/${all.length} artefatos no registry corporativo configurado.`);
  for (const [index, artifact] of selected.entries()) {
    const {status} = probe(artifact, registry);
    rows.push({name: artifact.name, version: artifact.version, optional: artifact.optional,
      hasInstallScript: artifact.hasInstallScript, status});
    if ((index + 1) % 25 === 0 || index === selected.length - 1) console.log(`Verificados: ${index + 1}/${selected.length}.`);
  }
  mkdirSync(resolve(root, 'reports'), {recursive: true});
  const output = resolve(root, 'reports', 'nexus-preflight.csv');
  writeFileSync(output, toCsv(rows, ['name', 'version', 'optional', 'hasInstallScript', 'status']), {mode: 0o600});
  const expected = mode === 'metadata' ? 'METADADOS_DISPONIVEIS' : 'ARTEFATO_DISPONIVEL';
  const failures = rows.filter(row => row.status !== expected);
  console.log(`Resultado: ${rows.length - failures.length}/${rows.length} verificações bem-sucedidas; relatório: frontend/reports/nexus-preflight.csv.`);
  if (selected.length < all.length) console.warn('ATENÇÃO: execução parcial, não valida toda a árvore.');
  if (failures.length) {
    console.error(`${failures.length} ocorrência(s) requerem verificação pelo time responsável pelo Nexus.`);
    process.exitCode = 1;
  }
} finally {
  // Exclui o cache isolado que contém bytes de pacotes; não toca o cache global do desenvolvedor.
  rmSync(cache, {recursive: true, force: true});
}
