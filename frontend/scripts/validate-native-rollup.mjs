/**
 * Detecta previamente a ausência do binding oficial Windows necessário ao Rollup.
 * Entrada: pacotes já instalados em node_modules.
 * Saída: confirmação ou orientação específica, sem modificar dependências.
 */
import {readFileSync} from 'node:fs';
const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
if (process.platform !== 'win32' || process.arch !== 'x64') {
  console.log('Verificação do binding win32-x64 não se aplica nesta plataforma.');
} else {
  const expected = manifest.overrides?.rollup;
  let rollup, binding;
  try { rollup = JSON.parse(readFileSync(new URL('../node_modules/rollup/package.json', import.meta.url), 'utf8')); }
  catch { throw new Error('Rollup não instalado. Execute o fluxo local:install ou npm ci com o lockfile corporativo.'); }
  try { binding = JSON.parse(readFileSync(new URL('../node_modules/@rollup/rollup-win32-x64-msvc/package.json', import.meta.url), 'utf8')); }
  catch { throw new Error(`Binding oficial @rollup/rollup-win32-x64-msvc@${expected} ausente. Verifique o tarball e execute npm run local:cache e npm run local:install.`); }
  if (rollup.version !== expected || binding.version !== expected) {
    throw new Error(`Rollup/binding divergentes: esperado ${expected}, encontrados ${rollup.version}/${binding.version}.`);
  }
  console.log(`Rollup e binding nativo Windows confirmados: ${expected}.`);
}
