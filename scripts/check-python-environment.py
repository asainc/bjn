"""Valida compatibilidade mínima do runtime Python antes de iniciar a API.

A checagem é deliberadamente diferente de um lock exato. O arquivo
``requirements.lock`` continua servindo como referência reproduzível para a
criação de um ambiente virtual novo, enquanto este script aceita runtimes
corporativos já existentes quando as versões instaladas estão dentro das
faixas suportadas pelo código.

Nenhuma dependência é instalada, removida ou alterada por este script.
"""
from __future__ import annotations

import importlib.metadata
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedPackage:
    """Define a faixa de versões que o código realmente necessita.

    ``minimum`` é inclusivo e ``maximum`` é exclusivo. O objetivo não é
    homologar cada patch disponível, mas impedir versões claramente antigas ou
    mudanças de versão principal que possam quebrar o contrato usado pelo
    projeto.
    """

    name: str
    minimum: tuple[int, ...]
    maximum: tuple[int, ...]


SUPPORTED_PACKAGES = (
    SupportedPackage("requests", (2, 32, 0), (3, 0, 0)),
    SupportedPackage("pydantic", (2, 13, 0), (3, 0, 0)),
    SupportedPackage("fastapi", (0, 121, 2), (1, 0, 0)),
    SupportedPackage("uvicorn", (0, 38, 0), (1, 0, 0)),
    SupportedPackage("python-multipart", (0, 0, 18), (1, 0, 0)),
    SupportedPackage("pymupdf", (1, 26, 0), (2, 0, 0)),
)


def installed_version(package: str) -> str | None:
    """Retorna a versão instalada sem importar o pacote alvo.

    Isso evita efeitos colaterais durante a validação, especialmente avisos do
    ``requests`` quando um ``chardet`` externo e incompatível está presente no
    mesmo ambiente Python.
    """
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def numeric_version(raw: str) -> tuple[int, ...]:
    """Converte uma versão em uma tupla numérica para comparação simples.

    Exemplos:
        ``0.121.2`` -> ``(0, 121, 2)``
        ``7.4.0.post2`` -> ``(7, 4, 0, 2)``

    A aplicação usa somente pacotes com versionamento numérico convencional;
    portanto não é necessário carregar uma biblioteca adicional apenas para a
    checagem de inicialização.
    """
    numbers = [int(item) for item in re.findall(r"\d+", raw)]
    return tuple(numbers or [0])


def padded(version: tuple[int, ...], size: int) -> tuple[int, ...]:
    """Completa a versão com zeros para comparar tuplas de tamanhos diferentes."""
    return version + (0,) * max(0, size - len(version))


def is_supported(found: str, requirement: SupportedPackage) -> bool:
    """Informa se a versão encontrada está dentro da faixa suportada."""
    parsed = numeric_version(found)
    size = max(len(parsed), len(requirement.minimum), len(requirement.maximum))
    current = padded(parsed, size)
    minimum = padded(requirement.minimum, size)
    maximum = padded(requirement.maximum, size)
    return minimum <= current < maximum


def fastapi_declared_starlette_range() -> tuple[tuple[str, str], ...]:
    """Lê a própria restrição do FastAPI para Starlette, quando disponível.

    O projeto não fixa uma versão independente de Starlette porque essa
    dependência deve acompanhar a versão de FastAPI instalada. Validar o par
    declarado pelo próprio FastAPI evita combinações artificiais, como usar um
    Starlette mais novo do que a versão de FastAPI aceita.
    """
    requirements = importlib.metadata.requires("fastapi") or []
    for requirement in requirements:
        base = requirement.split(";", 1)[0].strip()
        if not re.match(r"(?i)^starlette\b", base):
            continue
        constraints = re.findall(r"(>=|<=|==|>|<)\s*([0-9][A-Za-z0-9_.+-]*)", base)
        return tuple(constraints)
    return ()


