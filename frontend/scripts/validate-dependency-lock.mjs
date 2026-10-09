/**
 * Verifica origem, integridade e alinhamento do lockfile com o frontend homologável.
 * Entrada: manifests do frontend e registry corporativo atualmente configurado.
 * Saída: status de consistência ou erro; não aprova licenças nem versões no Nexus.
 */
import {readFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {validateCorporateRegistry, readConfiguredRegistry} from './validate-nexus-registry.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const lockPath = resolve(root, 'package-lock.json');
if (!existsSync(lockPath)) throw new Error('package-lock.json ausente: importe o lock corporativo validado ou execute npm run nexus:lock.');
const manifest = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'));
const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
const packages = lock.packages ?? {};
const registry = new URL(validateCorporateRegistry(readConfiguredRegistry()));
function check(ok, description) { if (!ok) throw new Error(description); }
check(lock.lockfileVersion === 3 && Boolean(packages['']), 'Lockfile v3 inválido ou sem pacote raiz.');
for (const section of ['dependencies', 'devDependencies']) {
  const a = packages[''][section] ?? {};
  const b = manifest[section] ?? {};
  check(Object.keys(a).length === Object.keys(b).length && Object.entries(b).every(([k,v]) => a[k] === v),
    `${section} divergente entre package.json e package-lock.json. Regenere pelo Nexus.`);
}
check(JSON.stringify(packages[''].overrides ?? manifest.overrides ?? {}) === JSON.stringify(manifest.overrides ?? {}),
  'Overrides divergentes no manifesto raiz do lockfile.');
let count = 0;
for (const [path, pkg] of Object.entries(packages)) {
  if (!path) continue;
  check(!pkg.link, `${path}: link não autorizado.`);
  check(typeof pkg.version === 'string' && /^\d+\.\d+\.\d+/.test(pkg.version), `${path}: versão ausente.`);
  if (!pkg.resolved) continue; // Pacotes empacotados dentro de outro módulo podem não ter URL própria.
  check(!/^(file:|git\+|git:|github:)/i.test(pkg.resolved), `${path}: origem local/Git não permitida.`);
  let url;
  try { url = new URL(pkg.resolved); } catch { throw new Error(`${path}: URL de tarball inválida.`); }
  check(url.protocol === 'https:' && url.hostname.toLowerCase() === registry.hostname.toLowerCase(),
    `${path}: artefato fora do Nexus corporativo.`);
  check(url.port === registry.port && !url.username && !url.password && !url.search && !url.hash,
    `${path}: URL de artefato insegura ou com credenciais.`);
  check(url.pathname.startsWith(registry.pathname), `${path}: artefato fora do repositório configurado.`);
  const suffix = url.pathname.slice(registry.pathname.length);
  check(!suffix.includes(registry.pathname) && !suffix.startsWith('repository/'),
    `${path}: caminho duplicado /repository/.../ no tarball. Corrija a origem antes de instalar.`);
  check(/^sha512-[A-Za-z0-9+/]+={0,2}$/.test(pkg.integrity ?? ''), `${path}: integridade SHA-512 ausente.`);
  count++;
}
check(count > 0, 'Nenhum artefato resolvido no Nexus foi encontrado.');
const native = packages['node_modules/@rollup/rollup-win32-x64-msvc'];
const rollupVersions = new Set(Object.entries(packages).filter(([path]) => /(?:^|\/)node_modules\/rollup$/.test(path)).map(([,pkg])=>pkg.version));
if (rollupVersions.size) {
  check(native?.version === manifest.devDependencies['@rollup/rollup-win32-x64-msvc'],
    'Binding Windows do Rollup não consta no lock na versão declarada em devDependencies.');
  check([...rollupVersions].every(version => version === native.version),
    'A versão do Rollup e de seu binding Windows divergem no lockfile.');
}
console.log(`Lockfile: ${count} artefatos com URL e SHA-512 do Nexus validados; binding Rollup consistente.`);
