"""Points d'ancrage (hauts et bas de versants) et plus courts chemins entre eux."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from deniveleur.moteur.graphe import Graphe


@dataclass
class Liaisons:
    """Liaisons d'une ancre vers ses voisines (une ligne par voisine)."""

    voisines: NDArray[np.intp]  # numéros d'ancre
    longueur: NDArray[np.float64]  # inf si pas de liaison utilisable
    montee: NDArray[np.float64]
    descente: NDArray[np.float64]
    chemin: NDArray[np.float64]  # longueur sur sentier ou piste
    arcs: list[list[int] | None]


def choisir_ancres(graphe: Graphe, reglages: dict[str, Any]) -> NDArray[np.intp]:
    """Carrefours le plus haut et le plus bas de chaque case qui a du relief.

    L'ancre n° 0 est toujours le point de départ.
    """
    case = reglages["ancre_case_m"]
    cle = (graphe.x // case).astype(np.int64) * (1 << 20) + (graphe.y // case).astype(np.int64)
    ordre = np.lexsort((graphe.z, cle))
    cles = cle[ordre]
    debut = np.flatnonzero(np.r_[True, cles[1:] != cles[:-1]])
    fin = np.r_[debut[1:], len(cles)] - 1
    bas, haut = ordre[debut], ordre[fin]
    relief = graphe.z[haut] - graphe.z[bas] >= reglages["ancre_relief_min_m"]
    ancres = np.unique(np.concatenate([bas[relief], haut[relief]]))
    ancres = ancres[ancres != graphe.depart]
    return np.concatenate([[graphe.depart], ancres])


class Chemins:
    """Calcule à la demande, et garde en mémoire, les liaisons entre ancres."""

    def __init__(self, graphe: Graphe, reglages: dict[str, Any]):
        self.g = graphe
        self.reglages = reglages
        self.ancres = choisir_ancres(graphe, reglages)
        self.x, self.y = graphe.x[self.ancres], graphe.y[self.ancres]
        self.z = graphe.z[self.ancres]
        positions = np.c_[self.x, self.y]
        nombre = min(reglages["voisines"] + 1, len(self.ancres))
        _, voisines = cKDTree(positions).query(positions, k=nombre)
        self.voisines = voisines[:, 1:]
        # Distance de chaque ancre au départ, par le plus court chemin.
        self.retour = dijkstra(graphe.matrice, directed=False, indices=graphe.depart)[self.ancres]
        self.cos_demi_tour = float(np.cos(np.radians(reglages["angle_demi_tour_deg"])))
        self._liaisons: dict[int, Liaisons] = {}
        self._chemins: dict[tuple[int, int], list[int] | None] = {}

    def _remonter(self, precedent: list[int], racine: int, cible: int) -> list[int] | None:
        arcs: list[int] = []
        noeud = cible
        arc_entre = self.g.arc_entre
        while noeud != racine:
            avant = precedent[noeud]
            if avant < 0:
                return None
            arcs.append(arc_entre[(avant, noeud)])
            noeud = avant
        arcs.reverse()
        return arcs

    def sans_demi_tour(self, arcs: list[int]) -> bool:
        if len(arcs) < 2:
            return True
        tableau = np.asarray(arcs)
        cosinus = (self.g.cap_fin[tableau[:-1]] * self.g.cap_debut[tableau[1:]]).sum(axis=1)
        return bool((cosinus >= self.cos_demi_tour).all())

    def liaisons(self, ancre: int) -> Liaisons:
        """Liaisons de `ancre` vers ses voisines, par le plus court chemin."""
        connues = self._liaisons.get(ancre)
        if connues is not None:
            return connues
        g = self.g
        racine = int(self.ancres[ancre])
        _, precedent = dijkstra(
            g.matrice,
            directed=False,
            indices=racine,
            return_predecessors=True,
            limit=self.reglages["liaison_max_m"],
        )
        precedents = precedent.tolist()
        voisines = self.voisines[ancre]
        nombre = len(voisines)
        longueur = np.full(nombre, np.inf)
        montee, descente, chemin = np.zeros(nombre), np.zeros(nombre), np.zeros(nombre)
        liste: list[list[int] | None] = []
        for rang, voisine in enumerate(voisines):
            arcs = self._remonter(precedents, racine, int(self.ancres[voisine]))
            if arcs and self.sans_demi_tour(arcs):
                tableau = np.asarray(arcs)
                longueur[rang] = g.arc_longueur[tableau].sum()
                montee[rang] = g.arc_gain[tableau].sum()
                descente[rang] = g.arc_gain[tableau ^ 1].sum()
                chemin[rang] = g.arc_longueur[tableau][g.arc_chemin[tableau]].sum()
            else:
                arcs = None
            liste.append(arcs)
            self._chemins[(ancre, int(voisine))] = arcs
        resultat = Liaisons(voisines, longueur, montee, descente, chemin, liste)
        self._liaisons[ancre] = resultat
        return resultat

    def chemin(self, de: int, vers: int) -> list[int] | None:
        """Plus court chemin entre deux ancres quelconques (None si trop loin)."""
        cle = (de, vers)
        if cle not in self._chemins:
            self.liaisons(de)
        if cle not in self._chemins:
            racine = int(self.ancres[de])
            _, precedent = dijkstra(
                self.g.matrice, directed=False, indices=racine, return_predecessors=True
            )
            self._chemins[cle] = self._remonter(precedent.tolist(), racine, int(self.ancres[vers]))
        return self._chemins[cle]
