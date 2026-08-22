"""Article XI made executable: a provider name outside the LLM adapter fails CI.

The rule of ADR-011 is literal — «un `if provider == "..."` fuera del adapter es
un bug del art. XI, no un atajo» — and a rule that depends on a reviewer
noticing it is not a rule. This test is installed while there is a single
implementation, which is exactly when it is trivial to pass and precisely
before the second one, which is when it would break without it (research R-22).

Two scopes, deliberately different:

- **Provider names** are forbidden in `services/`, `domain/`, `api/`, `db/`,
  `workers/` and in the tests of those layers. They are allowed inside
  `adapters/llm/`, which is what an adapter is for, and in `core/config.py`,
  where the credential and the model name of a concrete provider have to be
  named to be read from configuration (research R-21).
- **Sampling parameters** are forbidden in `services/` and in the port
  signatures. `temperature`, `top_p` and `top_k` are deprecated in Gemini 3.x
  and not every provider exposes them alike: they are a detail of an
  implementation, and hoisting one into the domain is the same bug as naming a
  provider (research R-25, ADR-003).

What gets scanned is **code**: identifiers and string literals, which is where
`if provider == "..."` and `settings.google_model` live. Comments and
docstrings are exempt on purpose — a rule that forbids writing down why it
exists is a rule someone eventually deletes, and this very module has to name
all seven providers to look for them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
TESTS_ROOT = BACKEND_ROOT / "tests"

# The layers art. XI protects. `core/` is out on purpose: Settings has to name
# `google_api_key` to read it from the environment. `adapters/` is out because
# the adapter is the one place that may know who it is talking to.
SCANNED_LAYERS: tuple[str, ...] = ("api", "db", "domain", "services", "workers")

# The closed list of ADR-011, plus the alias each provider is known by.
PROVIDER_NAMES: tuple[str, ...] = (
    "google",
    "gemini",
    "openai",
    "anthropic",
    "deepseek",
    "kimi",
    "moonshot",
)

# An underscore counts as a boundary, a letter does not: `google_model` is the
# provider leaking into an identifier and must be caught, while `googler` is a
# different word and a substring match would turn this guard into noise nobody
# keeps green.
PROVIDER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(PROVIDER_NAMES) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

SAMPLING_PARAMETERS: tuple[str, ...] = ("temperature", "top_p", "top_k")
SAMPLING_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(SAMPLING_PARAMETERS) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# Where the ports are declared. Their signatures are part of the contract every
# future implementation has to satisfy (contracts/llm-extraction.md).
PORT_MODULE = APP_ROOT / "adapters" / "llm" / "base.py"
ADAPTER_PREFIX = "app.adapters"


def _app_imports(path: Path) -> set[str]:
    """Dotted names of this application that `path` imports."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()

    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names if alias.name.startswith("app."))
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app"):
            imported.add(node.module or "")

    return imported


def _belongs_to(imported: set[str], layer: str) -> bool:
    prefix = f"app.{layer}"
    return any(name == prefix or name.startswith(f"{prefix}.") for name in imported)


def _tests_of_scanned_layers() -> list[Path]:
    """Test modules that exercise a protected layer.

    A test file has no layer of its own, so it is classified by what it
    imports: it is a test *of* these layers when it reaches into one of them
    and never into `adapters/`. A test that imports the adapter is a test of
    the adapter, and naming a provider there is its job.
    """
    selected: list[Path] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        imported = _app_imports(path)
        if any(name.startswith(ADAPTER_PREFIX) for name in imported):
            continue
        if any(_belongs_to(imported, layer) for layer in SCANNED_LAYERS):
            selected.append(path)
    return selected


def _sources_under_scan() -> list[Path]:
    layers = [path for layer in SCANNED_LAYERS for path in sorted((APP_ROOT / layer).rglob("*.py"))]
    return layers + _tests_of_scanned_layers()


def _docstring_nodes(module: ast.Module) -> set[int]:
    """Ids of the string constants that are docstrings, so prose can be skipped."""
    ids: set[int] = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _code_text(path: Path) -> list[tuple[str, int]]:
    """Every identifier and every string literal of the file, with its line."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(module)
    found: list[tuple[str, int]] = []

    for node in ast.walk(module):
        match node:
            case ast.Name(id=text) | ast.Attribute(attr=text) | ast.arg(arg=text):
                found.append((text, node.lineno))
            case ast.FunctionDef(name=text) | ast.AsyncFunctionDef(name=text):
                found.append((text, node.lineno))
            case ast.ClassDef(name=text):
                found.append((text, node.lineno))
            case ast.keyword(arg=str() as text):
                found.append((text, node.value.lineno))
            case ast.alias(name=text):
                found.append((text, node.lineno))
            case ast.Import() | ast.ImportFrom():
                found.append((getattr(node, "module", None) or "", node.lineno))
            case ast.Constant(value=str() as text) if id(node) not in docstrings:
                found.append((text, node.lineno))

    return found


def _reported_as(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT) if path.is_relative_to(BACKEND_ROOT) else path)


def _offences(path: Path, pattern: re.Pattern[str]) -> list[str]:
    return [
        f"{_reported_as(path)}:{number}: «{match.group()}» in «{text}»"
        for text, number in _code_text(path)
        for match in pattern.finditer(text)
    ]


def test_provider_names_stay_inside_the_llm_adapter() -> None:
    violations = [
        offence for path in _sources_under_scan() for offence in _offences(path, PROVIDER_PATTERN)
    ]
    assert not violations, (
        "A provider name appears outside adapters/llm/ (art. XI, ADR-011). "
        "Ask the capability, not the name:\n" + "\n".join(violations)
    )


def test_sampling_parameters_stay_out_of_services_and_ports() -> None:
    services = sorted((APP_ROOT / "services").rglob("*.py"))
    violations = [
        offence
        for path in [*services, PORT_MODULE]
        if path.exists()
        for offence in _offences(path, SAMPLING_PATTERN)
    ]
    assert not violations, (
        "A sampling parameter appears in services/ or in a port signature "
        "(research R-25). It belongs to the implementation that supports it:\n"
        + "\n".join(violations)
    )


def test_the_scan_catches_the_two_bugs_it_exists_for(tmp_path: Path) -> None:
    """A guard nobody has seen fail is a guard nobody knows works."""
    offender = tmp_path / "tempting_shortcut.py"
    offender.write_text(
        '"""A docstring may name Gemini: prose is not code."""\n'
        "def build(provider: str, settings: object) -> object:\n"
        '    if provider == "google":\n'
        "        return settings.google_model\n"
        "    return chat(temperature=0, top_p=1)\n",
        encoding="utf-8",
    )

    provider_hits = _offences(offender, PROVIDER_PATTERN)
    assert [hit.split(": ", 1)[1] for hit in provider_hits] == [
        "«google» in «google»",
        "«google» in «google_model»",
    ]

    sampling_hits = _offences(offender, SAMPLING_PATTERN)
    assert len(sampling_hits) == 2


def test_the_scan_covers_the_layers_it_claims_to_cover() -> None:
    """A guard that silently scans nothing passes forever."""
    missing = [layer for layer in SCANNED_LAYERS if not (APP_ROOT / layer).is_dir()]
    assert not missing, f"Layers declared in the scan but absent from app/: {missing}"

    scanned = _sources_under_scan()
    assert scanned, "The provider-name scan matched no file at all"
    assert PORT_MODULE.exists(), f"The port module is missing: {PORT_MODULE}"
