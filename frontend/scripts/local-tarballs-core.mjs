/**
 * Utilitários puros de inspeção de arquivos npm oficiais em formato tgz.
 * Entradas: bytes do tarball e objetos lockfile.
 * Saídas: identidade extraída do manifesto, SHA-512 e lista de correspondências.
 * Motivo: confiar no conteúdo e no hash, nunca no nome dado ao arquivo baixado.
 */
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {packageNameFromPath} from './governance-core.mjs';

const MAX_UNPACKED_BYTES = 256 * 1024 * 1024;

/** Extrai o manifesto do arquivo TAR compactado sem executar scripts do pacote. */
export function readTarballIdentity(compressed) {
  if (!Buffer.isBuffer(compressed) || compressed.length === 0) throw new Error('Arquivo tarball vazio.');
  let tar;
  try { tar = gunzipSync(compressed, {maxOutputLength: MAX_UNPACKED_BYTES}); }
  catch { throw new Error('Arquivo .tgz inválido ou maior que o limite de inspeção.'); }
  for (let position = 0; position + 512 <= tar.length;) {
    const header = tar.subarray(position, position + 512);
    if (header.every(value => value === 0)) break;
    const name = header.subarray(0, 100).toString('utf8').split('\0')[0].replace(/^\.\//, '');
    const prefix = header.subarray(345, 500).toString('utf8').split('\0')[0];
    const path = prefix ? `${prefix}/${name}` : name;
    const sizeText = header.subarray(124, 136).toString('ascii').split('\0')[0].trim();
    if (!/^[0-7]+$/.test(sizeText)) throw new Error('TAR inválido: tamanho de entrada não octal.');
    const size = parseInt(sizeText, 8);
    const start = position + 512;
    if (!Number.isSafeInteger(size) || start + size > tar.length) throw new Error('TAR truncado ou inválido.');
    if (path === 'package/package.json') {
      if (size > 1024 * 1024) throw new Error('Manifesto de pacote excessivamente grande.');
      let manifest;
      try { manifest = JSON.parse(tar.subarray(start, start + size).toString('utf8')); }
      catch { throw new Error('package/package.json inválido no tarball.'); }
      if (!/^(@[^/]+\/)?[a-zA-Z0-9][\w.-]*$/.test(manifest.name ?? '') ||
          !/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(manifest.version ?? '')) {
        throw new Error('Nome ou versão inválidos no package/package.json.');
      }
      return {name: manifest.name, version: manifest.version};
    }
    position = start + Math.ceil(size / 512) * 512;
  }
  throw new Error('package/package.json ausente no tarball npm.');
}

/** Calcula a integridade do arquivo original, sem modificar seus bytes. */
export function tarballIntegrity(bytes) {
  return `sha512-${createHash('sha512').update(bytes).digest('base64')}`;
}

/** Agrupa artefatos por identidade real, inclusive pacotes sob escopos. */
export function lockIdentityMap(lock) {
  const found = new Map();
  for (const [path, pkg] of Object.entries(lock?.packages ?? {})) {
    if (!path || !pkg.version) continue;
    const name = packageNameFromPath(path);
    const key = `${name}@${pkg.version}`;
    if (found.has(key) && found.get(key).integrity !== pkg.integrity) {
      throw new Error(`Integridades conflitantes no lock para ${key}.`);
    }
    found.set(key, pkg);
  }
  return found;
}
