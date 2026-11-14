"""Chargement des paramètres (fichier `config/parametres.toml`)."""

import tomllib
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

DOSSIER_DONNEES = Path("data")


@cache
def charger() -> dict[str, Any]:
    """Lit le fichier de paramètres livré avec l'application."""
    texte = resources.files("deniveleur.config").joinpath("parametres.toml").read_text("utf-8")
    return tomllib.loads(texte)


def zone(identifiant: str) -> dict[str, Any]:
    zones = charger()["zones"]
    if identifiant not in zones:
        connues = ", ".join(sorted(zones))
        raise KeyError(f"Zone inconnue : {identifiant}. Zones connues : {connues}.")
    return zones[identifiant]


ZONE_PAR_DEFAUT = "saint-cloud-meudon"
