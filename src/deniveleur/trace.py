"""D+ d'un tracé existant (fichier GPX ou tracé Strava) d'après notre modèle d'altitude.

Sert à vérifier que nos chiffres de dénivelé sont cohérents avec ceux de Strava.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from deniveleur import geo, profil
from deniveleur.donnees.altitude import ModeleAltitude


@dataclass
class Mesure:
    distance_m: float
    dplus_m: float
    dmoins_m: float
    altitude_min_m: float
    altitude_max_m: float


def lire_gpx(chemin: Path) -> tuple[np.ndarray, np.ndarray]:
    """Renvoie (longitudes, latitudes) des points de trace d'un fichier GPX."""
    points = [
        (float(element.attrib["lon"]), float(element.attrib["lat"]))
        for element in ET.parse(chemin).iter()
        if element.tag.endswith("}trkpt") or element.tag.endswith("}rtept")
    ]
    if len(points) < 2:
        raise ValueError(f"Aucune trace trouvée dans {chemin}.")
    longitudes, latitudes = zip(*points, strict=True)
    return np.array(longitudes), np.array(latitudes)


def decoder_polyline(texte: str) -> tuple[np.ndarray, np.ndarray]:
    """Décode un tracé au format compact de Strava/Google. Renvoie (longitudes, latitudes)."""
    valeurs: list[int] = []
    courant, decalage = 0, 0
    for caractere in texte:
        morceau = ord(caractere) - 63
        courant |= (morceau & 0x1F) << decalage
        decalage += 5
        if morceau < 0x20:
            valeurs.append(~(courant >> 1) if courant & 1 else courant >> 1)
            courant, decalage = 0, 0
    latitudes = np.cumsum(valeurs[0::2]) / 1e5
    longitudes = np.cumsum(valeurs[1::2]) / 1e5
    return longitudes, latitudes


def mesurer(
    longitudes: np.ndarray,
    latitudes: np.ndarray,
    altitude: ModeleAltitude,
    reglages: dict[str, Any],
) -> Mesure:
    """Distance et dénivelé d'un tracé, avec les mêmes réglages que le réseau."""
    x, y = geo.gps_vers_l93(longitudes, latitudes)
    x, y, distances = profil.densifier(x, y, reglages["pas_m"])
    z = profil.lisser(altitude.altitude(x, y), reglages["pas_m"], reglages["lissage_m"])
    dplus, dmoins = profil.gains_hysteresis(z, reglages["hysteresis_m"])
    return Mesure(float(distances[-1]), dplus, dmoins, float(z.min()), float(z.max()))
