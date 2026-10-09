/** Confere o baseline exigido pelo frontend e os ajustes oficiais registrados. */
import {readFileSync} from 'node:fs';
const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
for (const [name, version] of Object.entries({...manifest.dependencies, ...manifest.devDependencies})) {
  if (name.startsWith('@angular/') && version !== '21.2.19') {
    throw new Error(`${name}: esperado Angular 21.2.19, encontrado ${version}.`);
  }
}
if (manifest.packageManager !== 'npm@10.9.0') throw new Error('packageManager deve permanecer npm@10.9.0.');
if (manifest.devDependencies['@rollup/rollup-win32-x64-msvc'] !== manifest.overrides?.rollup) {
  throw new Error('O binding Windows e o override do Rollup devem usar a mesma versão.');
}
if (manifest.overrides?.chokidar?.readdirp !== '4.1.2' || manifest.overrides?.postcss !== '8.5.25') {
  throw new Error('Versões locais declaradas divergentes do baseline documentado.');
}
console.log('Baseline Angular 21.2.19 e pares oficiais do Rollup validados.');
