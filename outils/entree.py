#!/usr/bin/env python3
"""Écrit l'entrée d'index d'un système à partir de son paquet Flatpak au format OCI.

L'entrée décrit l'image poussée sur ghcr.io : son nom dans le registre, son empreinte (celle du
manifeste réellement poussé) et les étiquettes ``org.flatpak.*`` de sa configuration, que Flatpak
lit pour connaître l'appli sans télécharger le paquet. Rien d'autre du paquet n'en sort : pas de
code, seulement ces métadonnées.

    entree.py <dossier OCI> <nom dans le registre> <empreinte sha256:…> [étiquette…]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
NAME = re.compile(r"^[a-z0-9]+([._/-][a-z0-9]+)*$")
ARCHES = {"x86_64": "amd64", "aarch64": "arm64"}


def blob(layout: Path, digest: str) -> dict:
    algo, value = digest.split(":", 1)
    return json.loads((layout / "blobs" / algo / value).read_text())


def entry(layout: Path, name: str, digest: str, tags: list[str]) -> dict:
    if not NAME.match(name):
        raise SystemExit(f"nom de registre invalide : {name}")
    if not DIGEST.match(digest):
        raise SystemExit(f"empreinte invalide : {digest}")
    manifests = json.loads((layout / "index.json").read_text())["manifests"]
    if len(manifests) != 1:
        raise SystemExit(f"{layout} : un seul paquet attendu, {len(manifests)} trouvés")
    manifest = blob(layout, manifests[0]["digest"])
    labels = blob(layout, manifest["config"]["digest"])["config"]["Labels"]
    ref = labels.get("org.flatpak.ref", "")
    parts = ref.split("/")
    if len(parts) != 4 or parts[0] != "app" or "org.flatpak.metadata" not in labels:
        raise SystemExit(f"{layout} : pas un paquet d'appli Flatpak (org.flatpak.ref = {ref!r})")
    return {
        "Name": name,
        "Images": [
            {
                "Tags": tags or ["latest"],
                "Digest": digest,
                "MediaType": manifests[0]["mediaType"],
                "OS": "linux",
                "Architecture": ARCHES.get(parts[2], parts[2]),
                "Labels": labels,
            }
        ],
        "Lists": [],
    }


def main(argv: list[str]) -> None:
    if len(argv) < 4:
        raise SystemExit(__doc__)
    json.dump(entry(Path(argv[1]), argv[2], argv[3], argv[4:]), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
