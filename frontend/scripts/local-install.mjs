/**
 * Orquestra instalação offline usando somente o lockfile e o cache npm local.
 * Entrada: lockfile corporativo e tarballs já carregados em cache.
 * Saída: node_modules reprodutível ou erro de cache/artefato ausente.
 */
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {existsSync} from 'node:fs';
const root = resolve(fileURLToPath(new URL('../', import.meta.url)));
const cli = process.env.npm_execpath;
if (!cli?.endsWith('.js')) throw new Error('Execute pelo comando npm run local:install.');
if (!existsSync(resolve(root, 'package-lock.json'))) throw new Error('package-lock.json ausente. Gere ou importe o lock corporativo primeiro.');
function run(script, args = []) {
  const result = spawnSync(process.execPath, [resolve(root, 'scripts', script), ...args], {cwd: root, stdio: 'inherit', timeout: 120000});
  if (result.status !== 0 || result.error) throw new Error(`${script}: verificação não concluída.`);
}
run('validate-dependency-lock.mjs');
run('local-tarballs.mjs', ['--cache']);
console.log('Instalando somente do cache npm. Pacotes transitivos não presentes no cache impedirão a instalação.');
const result = spawnSync(process.execPath, [cli, 'ci', '--offline', '--include=optional', '--no-audit', '--no-fund', '--replace-registry-host=never'], {
  cwd: root, stdio: 'inherit', timeout: 20 * 60 * 1000, windowsHide: true,
});
if (result.error || result.status !== 0) {
  throw new Error('Instalação offline incompleta: confira o primeiro artefato ausente, o cache npm e o lockfile. Nenhuma versão foi substituída.');
}
run('validate-native-rollup.mjs');
console.log('Instalação offline concluída, incluindo o binding Windows, na plataforma aplicável.');
