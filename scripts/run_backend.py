"""Inicializa o backend usando uma única configuração de execução.

Este arquivo existe para evitar que cada script de Windows/Linux replique host,
porta, quantidade de processos e regras de recarga automática. O ponto mais
importante é o escopo da recarga: somente diretórios que podem alterar o backend
são observados. A pasta ``frontend/node_modules`` nunca entra nesse escopo e,
por isso, alterações internas do npm não geram o aviso ``WatchFiles detected
changes`` nem reiniciam a API.

Entradas principais:
    ``--reload``: ativa a recarga automática para desenvolvimento.
    ``APP_RUNTIME_CONFIG``: caminho opcional para outro JSON de execução.
    ``BACKEND_HOST``: substitui o host configurado no JSON.
    ``BACKEND_PORT``: substitui a porta configurada no JSON.
    ``BACKEND_WORKERS``: substitui a quantidade de processos do backend.
    ``BACKEND_ACCESS_LOG``: ``true`` ou ``false`` para o log HTTP do Uvicorn.

Saída esperada:
    O processo permanece em execução servindo ``backend.principal:aplicacao``.
    Se a configuração for inválida ou o ambiente Python estiver incompatível,
    o script encerra com código diferente de zero e uma mensagem objetiva.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "runtime.json"
BACKEND_APP = "backend.principal:aplicacao"


def ensure_project_import_path() -> None:
    """Garante que os pacotes do projeto sejam importáveis em qualquer diretório.

    O usuário pode executar ``python caminho/scripts/run_backend.py`` sem estar
    na raiz do projeto. Nesse caso, o Python adiciona ``scripts`` ao ``sys.path``,
    mas não adiciona automaticamente a pasta que contém ``backend``.

    Esta função torna o iniciador autossuficiente: adiciona a raiz ao processo
    atual e ao ``PYTHONPATH`` herdado pelos subprocessos usados pelo reload do
    Uvicorn no Windows. Nenhum caminho da máquina do usuário é persistido.
    """
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    current_python_path = os.environ.get("PYTHONPATH", "")
    entries = [item for item in current_python_path.split(os.pathsep) if item]
    if project_root not in entries:
        os.environ["PYTHONPATH"] = os.pathsep.join([project_root, *entries])

    # Uvicorn resolve o import string a partir do diretório de trabalho. Manter
    # a raiz como cwd também deixa caminhos relativos de config/prompts estáveis.
    os.chdir(PROJECT_ROOT)


@dataclass(frozen=True)
class RuntimeSettings:
    """Valores necessários apenas para iniciar os servidores locais.

    A aplicação de negócio continua usando ``backend.config.Settings``. Esta
    classe é separada porque host, porta e recarga são preocupações de execução,
    não regras da análise documental.

    Atributos:
        backend_host: endereço local em que a API escuta conexões.
        backend_port: porta TCP da API.
        backend_workers: quantidade de processos Uvicorn em execução normal.
        backend_access_log: define se cada requisição HTTP aparece no log padrão.
        frontend_host: endereço esperado para o Angular local.
        frontend_port: porta esperada para o Angular local.
        reload_directories: diretórios observados quando ``--reload`` é usado.
        reload_include_patterns: tipos de arquivo que podem reiniciar a API.
        reload_exclude_patterns: caminhos/padrões que nunca devem provocar reinicialização.
    """

    backend_host: str
    backend_port: int
    backend_workers: int
    backend_access_log: bool
    frontend_host: str
    frontend_port: int
    reload_directories: tuple[Path, ...]
    reload_include_patterns: tuple[str, ...]
    reload_exclude_patterns: tuple[str, ...]


def _read_json(path: Path) -> dict[str, Any]:
    """Lê o arquivo de execução e garante que a raiz seja um objeto JSON.

    Entrada:
        ``path``: caminho para o arquivo de configuração.

    Saída:
        ``dict[str, Any]`` com o conteúdo já convertido para objetos Python.

    Erros:
        ``ValueError`` quando o arquivo não existe, não pode ser lido ou não
        contém um objeto JSON. O texto do erro não inclui segredos.
    """
    if not path.is_file():
        raise ValueError(f"Arquivo de configuração de execução não encontrado: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Não foi possível ler config/runtime.json.") from exc
    if not isinstance(value, dict):
        raise ValueError("A raiz de config/runtime.json deve ser um objeto JSON.")
    return value


def _required_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Obtém uma seção obrigatória do JSON sem aceitar tipos inesperados.

    Entrada:
        ``data``: dicionário raiz da configuração.
        ``key``: nome da seção, por exemplo ``backend``.

    Saída:
        O dicionário armazenado naquela seção.
    """
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"A seção '{key}' deve existir e ser um objeto JSON.")
    return value


