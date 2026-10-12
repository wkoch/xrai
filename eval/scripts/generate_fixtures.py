#!/usr/bin/env python3
"""Generate synthetic parser/state fixtures; never count these as real D1 tasks."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def generate(destination: Path, modules: int = 64, statements: int = 2048):
    if modules < 1 or statements < 1:
        raise ValueError("modules and statements must be positive")
    files = {
        "crlf.rs": b"pub fn windows() -> u8 {\r\n    1\r\n}\r\n",
        "unicode.py": "def café():\n    return 'São Paulo 🦉'\n".encode(),
        "homonyms.ts": b"export class A { run() { return 1; } }\nexport class B { run() { return 2; } }\n",
        "no-symbols.js": b"// Intentionally no declarations. Unicode: \xc3\xa1\n",
        "incomplete.go": b"package fixture\nfunc unfinished(\n",
        "component.tsx": b"export function Card() { return <section aria-label='card'>Hello</section>; }\n",
        "component.jsx": b"export function Card() { return <section>Hello</section>; }\n",
        "config/base.json": b'{"exclude":["generated/**"]}\n',
        "config/head.json": b'{"exclude":[]}\n',
        "state/base/old.py": b"def old():\n    return 1\n",
        "state/head/new.py": b"def new():\n    return 2\n",
        "mtime/base.py": b"def same_size():\n    return 1\n",
        "mtime/head.py": b"def same_size():\n    return 2\n",
    }
    files["large.py"] = ("def large():\n    total = 0\n" + "".join(f"    total += {i}\n" for i in range(statements)) + "    return total\n").encode()
    for i in range(modules):
        files[f"generated/module_{i:05d}.rs"] = f"pub fn item_{i}() -> usize {{ {i} }}\n".encode()
    entries = []
    for name, data in sorted(files.items()):
        p = destination / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        os.utime(p, (946684800, 946684800))
        entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mtime_ns": 946684800000000000})
    manifest = {"seed": "no-randomness-v1", "modules": modules, "statements": statements, "files": entries,
                "scenarios": {"crlf": "crlf.rs", "unicode": "unicode.py", "homonyms": "homonyms.ts", "no_symbols": "no-symbols.js", "incomplete": "incomplete.go", "large_function": "large.py", "jsx_tsx": ["component.jsx", "component.tsx"], "configuration_change": ["config/base.json", "config/head.json"], "create_remove": ["state/base/old.py", "state/head/new.py"], "preserved_mtime": ["mtime/base.py", "mtime/head.py"]}}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--modules", type=int, default=64)
    parser.add_argument("--statements", type=int, default=2048)
    args = parser.parse_args()
    generate(args.destination, args.modules, args.statements)
