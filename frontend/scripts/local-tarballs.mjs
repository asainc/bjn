/**
 * Valida arquivos .tgz baixados localmente pelo procedimento corporativo.
 * Entradas: frontend/local-packages/*.tgz e package-lock.json corporativo.
 * Saídas: relatório local com status e cache npm opcional, sem alterar manifestos.
 * Motivo: aproveitar tarballs aprovados e evitar tentar baixá-los de URLs duplicadas.
 */
import {readFileSync, readdirSync, existsSync, mkdirSync, writeFileSync} from 'node:fs';
import {resolve, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {readTarballIdentity, tarballIntegrity, lockIdentityMap} from './local-tarballs-core.mjs';
import {toCsv, collectArtifacts} from './governance-core.mjs';

const root = resolve(fileURLToPath(new URL('../', import.meta.url)));
const directory = resolve(root, 'local-packages');
const lockPath = resolve(root, 'package-lock.json');
const mode = process.argv.includes('--cache') ? 'cache' : 'check';
const hasLock = existsSync(lockPath);
const lock = hasLock ? JSON.parse(readFileSync(lockPath, 'utf8')) : null;
const known = hasLock ? lockIdentityMap(lock) : new Map();
const candidates = readdirSync(directory).filter(name => name.endsWith('.tgz')).sort();
const rows = [];
const cached = new Set();

/** Adiciona apenas o tarball validado ao cache padrão do npm (sem instalá-lo). */
function addCache(archive) {
  const cli = process.env.npm_execpath;
  if (!cli?.endsWith('.js')) throw new Error('Execute o cache pelo script npm run local:cache.');
  const result = spawnSync(process.execPath, [cli, 'cache', 'add', archive, '--ignore-scripts', '--no-audit', '--no-fund'], {
    cwd: root, stdio: 'pipe', encoding: 'utf8', timeout: 120000, windowsHide: true,
  });
  return result.status === 0 && !result.error;
}

for (const filename of candidates) {
  const fullPath = join(directory, filename);
  let identity = '', status = 'ARQUIVO_INVALIDO';
  try {
    const bytes = readFileSync(fullPath);
    const pkg = readTarballIdentity(bytes);
    identity = `${pkg.name}@${pkg.version}`;
    const match = known.get(identity);
    if (!hasLock) status = 'SEM_LOCK_NAO_VERIFICADO';
    else if (!match) status = 'FORA_DO_LOCK';
    else if (tarballIntegrity(bytes) !== match.integrity) status = 'SHA512_DIVERGENTE';
    else if (cached.has(identity)) status = 'DUPLICADO';
    else {
      status = mode === 'cache' ? (addCache(fullPath) ? 'ADICIONADO_AO_CACHE' : 'CACHE_FALHOU') : 'VALIDADO';
      if (status === 'VALIDADO' || status === 'ADICIONADO_AO_CACHE') cached.add(identity);
    }
  } catch { /* Não expõe conteúdo do pacote nem dados do terminal em logs de auditoria. */ }
  rows.push({filename, package: identity, status});
}
const expected = lock ? collectArtifacts(lock, {platform: 'win32', architecture: 'x64'}) : [];
const covered = expected.filter(pkg => cached.has(`${pkg.name}@${pkg.version}`));
const absent = expected.filter(pkg => !cached.has(`${pkg.name}@${pkg.version}`));
mkdirSync(resolve(root, 'reports'), {recursive: true});
writeFileSync(resolve(root, 'reports', 'local-tarballs.csv'), toCsv(rows, ['filename','package','status']), {mode: 0o600});
if (hasLock) {
  writeFileSync(resolve(root, 'reports', 'local-missing.csv'), toCsv(absent.map(({name,version,optional}) => ({name,version,optional})), ['name','version','optional']), {mode: 0o600});
}
console.log(`Pacotes locais inspecionados: ${rows.length}. Correspondências SHA-512: ${covered.length}/${expected.length}.`);
console.log('Relatórios: frontend/reports/local-tarballs.csv e, quando houver lock, local-missing.csv.');
if (!hasLock) {
  console.error('package-lock.json ausente: é necessário obtê-lo/gerá-lo pelo Nexus antes de validar integridade e instalar offline.');
  process.exitCode = 1;
} else if (!candidates.length) {
  console.error('Nenhum arquivo .tgz encontrado em frontend/local-packages/. Copie os downloads corporativos para lá.');
  process.exitCode = 1;
} else if (rows.some(row => ['ARQUIVO_INVALIDO','SHA512_DIVERGENTE','CACHE_FALHOU'].includes(row.status))) {
  console.error('Há arquivo inválido, integridade divergente ou falha de cache. Corrija antes de instalar.');
  process.exitCode = 1;
}
const outside = rows.filter(row => row.status === 'FORA_DO_LOCK' || row.status === 'DUPLICADO');
if (outside.length) console.warn(`${outside.length} arquivo(s) adicional(is)/duplicado(s) ignorado(s), sem instalar nem alterar o lock.`);
if (absent.length) console.log(`${absent.length} artefato(s) ainda precisam estar presentes no cache ou disponíveis pelo Nexus para a instalação completa.`);
