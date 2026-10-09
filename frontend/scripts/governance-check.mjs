/**
 * Valida homologação exata das dependências de frontend sem usar rede.
 * Entrada: frontend/config/approved-packages.json, fornecido pela governança.
 * Saídas: relatório CSV local e código 1 enquanto houver qualquer pendência.
 */
import {readFileSync, mkdirSync, writeFileSync, existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {collectArtifacts, evaluateApprovals, toCsv} from './governance-core.mjs';

const base = resolve(fileURLToPath(new URL('../', import.meta.url)));
const outputDir = resolve(base, 'reports');
const approvedFile = process.env.NPM_APPROVED_PACKAGES_FILE || resolve(base, 'config/approved-packages.json');
const lockPath = resolve(base, 'package-lock.json');
if (!existsSync(lockPath)) throw new Error('package-lock.json ausente. Execute npm run nexus:lock antes da homologação.');
const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
const artifacts = collectArtifacts(lock);
let approvals;
try {
  approvals = JSON.parse(readFileSync(approvedFile, 'utf8'));
} catch (error) {
  if (error.code === 'ENOENT') {
    console.error('Homologação pendente: forneça o catálogo aprovado em frontend/config/approved-packages.json ou NPM_APPROVED_PACKAGES_FILE.');
    process.exitCode = 1;
  } else throw error;
}
if (approvals) {
  const rows = evaluateApprovals(artifacts, approvals);
  const pending = rows.filter(row => row.status !== 'APROVADO');
  mkdirSync(outputDir, {recursive: true});
  writeFileSync(resolve(outputDir, 'governance-status.csv'), toCsv(rows, ['name', 'version', 'status', 'optional']), {mode: 0o600});
  console.log(`Homologação: ${rows.length - pending.length}/${rows.length} artefatos aprovados por versão e integridade.`);
  if (pending.length) {
    console.error(`${pending.length} pendência(s). Consulte frontend/reports/governance-status.csv. Instalação não homologada.`);
    process.exitCode = 1;
  }
}
