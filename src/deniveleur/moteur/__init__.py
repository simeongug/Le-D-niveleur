"""Le moteur : trouve des boucles à D+ maximal sur le réseau de chemins.

Il ne connaît ni la ligne de commande, ni l'interface web, ni les régions :
on lui donne un réseau, un point de départ et une distance.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from deniveleur import geo
from deniveleur.moteur import graphe as module_graphe
from deniveleur.moteur.boucle import Evaluateur
from deniveleur.moteur.chemins import Chemins
from deniveleur.moteur.itineraire import Boucle, Montee, assembler
from deniveleur.moteur.recherche import Candidat, Recherche
from deniveleur.reseau import Reseau

__all__ = ["Boucle", "Montee", "Rapport", "generer"]

journal = logging.getLogger(__name__)


@dataclass
class Rapport:
    """Ce qui s'est passé pendant la recherche (pour le journal et les benchmarks)."""

    duree_s: float
    preparation_s: float
    noeuds: int
    ancres: int
    constructions: int
    abouties: int
    valides: int
    ecart_depart_m: float


def _differents(
    candidats: list[Candidat], graphe: Any, nombre: int, part_min: float
) -> list[Candidat]:
    """Les meilleurs candidats, en écartant ceux qui ressemblent trop à un déjà choisi."""
    choisis: list[Candidat] = []
    ensembles: list[set[int]] = []
    for candidat in candidats:
        troncons = {arc >> 1 for arc in candidat.arcs}
        longueur = sum(graphe.arc_longueur[2 * t] for t in troncons)
        trop_proche = False
        for autres in ensembles:
            commun = sum(graphe.arc_longueur[2 * t] for t in troncons & autres)
            if commun > (1 - part_min) * longueur:
                trop_proche = True
                break
        if not trop_proche:
            choisis.append(candidat)
            ensembles.append(troncons)
            if len(choisis) == nombre:
                break
    return choisis


def generer(
    reseau: Reseau,
    parametres: dict[str, Any],
    latitude: float,
    longitude: float,
    distance_m: float,
    tolerance: float | None = None,
    budget_s: float | None = None,
    graine: int = 0,
    propositions: int = 1,
    chemin_min: float = 0.0,
    escaliers: bool | None = None,
) -> tuple[list[Boucle], Rapport]:
    """Cherche les meilleures boucles de `distance_m` partant de (latitude, longitude).

    `chemin_min` : part minimale de sentier ou piste (0 à 1). `escaliers` : False
    pour les éviter (None = réglage par défaut).

    Renvoie les boucles valides, de la plus riche en D+ à la moins riche (liste
    vide si aucune n'a été trouvée), et un rapport de recherche.
    """
    reglages = dict(parametres["moteur"])
    if escaliers is not None:
        reglages["escaliers"] = escaliers
    tolerance = reglages["tolerance"] if tolerance is None else tolerance
    budget_s = reglages["budget_s"] if budget_s is None else budget_s
    debut = time.perf_counter()
    x, y = geo.gps_vers_l93(np.array([longitude]), np.array([latitude]))
    graphe = module_graphe.construire(reseau, float(x[0]), float(y[0]), distance_m, reglages)
    evaluateur = Evaluateur(
        graphe, reglages, parametres["profil"]["hysteresis_m"], parametres["profil"]["pas_m"]
    )
    chemins = Chemins(graphe, reglages)
    recherche = Recherche(
        graphe, chemins, evaluateur, distance_m, tolerance, reglages, graine, chemin_min
    )
    preparation = time.perf_counter() - debut
    candidats, bilan = recherche.chercher(budget_s)
    valides = sorted((c for c in candidats if c.valide), key=lambda c: -c.mesure.dplus_m)
    retenus = _differents(valides, graphe, propositions, reglages["difference_min_part"])
    boucles = [assembler(c.arcs, c.mesure, graphe, reseau, parametres["montees"]) for c in retenus]
    rapport = Rapport(
        duree_s=time.perf_counter() - debut,
        preparation_s=preparation,
        noeuds=graphe.nombre_noeuds,
        ancres=len(chemins.ancres),
        constructions=bilan.constructions,
        abouties=bilan.abouties,
        valides=bilan.valides,
        ecart_depart_m=float(
            np.hypot(graphe.x[graphe.depart] - x[0], graphe.y[graphe.depart] - y[0])
        ),
    )
    journal.info(
        "Recherche : %.1f s (dont %.1f s de préparation), %d carrefours, %d ancres, "
        "%d boucles construites, %d valides, meilleur D+ %s",
        rapport.duree_s,
        preparation,
        rapport.noeuds,
        rapport.ancres,
        bilan.constructions,
        bilan.valides,
        f"{boucles[0].dplus_m:.0f} m" if boucles else "aucun",
    )
    return boucles, rapport
