/**
 * Diagnostica URL de tarball informada pelo Nexus sem alterar arquivos.
 * Entrada: pacote/versão opcional via argumento CLI, e registry npm configurado.
 * Saída: metadados de origem e alerta sobre duplicação de /repository/.../.
 */
import {existsSync, readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateCorporateRegistry, readConfiguredRegistry, npmCommand} from './validate-nexus-registry.mjs';
const root = resolve(fileURLToPath(new URL('../', import.meta.url)));
const registry = validateCorporateRegistry(readConfiguredRegistry());
const name = process.argv[2] || '@rollup/rollup-win32-x64-msvc';
const version = process.argv[3] || '4.60.1';
if (!/^(@[\w.-]+\/)?[\w.-]+$/.test(name) || !/^\d+\.\d+\.\d+$/.test(version)) {
  throw new Error('Nome ou versão inválidos para consulta.');
}
const lockPath = resolve(root, 'package-lock.json');
if (existsSync(lockPath)) {
  const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
  const target = Object.entries(lock.packages || {}).find(([path,pkg]) => path.endsWith(`/node_modules/${name}`) && pkg.version === version)
    || Object.entries(lock.packages || {}).find(([path,pkg]) => path === `node_modules/${name}` && pkg.version === version);
  if (target) {
    const url = target[1].resolved ?? '';
    console.log('Lockfile:', url ? 'artefato localizado' : 'sem URL de tarball');
    if (url) {
      const parsed = new URL(url);
      const relative = parsed.pathname.slice(new URL(registry).pathname.length);
      console.log(relative.startsWith('repository/') ? 'ALERTA: URL duplicada registrada no lockfile.' : 'URL do lock: não foi detectada duplicação direta.');
    }
  } else console.log('Pacote não encontrado na versão solicitada no lockfile.');
}
try {
  const raw = npmCommand(['view', `${name}@${version}`, 'dist.tarball', '--json', '--registry', registry, '--no-audit'], {cwd: root});
  const dist = JSON.parse(raw);
  const url = new URL(dist);
  const registryUrl = new URL(registry);
  console.log('Metadados do Nexus:', url.hostname === registryUrl.hostname ? 'mesmo host' : 'host diferente');
  console.log(url.pathname.startsWith(registryUrl.pathname + 'repository/') ? 'ALERTA: URL duplicada devolvida pelos metadados Nexus.' :
    url.pathname.startsWith(registryUrl.pathname) ? 'Caminho de tarball dentro do repositório.' : 'Tarball fora do caminho configurado.');
} catch {
  console.log('A consulta aos metadados falhou. Confira permissões/registry; nenhuma versão foi modificada.');
  process.exitCode = 1;
}
