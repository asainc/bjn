/**
 * Valida a versão de Node.js e npm adotada como baseline do frontend.
 *
 * Entrada: executáveis `node` e `npm` disponíveis no PATH.
 * Saída: confirmação do ambiente ou erro explícito antes de acessar o Nexus.
 * Motivo: evitar árvores diferentes causadas por versões distintas do gerenciador.
 */
import {execFileSync} from 'node:child_process';

const EXPECTED_NODE = '22.12.0';
const EXPECTED_NPM = '10.9.0';

function fail(message) {
  throw new Error(message);
}

const currentNode = process.versions.node;
if (currentNode !== EXPECTED_NODE) {
  fail(`Node.js ${currentNode} detectado. Use exatamente ${EXPECTED_NODE} para gerar/instalar o lockfile corporativo.`);
}

const npmExecutable = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const currentNpm = execFileSync(npmExecutable, ['--version'], {encoding: 'utf8', timeout: 30000}).trim();
if (currentNpm !== EXPECTED_NPM) {
  fail(`npm ${currentNpm} detectado. O baseline do Node.js ${EXPECTED_NODE} usa npm ${EXPECTED_NPM}.`);
}

console.log(`Ambiente validado: Node.js ${EXPECTED_NODE} + npm ${EXPECTED_NPM}.`);
