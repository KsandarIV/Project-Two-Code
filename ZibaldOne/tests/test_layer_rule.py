"""Layer rule: `core` is the base layer and never imports `ui`, `cli` or `storage`."""

import ast
from pathlib import Path

import zibaldone

CORE = Path(zibaldone.__file__).parent / "core"
FORBIDDEN = ("ui", "cli", "storage")


def forbidden_imports(source: str, module: str = "zibaldone.core.x") -> list:
    """The forbidden layers imported anywhere in `source`, including imports inside functions."""
    found = []
    package = module.rsplit(".", 1)[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join(parts + ([base] if base else []))
            names = [base] + [f"{base}.{alias.name}" for alias in node.names]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if parts[0] == "zibaldone" and len(parts) > 1 and parts[1] in FORBIDDEN:
                found.append(name)
    return found


def test_core_does_not_import_upper_layers():
    problems = []
    for path in sorted(CORE.rglob("*.py")):
        module = "zibaldone.core." + ".".join(path.relative_to(CORE).with_suffix("").parts)
        for name in forbidden_imports(path.read_text(encoding="utf-8"), module):
            problems.append(f"{path.relative_to(CORE.parent.parent)}: imports {name}")
    assert not problems, "core must not import ui, cli or storage:\n" + "\n".join(problems)


def test_the_check_catches_a_forbidden_import():
    assert forbidden_imports("from zibaldone.storage.database import Store")
    assert forbidden_imports("import zibaldone.ui.app")
    assert forbidden_imports("def f():\n    from zibaldone import cli\n")
    assert forbidden_imports("from ..storage import media", "zibaldone.core.x")
    assert not forbidden_imports("from zibaldone.core.errors import StoreError\nimport json")
