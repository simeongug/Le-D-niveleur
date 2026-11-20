"""Chargement des paramètres (fichier `config/parametres.toml`).

Un **profil** adapte les réglages à une pratique : « course » (par défaut, trail) ou
« velo-route ». Un profil ne redéfinit que ce qui change, section par section
(`[profils.velo-route.moteur]`…) ; tout le reste vient des réglages de base.
"""

import copy
import tomllib
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

DOSSIER_DONNEES = Path("data")
PROFIL_PAR_DEFAUT = "course"


@cache
def _brut() -> dict[str, Any]:
    texte = resources.files("deniveleur.config").joinpath("parametres.toml").read_text("utf-8")
    return tomllib.loads(texte)


@cache
def _charger(profil: str) -> dict[str, Any]:
    base = _brut()
    if profil == PROFIL_PAR_DEFAUT:
        return base
    profils = base.get("profils", {})
    if profil not in profils:
        connus = ", ".join([PROFIL_PAR_DEFAUT, *sorted(profils)])
        raise KeyError(f"Profil inconnu : {profil}. Profils connus : {connus}.")
    fusion = copy.deepcopy(base)
    for section, valeurs in profils[profil].items():
        if isinstance(valeurs, dict):
            fusion.setdefault(section, {}).update(copy.deepcopy(valeurs))
        else:
            fusion[section] = valeurs
    fusion["profil"] = profil
    return fusion


def charger(profil: str = PROFIL_PAR_DEFAUT) -> dict[str, Any]:
    """Lit le fichier de paramètres livré avec l'application, pour un profil donné."""
    return _charger(profil)


def zone(identifiant: str) -> dict[str, Any]:
    zones = _brut()["zones"]
    if identifiant not in zones:
        connues = ", ".join(sorted(zones))
        raise KeyError(f"Zone inconnue : {identifiant}. Zones connues : {connues}.")
    return zones[identifiant]


def profil_de(identifiant: str) -> str:
    """Profil d'une zone (« course » si la fiche n'en précise pas)."""
    return str(zone(identifiant).get("profil", PROFIL_PAR_DEFAUT))


ZONE_PAR_DEFAUT = "ouest-parisien"
