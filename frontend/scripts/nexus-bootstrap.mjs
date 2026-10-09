/**
 * Resolução de lock e instalação através do registry corporativo autorizado.
 * Entradas: manifesto, configuração do npm e lockfile previamente versionado.
 * Saídas: lockfile reprodutível ou instalação oficial; nunca sobrescreve lock sem permissão.
 */
import {spawnSync} from 'node:child_process';
import {existsSync, readFileSync, rmSync, copyFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {validateCorporateRegistry, readConfiguredRegistry} from './validate-nexus-registry.mjs';
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const lockPath = resolve(root, 'package-lock.json');
const cli = process.env.npm_execpath;
if (!cli?.endsWith('.js')) throw new Error('Execute via npm run nexus:lock ou npm run install:corporate.');
function runScript(file,args = []) {
  const r = spawnSync(process.execPath, [resolve(here,file),...args], {cwd:root,stdio:'inherit',timeout:20*60*1000});
  if (r.status !== 0 || r.error) throw new Error(`${file}: validação não concluída.`);
}
function runNpm(args) {
  const r = spawnSync(process.execPath, [cli, ...args], {cwd:root,stdio:'inherit',timeout:20*60*1000,windowsHide:true});
  if (r.status !== 0 || r.error) throw new Error('npm não concluiu a etapa. Verifique o erro original e o acesso corporativo.');
}
runScript('validate-environment.mjs');
const registry = validateCorporateRegistry(readConfiguredRegistry());
console.log(`Nexus validado: ${new URL(registry).hostname}${new URL(registry).pathname}`);
if (process.argv.includes('--lock-only')) {
  const rebuild = process.argv.includes('--rebuild');
  if (existsSync(lockPath) && !rebuild) {
    throw new Error('Já existe package-lock.json. Valide com npm run verify:lock; use npm run nexus:lock -- --rebuild somente se precisar regenerar.');
  }
  const backup = resolve(tmpdir(), `judicial-lock-backup-${process.pid}.json`);
  const hadLock = existsSync(lockPath);
  if (hadLock) { copyFileSync(lockPath,backup); rmSync(lockPath); }
  try {
    runNpm(['install','--package-lock-only','--ignore-scripts','--strict-peer-deps','--include=optional','--no-audit','--no-fund',`--registry=${registry}`]);
    if (!existsSync(lockPath)) throw new Error('npm não produziu package-lock.json.');
    const lock = JSON.parse(readFileSync(lockPath,'utf8'));
    if (lock.lockfileVersion !== 3) throw new Error('O lockfile precisa ter formato v3.');
    runScript('validate-dependency-lock.mjs');
    console.log('Novo lock validado. Revise e versione-o conforme governança.');
  } catch (error) {
    if (hadLock) { copyFileSync(backup,lockPath); console.error('Lock anterior restaurado após a falha.'); }
    else rmSync(lockPath,{force:true});
    throw error;
  } finally { if (hadLock) rmSync(backup,{force:true}); }
} else if (process.argv.includes('--install')) {
  if (!existsSync(lockPath)) throw new Error('package-lock.json ausente. Gere pelo Nexus antes de instalar.');
  runScript('validate-dependency-lock.mjs');
  runScript('nexus-preflight.mjs',['--artifacts']);
  runNpm(['ci','--include=optional','--strict-peer-deps','--no-audit','--no-fund','--replace-registry-host=never',`--registry=${registry}`]);
  runScript('validate-native-rollup.mjs');
  console.log('Instalação concluída; ainda requer aprovação corporativa aplicável.');
} else throw new Error('Use --lock-only ou --install.');
