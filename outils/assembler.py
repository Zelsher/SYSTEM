#!/usr/bin/env python3
"""Assemble l'index statique lu par Flatpak (``<site>/index/static``) depuis ``entrees/*.json``.

Flatpak demande ``<adresse>/index/static?label:org.flatpak.ref:exists=1&…`` ; un hébergement
statique ignore la requête et sert le fichier. Chaque système tient sa propre entrée (une par
appli), écrite par sa publication (``.github/workflows/publier.yml``).

    assembler.py <dossier des entrées> <dossier du site>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REGISTRY = "https://ghcr.io/"


def assemble(entries: Path) -> dict:
    results = []
    seen: dict[str, str] = {}
    for path in sorted(entries.glob("*.json")):
        item = json.loads(path.read_text())
        for image in item["Images"]:
            ref = image["Labels"]["org.flatpak.ref"]
            if ref in seen:
                raise SystemExit(f"{ref} déclaré deux fois : {seen[ref]} et {path.name}")
            seen[ref] = path.name
        results.append(item)
    return {"Registry": REGISTRY, "Results": results}


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        raise SystemExit(__doc__)
    site = Path(argv[2])
    (site / "index").mkdir(parents=True, exist_ok=True)
    index = assemble(Path(argv[1]))
    (site / "index" / "static").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"{len(index['Results'])} appli(s) dans l'index")


if __name__ == "__main__":
    main(sys.argv)
