/**
 * Inicia backend e frontend no mesmo terminal para desenvolvimento local.
 *
 * O backend é iniciado por `scripts/run_backend.py --reload`. Dessa forma, as
 * regras de recarga automática ficam em um único lugar e `frontend/node_modules`
 * não é observado pelo WatchFiles.
 *
 * Entradas opcionais por variável de ambiente:
 *   BACKEND_PYTHON  -> caminho do interpretador Python.
 *   BACKEND_HOST    -> substitui o host do backend.
 *   BACKEND_PORT    -> substitui a porta do backend.
 *   FRONTEND_HOST   -> substitui o host do Angular.
 *   FRONTEND_PORT   -> substitui a porta do Angular.
 *
 * Saída esperada:
 *   os dois processos permanecem ativos até Ctrl+C. Se um deles falhar, o outro
 *   também é encerrado para evitar uma aplicação parcialmente disponível.
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const windows = process.platform === 'win32';
const runtimePath = process.env.APP_RUNTIME_CONFIG
  ? resolve(root, process.env.APP_RUNTIME_CONFIG)
  : join(root, 'config', 'runtime.json');
const runtime = JSON.parse(readFileSync(runtimePath, 'utf8'));

const backendHost = process.env.BACKEND_HOST || runtime.backend.host;
const backendPort = Number(process.env.BACKEND_PORT || runtime.backend.port);
const frontendHost = process.env.FRONTEND_HOST || runtime.frontend.host;
const frontendPort = Number(process.env.FRONTEND_PORT || runtime.frontend.port);

const venvPython = join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.BACKEND_PYTHON || (existsSync(venvPython) ? venvPython : 'python');
const angular = join(root, 'frontend', 'node_modules', '@angular', 'cli', 'bin', 'ng.js');
const runtimeProxyPath = join(root, 'frontend', '.runtime-proxy.json');
const children = [];
let closing = false;

/** Encerra somente processos que este arquivo iniciou. */
function stop(code = 0) {
  if (closing) return;
  closing = true;

  // O arquivo é temporário e contém apenas o endereço local do backend.
  // Removê-lo evita que uma configuração de outra execução seja reutilizada.
  rmSync(runtimeProxyPath, { force: true });

  for (const child of children) {
    if (!child.pid || child.exitCode !== null) continue;

    if (windows) {
      // No Windows, taskkill /T encerra também os processos filhos do Angular/Uvicorn.
      spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      try {
        process.kill(-child.pid, 'SIGTERM');
      } catch {
        // O processo já pode ter encerrado sozinho; nesse caso não há ação pendente.
      }
    }
  }

  process.exitCode = code;
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());

/**
 * Cria um processo filho com o diretório e o ambiente adequados.
 *
 * Para o backend, `PYTHONPATH` recebe a raiz do projeto. Para o frontend,
 * credenciais do backend são removidas do ambiente antes de iniciar o Node.
 */
function launch(command, args, cwd, { frontend = false } = {}) {
  const environment = { ...process.env };

  if (!frontend) {
    const projectPythonPath = root;
    environment.PYTHONPATH = environment.PYTHONPATH
      ? `${projectPythonPath}${delimiter}${environment.PYTHONPATH}`
      : projectPythonPath;
  } else {
    for (const key of ['BRADESCO_AUTHORIZATION_TOKEN', 'BRADESCO_IDENTIFICADOR', 'BRADESCO_SENHA', 'GATEWAY_TOKEN']) {
      delete environment[key];
    }
  }

  const child = spawn(command, args, {
    cwd,
    stdio: 'inherit',
    detached: !windows,
    env: environment,
  });

  children.push(child);
  child.on('error', () => {
    console.error('Não foi possível iniciar um dos serviços. Confira as dependências descritas no README.');
    stop(1);
  });
  child.on('exit', code => {
    if (!closing) {
      console.error('Um dos serviços encerrou. Confira a mensagem exibida acima.');
      stop(code || 1);
    }
  });

  return child;
}

/** Garante que a porta desejada não esteja ocupada por outro processo. */
async function requireFreePort(host, port) {
  await new Promise((accept, reject) => {
    const server = createServer();
    server.once('error', () => reject(new Error(`A porta ${port} já está ocupada em ${host}. Encerre o processo anterior antes de continuar.`)));
    server.listen(port, host, () => server.close(accept));
  });
}

/**
 * Cria a configuração de proxy usada somente nesta execução do Angular.
 *
 * Entrada:
 *   usa `backendHost` (string) e `backendPort` (number), já resolvidos a partir
 *   de `config/runtime.json` e das variáveis de ambiente.
 *
 * Saída:
 *   grava `frontend/.runtime-proxy.json`. O navegador continua chamando `/api`
 *   e o Angular encaminha a chamada para a porta efetivamente configurada no
 *   backend. Assim, alterar BACKEND_PORT não exige editar outro arquivo.
 */
function writeRuntimeProxy() {
  const proxy = {
    '/api/**': {
      target: `http://${backendHost}:${backendPort}`,
      secure: false,
      changeOrigin: true,
    },
  };
  writeFileSync(runtimeProxyPath, `${JSON.stringify(proxy, null, 2)}\n`, 'utf8');
}

/** Aguarda a API responder antes de iniciar o Angular. */
async function waitForBackend() {
  const endpoint = `http://${backendHost}:${backendPort}/api/v3/saude`;
  const deadline = Date.now() + 20_000;

  while (!closing && Date.now() < deadline) {
    try {
      const response = await fetch(endpoint, { signal: AbortSignal.timeout(1_000) });
      const value = await response.json();
      if (response.ok && value.status === 'ok') return true;
    } catch {
      // Durante a inicialização, falhas temporárias são esperadas e serão tentadas novamente.
    }
    await delay(250);
  }

  return false;
}

try {
  if (python !== 'python' && !existsSync(python)) {
    throw new Error('O interpretador Python configurado não foi encontrado. Confira BACKEND_PYTHON.');
  }
  if (!existsSync(angular)) {
    throw new Error('As dependências Angular não estão instaladas. Execute npm install dentro da pasta frontend.');
  }

  if (!Number.isInteger(backendPort) || backendPort < 1 || backendPort > 65535) {
    throw new Error('BACKEND_PORT deve ser um número inteiro entre 1 e 65535.');
  }
  if (!Number.isInteger(frontendPort) || frontendPort < 1 || frontendPort > 65535) {
    throw new Error('FRONTEND_PORT deve ser um número inteiro entre 1 e 65535.');
  }

  await requireFreePort(backendHost, backendPort);
  await requireFreePort(frontendHost, frontendPort);
  writeRuntimeProxy();

  launch(python, ['scripts/run_backend.py', '--reload'], root);

  if (!(await waitForBackend())) {
    throw new Error('O backend não respondeu dentro do tempo esperado. Confira a configuração e o ambiente Python.');
  }

  if (!closing) {
    launch(
      process.execPath,
      [
        angular,
        'serve',
        '--host', frontendHost,
        '--port', String(frontendPort),
        '--proxy-config', runtimeProxyPath,
      ],
      join(root, 'frontend'),
      { frontend: true },
    );
    console.log(`Backend pronto. Aguarde o Angular e abra http://${frontendHost}:${frontendPort}. Ctrl+C encerra os dois serviços.`);
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  stop(1);
}