def satisfies_constraints(version: str, constraints: tuple[tuple[str, str], ...]) -> bool:
    """Avalia as comparações simples declaradas pelo FastAPI para Starlette."""
    current_raw = numeric_version(version)
    for operator, expected_text in constraints:
        expected_raw = numeric_version(expected_text)
        size = max(len(current_raw), len(expected_raw))
        current = padded(current_raw, size)
        expected = padded(expected_raw, size)
        comparisons = {
            ">=": current >= expected,
            "<=": current <= expected,
            ">": current > expected,
            "<": current < expected,
            "==": current == expected,
        }
        if not comparisons[operator]:
            return False
    return True


def main() -> int:
    """Valida somente incompatibilidades que impedem ou tornam insegura a execução.

    Saída:
        ``0``: runtime compatível. Avisos podem ser exibidos sem bloquear.
        ``2``: dependência ausente ou versão fora da faixa suportada.
    """
    problems: list[str] = []
    warnings: list[str] = []

    if not ((3, 12) <= sys.version_info[:2] < (3, 14)):
        problems.append(
            f"Python {sys.version.split()[0]} em uso; versões suportadas: 3.12.x ou 3.13.x."
        )

    versions: dict[str, str] = {}
    for requirement in SUPPORTED_PACKAGES:
        found = installed_version(requirement.name)
        if found is None:
            problems.append(f"{requirement.name}: pacote ausente.")
            continue
        versions[requirement.name] = found
        if not is_supported(found, requirement):
            minimum = ".".join(map(str, requirement.minimum))
            maximum = ".".join(map(str, requirement.maximum))
            problems.append(
                f"{requirement.name}: instalado {found}; faixa suportada >= {minimum} e < {maximum}."
            )

    # Starlette é dependência direta do FastAPI. Em vez de impor um pin próprio,
    # o projeto verifica se a versão presente respeita o requisito declarado pela
    # própria versão de FastAPI instalada.
    starlette = installed_version("starlette")
    if starlette is None:
        problems.append("starlette: pacote ausente; ele deve ser instalado junto com FastAPI.")
    elif "fastapi" in versions:
        constraints = fastapi_declared_starlette_range()
        if constraints and not satisfies_constraints(starlette, constraints):
            readable = ", ".join(f"{operator}{version}" for operator, version in constraints)
            problems.append(
                f"starlette: instalado {starlette}; FastAPI {versions['fastapi']} declara {readable}."
            )

    # Requests 2.x não necessita de chardet quando charset-normalizer está
    # instalado. Algumas estações corporativas, porém, trazem chardet >= 6 por
    # outros softwares. Requests emite um aviso nesse cenário. Isso não deve
    # impedir a API de iniciar, porque remover pacote de um ambiente compartilhado
    # automaticamente poderia quebrar outra aplicação.
    chardet = installed_version("chardet")
    if chardet and numeric_version(chardet) >= (6, 0, 0):
        warnings.append(
            f"chardet {chardet} está instalado. Requests 2.x pode emitir um aviso de compatibilidade. "
            "O AI Ready não depende de chardet; em uma .venv exclusiva, prefira removê-lo e usar "
            "charset-normalizer. Em ambiente compartilhado, não remova sem validar as demais aplicações."
        )

    charset_normalizer = installed_version("charset-normalizer")
    if charset_normalizer is None:
        problems.append(
            "charset-normalizer: pacote ausente. Requests 2.x utiliza essa dependência no ambiente recomendado."
        )

    for item in warnings:
        print(f"AVISO: {item}", file=sys.stderr)

    if problems:
        print("ERRO: ambiente Python incompatível com os requisitos mínimos do projeto.", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Correção recomendada em ambiente isolado:", file=sys.stderr)
        print(r"  py -3.12 -m venv .venv", file=sys.stderr)
        print(r"  .venv\Scripts\python.exe -m pip install --upgrade pip", file=sys.stderr)
        print(r"  .venv\Scripts\python.exe -m pip install -r requirements.lock", file=sys.stderr)
        print(r"  .venv\Scripts\python.exe -m pip install --no-deps -e .", file=sys.stderr)
        return 2

    scope = "ambiente virtual" if sys.prefix != sys.base_prefix else "Python global/compartilhado"
    summary = ", ".join(
        f"{name}={version}"
        for name, version in sorted(versions.items())
    )
    if starlette:
        summary += f", starlette={starlette}"
    print(f"Dependências Python compatíveis ({scope}).")
    print(f"Versões detectadas: {summary}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
