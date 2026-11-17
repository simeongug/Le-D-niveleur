"""Altitude du terrain : dalles IGN RGE ALTI et lecture de l'altitude en un point."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import numpy as np
from numpy.typing import NDArray

from deniveleur import geo
from deniveleur.donnees import telechargement as tele

journal = logging.getLogger(__name__)

Tableau = NDArray[np.float64]


def coins_des_dalles(emprise: geo.Emprise, taille_m: int) -> list[tuple[int, int]]:
    """Coin sud-ouest de chaque dalle nécessaire pour couvrir l'emprise."""
    ouest, sud, est, nord = (int(v) for v in emprise)
    if any(v % taille_m for v in (ouest, sud, est, nord)):
        raise ValueError(f"L'emprise doit tomber sur des multiples de {taille_m} m.")
    return [(x, y) for y in range(sud, nord, taille_m) for x in range(ouest, est, taille_m)]


def nom_dalle(x: int, y: int, resolution_m: int) -> str:
    return f"alti_{resolution_m}m_{x}_{y}.tif"


def url_dalle(parametres: dict[str, Any], x: int, y: int) -> str:
    taille, resolution = parametres["taille_dalle_m"], parametres["resolution_m"]
    pixels = taille // resolution
    requete = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": parametres["couche"],
        "STYLES": "",
        "CRS": "EPSG:2154",
        "BBOX": f"{x},{y},{x + taille},{y + taille}",
        "WIDTH": pixels,
        "HEIGHT": pixels,
        "FORMAT": "image/geotiff",
    }
    return f"{parametres['url']}?{urlencode(requete)}"


def telecharger_dalles(parametres: dict[str, Any], emprise: geo.Emprise, dossier: Path) -> int:
    """Télécharge les dalles manquantes ; renvoie le nombre de dalles téléchargées."""
    import tifffile

    resolution = parametres["resolution_m"]
    pixels = parametres["taille_dalle_m"] // resolution
    dossier_dalles = dossier / "altitude"
    manifeste = tele.lire_manifeste(dossier)
    connues: dict[str, Any] = manifeste.setdefault("altitude", {}).setdefault("dalles", {})
    a_faire = [
        (x, y)
        for x, y in coins_des_dalles(emprise, parametres["taille_dalle_m"])
        if not (dossier_dalles / nom_dalle(x, y, resolution)).exists()
        or nom_dalle(x, y, resolution) not in connues
    ]

    def une_dalle(coin: tuple[int, int]) -> tuple[str, dict[str, Any]]:
        x, y = coin
        nom = nom_dalle(x, y, resolution)
        destination = dossier_dalles / nom
        erreur: Exception | None = None
        # Le service renvoie parfois une dalle incomplète : on vérifie et on réessaie.
        for essai in range(1, parametres["essais_par_dalle"] + 1):
            try:
                tele.telecharger(url_dalle(parametres, x, y), destination)
                image = tifffile.imread(destination)
                if image.shape != (pixels, pixels):
                    raise ValueError(f"taille inattendue {image.shape}")
                break
            except (ValueError, ConnectionError, OSError) as exc:
                erreur = exc
                destination.unlink(missing_ok=True)
                journal.warning("Dalle %s, essai %d : %s", nom, essai, exc)
                time.sleep(parametres["pause_entre_essais_s"] * essai)
        else:
            raise ConnectionError(f"Dalle {nom} impossible à télécharger : {erreur}")
        return nom, {
            "telecharge_le": tele.maintenant(),
            "taille_octets": destination.stat().st_size,
            "sha256": tele.empreinte(destination),
        }

    if a_faire:
        journal.info("Téléchargement de %d dalles d'altitude…", len(a_faire))
        with ThreadPoolExecutor(max_workers=4) as groupe:
            for nom, fiche in groupe.map(une_dalle, a_faire):
                connues[nom] = fiche
    manifeste["altitude"].update(
        {
            "source": parametres["url"],
            "couche": parametres["couche"],
            "resolution_m": resolution,
            "licence": "Licence Ouverte Etalab 2.0 — IGN, RGE ALTI®",
        }
    )
    tele.ecrire_manifeste(dossier, manifeste)
    return len(a_faire)


class ModeleAltitude:
    """Altitude du sol sur une emprise, lue dans les dalles déjà téléchargées."""

    def __init__(self, grille: NDArray[np.float32], emprise: geo.Emprise, resolution_m: float):
        self.grille = grille
        self.emprise = emprise
        self.resolution = float(resolution_m)

    @classmethod
    def charger(
        cls, parametres: dict[str, Any], emprise: geo.Emprise, dossier: Path
    ) -> "ModeleAltitude":
        import tifffile

        resolution, taille = parametres["resolution_m"], parametres["taille_dalle_m"]
        ouest, sud, est, nord = (int(v) for v in emprise)
        pixels = taille // resolution
        grille = np.empty(((nord - sud) // resolution, (est - ouest) // resolution), np.float32)
        for x, y in coins_des_dalles(emprise, taille):
            chemin = dossier / "altitude" / nom_dalle(x, y, resolution)
            if not chemin.exists():
                raise FileNotFoundError(
                    f"Dalle manquante : {chemin}. Lancer : deniveleur donnees telecharger"
                )
            ligne = (nord - y - taille) // resolution
            colonne = (x - ouest) // resolution
            grille[ligne : ligne + pixels, colonne : colonne + pixels] = tifffile.imread(chemin)
        manquants = grille < parametres["altitude_min_valide"]
        if manquants.any():
            journal.warning("%d pixels sans altitude, remplacés par la médiane.", manquants.sum())
            grille[manquants] = np.median(grille[~manquants])
        return cls(grille, emprise, resolution)

    def altitude(self, x: Tableau, y: Tableau) -> Tableau:
        """Altitude aux points (x, y) en Lambert-93, par interpolation entre pixels voisins."""
        ouest, _, _, nord = self.emprise
        lignes, colonnes = self.grille.shape
        # Le centre du pixel (0, 0) est à une demi-résolution du coin nord-ouest.
        c = np.clip((np.asarray(x) - ouest) / self.resolution - 0.5, 0, colonnes - 1)
        ligne = np.clip((nord - np.asarray(y)) / self.resolution - 0.5, 0, lignes - 1)
        c0 = np.minimum(c.astype(np.intp), colonnes - 2)
        l0 = np.minimum(ligne.astype(np.intp), lignes - 2)
        fc, fl = c - c0, ligne - l0
        g = self.grille
        haut = g[l0, c0] * (1 - fc) + g[l0, c0 + 1] * fc
        bas = g[l0 + 1, c0] * (1 - fc) + g[l0 + 1, c0 + 1] * fc
        return np.asarray(haut * (1 - fl) + bas * fl, dtype=np.float64)