def _environment_bool(name: str, default: bool) -> bool:
    """Converte uma variável de ambiente em booleano de forma explícita.

    Entrada:
        ``name``: nome da variável de ambiente.
        ``default``: valor usado quando a variável não foi definida.

    Saída:
        ``True`` ou ``False``. Valores diferentes de ``true/false/1/0`` são
        rejeitados para evitar comportamento silencioso e difícil de explicar.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "sim"}:
        return True
    if normalized in {"0", "false", "no", "nao", "não"}:
        return False
    raise ValueError(f"{name} deve ser true ou false.")


def _environment_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    """Lê um inteiro do ambiente e valida o intervalo permitido.

    Essa validação acontece antes de iniciar o servidor para que uma porta ou
    quantidade de processos inválida não gere uma falha pouco clara depois.
    """
    raw = os.environ.get(name)
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} deve ser um número inteiro.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} deve estar entre {minimum} e {maximum}.")
    return value


def _project_paths(values: Any, field_name: str) -> tuple[Path, ...]:
    """Transforma caminhos relativos do JSON em caminhos absolutos do projeto.

    Entrada:
        ``values``: lista JSON de textos.
        ``field_name``: nome usado na mensagem de validação.

    Saída:
        Tupla imutável de ``Path`` absolutos. A tupla facilita testar a
        configuração sem modificá-la acidentalmente durante a execução.
    """
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError(f"{field_name} deve ser uma lista não vazia de caminhos.")
    return tuple((PROJECT_ROOT / item).resolve() for item in values)


def _string_patterns(values: Any, field_name: str) -> tuple[str, ...]:
    """Valida uma lista de padrões relativos usada pelo observador de arquivos.

    Entrada:
        ``values``: lista lida do JSON.
        ``field_name``: nome do campo para mensagens de erro.

    Saída:
        Tupla de textos não vazios. Os padrões permanecem relativos porque o
        Uvicorn resolve exclusões a partir do diretório atual; caminhos absolutos
        não são aceitos por todas as versões suportadas da biblioteca.
    """
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError(f"{field_name} deve ser uma lista não vazia de padrões.")
    return tuple(item.strip() for item in values)


def load_runtime_settings(path: Path | None = None) -> RuntimeSettings:
    """Carrega e valida toda a configuração usada pelos scripts de execução.

    Ordem de precedência:
        1. variáveis de ambiente para valores simples de host/porta/processos;
        2. ``config/runtime.json`` (ou ``APP_RUNTIME_CONFIG``);
        3. nenhum valor é inventado silenciosamente fora desses locais.

    Saída:
        ``RuntimeSettings`` pronto para ser usado pelo Uvicorn e pelo iniciador
        conjunto de frontend/backend.
    """
    configured_path = path or Path(os.environ.get("APP_RUNTIME_CONFIG", DEFAULT_CONFIG_PATH))
    if not configured_path.is_absolute():
        configured_path = (PROJECT_ROOT / configured_path).resolve()

    data = _read_json(configured_path)
    backend = _required_mapping(data, "backend")
    frontend = _required_mapping(data, "frontend")
    reload_settings = _required_mapping(data, "reload")

    backend_host = os.environ.get("BACKEND_HOST", str(backend.get("host", ""))).strip()
    frontend_host = os.environ.get("FRONTEND_HOST", str(frontend.get("host", ""))).strip()
    if not backend_host or not frontend_host:
        raise ValueError("Os hosts de backend e frontend não podem ficar vazios.")

    backend_port = _environment_int("BACKEND_PORT", int(backend.get("port", 8000)), minimum=1, maximum=65535)
    frontend_port = _environment_int("FRONTEND_PORT", int(frontend.get("port", 4200)), minimum=1, maximum=65535)
    backend_workers = _environment_int("BACKEND_WORKERS", int(backend.get("workers", 1)), minimum=1, maximum=16)
    access_log = _environment_bool("BACKEND_ACCESS_LOG", bool(backend.get("access_log", False)))

    include_patterns = _string_patterns(reload_settings.get("include_patterns"), "reload.include_patterns")
    exclude_patterns = _string_patterns(reload_settings.get("exclude_paths"), "reload.exclude_paths")

    settings = RuntimeSettings(
        backend_host=backend_host,
        backend_port=backend_port,
        backend_workers=backend_workers,
        backend_access_log=access_log,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        reload_directories=_project_paths(reload_settings.get("directories"), "reload.directories"),
        reload_include_patterns=include_patterns,
        reload_exclude_patterns=exclude_patterns,
    )

    # Todos os diretórios observados precisam existir. Isso evita o Uvicorn cair
    # para um escopo mais amplo por causa de uma configuração escrita incorretamente.
    missing = [str(path) for path in settings.reload_directories if not path.is_dir()]
    if missing:
        raise ValueError("Diretório de recarga inexistente: " + ", ".join(missing))
    return settings


def validate_python_environment() -> None:
    """Executa a checagem de dependências antes de importar toda a aplicação.

    Entrada:
        Nenhuma. O mesmo interpretador que está executando este arquivo chama o
        validador, garantindo que a comparação represente o ambiente real.

    Saída:
        Nenhuma em caso de sucesso. Em caso de incompatibilidade, uma exceção
        interrompe a inicialização antes do servidor HTTP ser criado.
    """
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / "check-python-environment.py")]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError("O ambiente Python não atende aos requisitos mínimos compatíveis do projeto.")


def run_backend(*, reload_enabled: bool) -> None:
    """Inicia o Uvicorn com escopo de observação controlado.

    Entrada:
        ``reload_enabled``: quando ``True``, mudanças em Python, JSON de
        configuração e prompts Markdown reiniciam a API automaticamente.

    Saída:
        A função só retorna quando o servidor é encerrado.

    Regra importante:
        Mesmo em desenvolvimento, ``frontend`` e ``frontend/node_modules`` não
        são observados. Assim, o npm pode criar/alterar milhares de arquivos sem
        provocar o warning mostrado no terminal do usuário.
    """
    ensure_project_import_path()
    settings = load_runtime_settings()
    validate_python_environment()

    workers = 1 if reload_enabled else settings.backend_workers
    options: dict[str, Any] = {
        "host": settings.backend_host,
        "port": settings.backend_port,
        "workers": workers,
        "access_log": settings.backend_access_log,
    }

    if reload_enabled:
        options.update(
            reload=True,
            reload_dirs=[str(path) for path in settings.reload_directories],
            reload_includes=list(settings.reload_include_patterns),
            reload_excludes=list(settings.reload_exclude_patterns),
        )

    uvicorn.run(BACKEND_APP, **options)


def parse_arguments() -> argparse.Namespace:
    """Converte os argumentos do terminal em opções tipadas para o iniciador."""
    parser = argparse.ArgumentParser(description="Inicia o backend do AI Ready Processual.")
    parser.add_argument("--reload", action="store_true", help="Reinicia a API somente quando arquivos relevantes do backend mudarem.")
    return parser.parse_args()


def main() -> int:
    """Ponto único de entrada do backend usado por todos os sistemas operacionais."""
    arguments = parse_arguments()
    try:
        run_backend(reload_enabled=arguments.reload)
    except (ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
