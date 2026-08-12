"""Article II made executable: dependencies flow one way, or the build fails.

Installed while the layers are still empty, which is exactly when it is trivial
to pass and when it starts protecting everything written afterwards.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ROOT_PACKAGE = "app"

# Most specific first: `workers.tasks` must win over `workers`.
KNOWN_LAYERS: tuple[str, ...] = (
    "workers.tasks",
    "adapters",
    "api",
    "core",
    "db",
    "domain",
    "services",
    "workers",
)

# layer -> layers it must never import.
FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    # Routers validate and delegate; they never touch persistence.
    "api": frozenset({"db"}),
    # A port knows nothing about who calls it or where the data is stored.
    "adapters": frozenset({"services", "db"}),
    # Pure rules with no I/O: the domain imports no other layer at all.
    "domain": frozenset({"api", "services", "adapters", "db", "workers", "core"}),
    # A task only orchestrates services (art. II).
    "workers.tasks": frozenset({"db", "adapters"}),
}


def _layer_of(dotted: str) -> str | None:
    """Map a module path relative to the app package onto its layer."""
    for layer in KNOWN_LAYERS:
        if dotted == layer or dotted.startswith(f"{layer}."):
            return layer
    return None


def _module_layer(path: Path) -> str | None:
    dotted = path.relative_to(APP_ROOT).with_suffix("").as_posix().replace("/", ".")
    return _layer_of(dotted)


def _imported_layers(module: ast.Module, path: Path) -> Iterator[tuple[str, int]]:
    """Yield (layer, lineno) for every import of another layer of this app."""
    package = [part for part in path.relative_to(APP_ROOT).parent.as_posix().split("/") if part]

    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(f"{ROOT_PACKAGE}."):
                    layer = _layer_of(alias.name.removeprefix(f"{ROOT_PACKAGE}."))
                    if layer is not None:
                        yield layer, node.lineno
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        module_name = node.module or ""
        if node.level:
            # Relative import: resolve against the package holding the file.
            base = package[: len(package) - node.level + 1]
            dotted = ".".join([*base, module_name]).strip(".")
        elif module_name.startswith(f"{ROOT_PACKAGE}."):
            dotted = module_name.removeprefix(f"{ROOT_PACKAGE}.")
        else:
            continue

        layer = _layer_of(dotted)
        if layer is not None:
            yield layer, node.lineno


def test_layer_dependencies_are_unidirectional() -> None:
    violations: list[str] = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        origin = _module_layer(path)
        forbidden = FORBIDDEN_IMPORTS.get(origin or "")
        if forbidden is None:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported, lineno in _imported_layers(module, path):
            if imported != origin and imported in forbidden:
                violations.append(
                    f"{path.relative_to(APP_ROOT.parent)}:{lineno}: "
                    f"{origin}/ imports {imported}/ (art. II)"
                )

    assert not violations, "Layer dependency violations:\n" + "\n".join(violations)


def test_every_declared_layer_exists() -> None:
    """The rules above must describe the tree that actually exists."""
    missing = [
        layer for layer in FORBIDDEN_IMPORTS if not (APP_ROOT / layer.replace(".", "/")).is_dir()
    ]
    assert not missing, f"Layers declared in the rules but absent from app/: {missing}"
