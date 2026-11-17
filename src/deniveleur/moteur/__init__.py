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
from deniveleur.moteur.recherche import VOIES, Candidat, Recherche
from deniveleur.reseau import Reseau

__all__ = ["VOIES", "Boucle", "Montee", "Rapport", "generer"]

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
    dplus_cible: float | None = None,
    voies: str = "indifferent",
    allers_retours: bool = False,
) -> tuple[list[Boucle], Rapport]:
    """Cherche les meilleures boucles de `distance_m` partant de (latitude, longitude).

    `dplus_cible` : D+ visé en mètres (None = le plus de D+ possible).
    `chemin_min` : part minimale de sentier ou piste (0 à 1). `escaliers` : False
    pour les éviter (None = réglage par défaut). `voies` : « chemin » ou « route » pour
    privilégier l'un ou l'autre, « indifferent » sinon. `allers_retours` : True pour
    accepter de repasser par un tronçon (une fois dans chaque sens) et les culs-de-sac.

    Renvoie les boucles valides, de la plus riche en D+ à la moins riche (liste
    vide si aucune n'a été trouvée), et un rapport de recherche.
    """
    reglages = dict(parametres["moteur"])
    if escaliers is not None:
        reglages["escaliers"] = escaliers
    reglages["allers_retours_acceptes"] = allers_retours
    tolerance = reglages["tolerance"] if tolerance is None else tolerance
    budget_s = reglages["budget_s"] if budget_s is None else budget_s
    debut = time.perf_counter()
    x, y = geo.gps_vers_l93(np.array([longitude]), np.array([latitude]))
    graphe = module_graphe.construire(reseau, float(x[0]), float(y[0]), distance_m, reglages)
    evaluateur = Evaluateur(
        graphe, reglages, parametres["profil"]["hysteresis_m"], parametres["profil"]["pas_m"]
    )
    chemins = Chemins(graphe, reglages)

    def recherche(avec_allers_retours: bool) -> Recherche:
        return Recherche(
            graphe,
            chemins,
            evaluateur,
            distance_m,
            tolerance,
            reglages,
            graine,
            chemin_min,
            dplus_cible,
            voies,
            avec_allers_retours,
        )

    preparation = time.perf_counter() - debut
    if allers_retours:
        # Allers-retours acceptés : on cherche aussi des boucles strictes, pour ne proposer
        # un aller-retour que s'il rapporte vraiment plus qu'une boucle sans.
        strictes = recherche(False)
        part = reglages["allers_retours"]["part_temps_strict"]
        candidats_stricts, bilan_strict = strictes.chercher(budget_s * part)
        avec = recherche(True)
        candidats, bilan = avec.chercher(budget_s * (1 - part))
        for candidat in candidats_stricts:
            # Même barème que les autres (une boucle stricte n'a aucune pénalité d'aller-retour).
            candidat.note = avec.noter(candidat.mesure)
            candidat.valide = avec.valide(candidat.mesure)
        candidats = sorted(candidats + candidats_stricts, key=lambda c: (-c.valide, -c.note))
        bilan.constructions += bilan_strict.constructions
        bilan.abouties += bilan_strict.abouties
        bilan.valides += bilan_strict.valides
    else:
        candidats, bilan = recherche(False).chercher(budget_s)
    if dplus_cible is None and not allers_retours:
        valides = sorted((c for c in candidats if c.valide), key=lambda c: -c.mesure.dplus_m)
    else:
        valides = sorted((c for c in candidats if c.valide), key=lambda c: -c.note)
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
