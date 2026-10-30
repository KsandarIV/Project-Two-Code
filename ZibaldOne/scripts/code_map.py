"""Regenerate docs/tecnica/mappa-codice.md: size per layer, import hubs, biggest modules.

Usage (from the ZibaldOne folder): python scripts/code_map.py
Only the standard library; reads src/zibaldone with `ast`.
"""

import ast
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "zibaldone"
OUT = ROOT / "docs" / "tecnica" / "mappa-codice.md"
LAYERS = ("core", "storage", "cli", "cloud", "notify", "packs", "ui")


def module_name(path: Path) -> str:
    parts = path.relative_to(SRC.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def scan():
    modules = {}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = (ast.get_docstring(tree) or "").strip().splitlines()
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
        modules[module_name(path)] = {
            "lines": len(path.read_text(encoding="utf-8").splitlines()),
            "doc": doc[0] if doc else "",
            "imports": {i for i in imports if i.startswith("zibaldone")},
        }
    return modules


def layer(name: str) -> str:
    parts = name.split(".")
    return parts[1] if len(parts) > 1 and parts[1] in LAYERS else "(radice)"


def main() -> None:
    modules = scan()
    by_layer = defaultdict(list)
    for name in modules:
        by_layer[layer(name)].append(name)
    incoming = Counter(i for m in modules.values() for i in m["imports"] if i in modules)
    broken = [
        f"{n} -> {i}"
        for n, m in modules.items()
        if layer(n) == "core"
        for i in m["imports"]
        if layer(i) in ("ui", "cli", "storage")
    ]
    lines = [
        "# Mappa del codice",
        "",
        f"Generata da `scripts/code_map.py` il {date.today().isoformat()}. Si rigenera a ogni PR di rilascio.",
        f"{len(modules)} moduli in `src/zibaldone/`. Regola: `core` non importa `ui`, `cli`, `storage`"
        + (f" (violata da: {', '.join(broken)})." if broken else " (rispettata)."),
        "",
        "## Livelli",
    ]
    for lay in (*LAYERS, "(radice)"):
        names = by_layer.get(lay)
        if names:
            total = sum(modules[n]["lines"] for n in names)
            lines.append(f"- **{lay}**: {len(names)} moduli, {total} righe")
    lines += ["", "## Moduli più usati (import in ingresso)"]
    for name, count in incoming.most_common(12):
        lines.append(f"- `{name}` ({count}): {modules[name]['doc'] or modules[name]['lines']} ".rstrip())
    lines += ["", "## Moduli più grandi"]
    for name in sorted(modules, key=lambda n: -modules[n]["lines"])[:8]:
        lines.append(f"- `{name}`: {modules[name]['lines']} righe")
    lines += ["", "Per lo scopo di un modulo: la prima riga del suo docstring."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"scritto {OUT} ({OUT.stat().st_size} byte)")


if __name__ == "__main__":
    main()
