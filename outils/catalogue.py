#!/usr/bin/env python3
"""Fait l'index lu par Flatpak (``<site>/index/static``) en lisant les images des systèmes sur ghcr.io.

Le catalogue lit l'entrepôt ; aucun système n'écrit ici (ADR 0140 d'ARRSA) : la seule chose qui puisse
changer l'index est ce dépôt, avec le jeton éphémère de son propre robot. Pour chaque système de
``systemes.toml``, on lit le manifeste de l'image (son empreinte est celle que Flatpak vérifiera) et sa
configuration (les étiquettes ``org.flatpak.*`` : identifiant, permissions, taille). Rien d'autre du paquet
n'est lu, et aucun code n'arrive ici.

Une image illisible fait échouer tout le catalogue : l'index publié reste l'ancien, et l'échec se voit
(courriel de GitHub), au lieu d'un système qui disparaîtrait sans bruit.

    catalogue.py <systemes.toml> <dossier du site>    (skopeo connecté à ghcr.io)
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REGISTRY = "ghcr.io"
OWNER = "zelsher"
APP_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}$")
PACKAGE = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*$")
ARCHES = {"x86_64": "amd64", "aarch64": "arm64"}
TAG = "latest"
# Pour ajouter le dépôt à la main : flatpak remote-add --from <site>/arrsa-systemes.flatpakrepo
# (ARRSA OS le déclare déjà dans son image). Pas de clé GPG : dépôt OCI.
FLATPAKREPO = """[Flatpak Repo]
Title=Systèmes d'ARRSA
Url=oci+https://zelsher.github.io/arrsa-systemes
Homepage=https://github.com/Zelsher/arrsa-systemes
Comment=Paquets privés sur ghcr.io : un jeton read:packages est nécessaire
"""


def skopeo(*args: str) -> bytes:
    return subprocess.run(["skopeo", "inspect", "--raw", *args], check=True, capture_output=True).stdout


def read_list(path: Path) -> list[dict]:
    systems = tomllib.loads(path.read_text())["systeme"]
    seen: set[str] = set()
    for s in systems:
        if not (APP_ID.match(s["appli"]) and PACKAGE.match(s["paquet"])):
            raise SystemExit(f"{path} : appli ou paquet invalide : {s}")
        if s["appli"] in seen:
            raise SystemExit(f"{path} : {s['appli']} déclaré deux fois")
        seen.add(s["appli"])
    return systems


def entry(system: dict, manifest: bytes, config: dict) -> dict:
    """L'entrée d'index d'une image, à partir de son manifeste brut et de sa configuration."""
    labels = config["config"]["Labels"]
    parts = labels.get("org.flatpak.ref", "").split("/")
    # Un paquet ne peut pas se faire passer pour une autre appli que celle déclarée pour lui.
    if len(parts) != 4 or parts[:2] != ["app", system["appli"]] or "org.flatpak.metadata" not in labels:
        raise SystemExit(f"{system['paquet']} : org.flatpak.ref {labels.get('org.flatpak.ref')!r} "
                         f"n'est pas l'appli {system['appli']}")
    return {
        "Name": f"{OWNER}/{system['paquet']}",
        "Images": [{
            "Tags": [TAG],
            "Digest": "sha256:" + hashlib.sha256(manifest).hexdigest(),
            "MediaType": json.loads(manifest)["mediaType"],
            "OS": "linux",
            "Architecture": ARCHES.get(parts[2], parts[2]),
            "Labels": labels,
        }],
        "Lists": [],
    }


def build(systems: list[dict]) -> dict:
    results = []
    for system in systems:
        image = f"docker://{REGISTRY}/{OWNER}/{system['paquet']}:{TAG}"
        results.append(entry(system, skopeo(image), json.loads(skopeo("--config", image))))
    return {"Registry": f"https://{REGISTRY}/", "Results": results}


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        raise SystemExit(__doc__)
    index = build(read_list(Path(argv[1])))
    site = Path(argv[2])
    (site / "index").mkdir(parents=True, exist_ok=True)
    (site / "index" / "static").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    (site / "arrsa-systemes.flatpakrepo").write_text(FLATPAKREPO)
    print(f"{len(index['Results'])} appli(s) dans l'index")


if __name__ == "__main__":
    main(sys.argv)
