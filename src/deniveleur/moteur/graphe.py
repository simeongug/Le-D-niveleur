"""Graphe de recherche : la partie du réseau utile pour une boucle donnée.

À partir du réseau complet, on ne garde que ce qui peut servir : les tronçons
atteignables depuis le départ, sans les culs-de-sac (un demi-tour y serait
obligatoire) ni les pentes invraisemblables. Chaque tronçon devient deux
« arcs », un par sens de parcours, parce que le D+ dépend du sens.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from deniveleur.reseau import Reseau

Tableau = NDArray[np.float64]
Entiers = NDArray[np.int32]


@dataclass
class Graphe:
    """Arcs numérotés 2·t (sens du tronçon t) et 2·t + 1 (sens inverse)."""

    x: Tableau  # carrefours
    y: Tableau
    z: Tableau
    arc_de: Entiers
    arc_vers: Entiers
    arc_longueur: Tableau
    arc_gain: Tableau  # D+ brut de l'arc, sans seuil
    arc_troncon: Entiers  # position du tronçon dans le réseau d'origine
    arc_chemin: NDArray[np.bool_]  # vrai = sentier ou piste
    cap_debut: Tableau  # direction (vecteur unitaire) au départ de l'arc, forme (arcs, 2)
    cap_fin: Tableau  # direction à l'arrivée
    # Altitudes le long de chaque arc, premier point exclu (c'est le carrefour de départ).
    profils: list[list[float]]
    # Points le long de chaque arc (premier point exclu), rangés bout à bout.
    debut_points: NDArray[np.int64]
    points_x: Tableau
    points_y: Tableau
    matrice: csr_matrix  # longueurs, pour les plus courts chemins
    arc_entre: dict[tuple[int, int], int]  # (carrefour, carrefour voisin) -> arc le plus court
    depart: int

    @property
    def nombre_noeuds(self) -> int:
        return len(self.x)

    @property
    def nombre_arcs(self) -> int:
        return len(self.arc_de)

    def points(self, arc: int) -> tuple[Tableau, Tableau]:
        debut, fin = self.debut_points[arc], self.debut_points[arc + 1]
        return self.points_x[debut:fin], self.points_y[debut:fin]


def sans_culs_de_sac(
    depart: Entiers, arrivee: Entiers, garde: NDArray[np.bool_], nombre_noeuds: int
) -> NDArray[np.bool_]:
    """Retire, de proche en proche, les tronçons qui mènent à une impasse."""
    garde = garde.copy()
    while True:
        degre = np.bincount(depart[garde], minlength=nombre_noeuds) + np.bincount(
            arrivee[garde], minlength=nombre_noeuds
        )
        impasse = garde & ((degre[depart] == 1) | (degre[arrivee] == 1))
        if not impasse.any():
            return garde
        garde &= ~impasse


def _matrice(depart: Entiers, arrivee: Entiers, longueur: Tableau, nombre: int) -> csr_matrix:
    """Matrice symétrique des longueurs ; entre deux mêmes carrefours, le plus court tronçon."""
    a, b = np.minimum(depart, arrivee), np.maximum(depart, arrivee)
    ordre = np.lexsort((longueur, b, a))
    a, b, valeurs = a[ordre], b[ordre], longueur[ordre]
    premier = np.ones(len(a), bool)
    premier[1:] = (a[1:] != a[:-1]) | (b[1:] != b[:-1])
    a, b, valeurs = a[premier], b[premier], np.maximum(valeurs[premier], 0.01)
    return csr_matrix(
        (np.concatenate([valeurs, valeurs]), (np.concatenate([a, b]), np.concatenate([b, a]))),
        shape=(nombre, nombre),
    )


def construire(
    reseau: Reseau, depart_x: float, depart_y: float, distance_m: float, reglages: dict[str, Any]
) -> Graphe:
    """Prépare le graphe pour une boucle de `distance_m` partant près de (depart_x, depart_y)."""
    nombre = len(reseau.noeud_x)
    dep, arr = reseau.depart, reseau.arrivee
    garde = dep != arr
    # Pente maximale choisie par la personne (jamais au-delà de la limite « plausible »).
    pente_limite = min(
        reglages["pente_max_plausible_pct"], reglages.get("pente_max_pct") or float("inf")
    )
    garde &= reseau.escalier | (reseau.pente_max <= pente_limite)
    if reglages.get("sans_bitume", False):
        garde &= reseau.chemin | reseau.escalier
    if not reglages["escaliers"]:
        garde &= ~reseau.escalier
    garde = sans_culs_de_sac(dep, arr, garde, nombre)

    # Point de départ : le carrefour utilisable le plus proche.
    utilisable = np.zeros(nombre, bool)
    utilisable[dep[garde]] = True
    utilisable[arr[garde]] = True
    ecart = np.hypot(reseau.noeud_x - depart_x, reseau.noeud_y - depart_y)
    ecart[~utilisable] = np.inf
    origine = int(np.argmin(ecart))
    if ecart[origine] > reglages["ecart_depart_max_m"]:
        raise ValueError(
            f"Aucun chemin utilisable à moins de {reglages['ecart_depart_max_m']} m du départ"
            " avec ces préférences (essayer de les assouplir)."
        )

    # On ne garde que ce qui est assez proche pour tenir dans la boucle.
    matrice = _matrice(dep[garde], arr[garde], reseau.longueur[garde], nombre)
    rayon = distance_m * reglages["rayon_max_part"]
    eloignement = dijkstra(matrice, directed=False, indices=origine, limit=rayon)
    garde &= np.isfinite(eloignement[dep]) & np.isfinite(eloignement[arr])
    garde = sans_culs_de_sac(dep, arr, garde, nombre)
    matrice = _matrice(dep[garde], arr[garde], reseau.longueur[garde], nombre)
    _, composante = connected_components(matrice, directed=False)
    garde &= composante[dep] == composante[origine]

    # Renumérotation des carrefours conservés.
    troncons = np.flatnonzero(garde).astype(np.int32)
    anciens = np.unique(np.concatenate([dep[troncons], arr[troncons]]))
    nouveau = np.full(nombre, -1, np.int32)
    nouveau[anciens] = np.arange(len(anciens), dtype=np.int32)
    u, v = nouveau[dep[troncons]], nouveau[arr[troncons]]
    longueur = reseau.longueur[troncons]

    arcs = 2 * len(troncons)
    arc_de = np.empty(arcs, np.int32)
    arc_vers = np.empty(arcs, np.int32)
    arc_de[0::2], arc_vers[0::2] = u, v
    arc_de[1::2], arc_vers[1::2] = v, u
    arc_gain = np.empty(arcs)
    arc_gain[0::2], arc_gain[1::2] = reseau.gain_aller[troncons], reseau.gain_retour[troncons]

    cap_debut, cap_fin = np.zeros((arcs, 2)), np.zeros((arcs, 2))
    profils: list[list[float]] = []
    morceaux_x, morceaux_y, tailles = [], [], []
    portee = reglages["portee_cap_points"]
    for rang, troncon in enumerate(troncons):
        x, y, z = reseau.trace(int(troncon))
        k = min(portee, len(x) - 1)
        vers_avant = np.array([x[k] - x[0], y[k] - y[0]])
        vers_fin = np.array([x[-1] - x[-1 - k], y[-1] - y[-1 - k]])
        vers_avant /= max(np.hypot(*vers_avant), 1e-9)
        vers_fin /= max(np.hypot(*vers_fin), 1e-9)
        cap_debut[2 * rang], cap_fin[2 * rang] = vers_avant, vers_fin
        cap_debut[2 * rang + 1], cap_fin[2 * rang + 1] = -vers_fin, -vers_avant
        profils.append(z[1:].tolist())
        profils.append(z[-2::-1].tolist())
        morceaux_x += [x[1:], x[-2::-1]]
        morceaux_y += [y[1:], y[-2::-1]]
        tailles += [len(x) - 1, len(x) - 1]

    arc_entre: dict[tuple[int, int], int] = {}
    arc_longueur = np.repeat(longueur, 2)
    for arc in np.argsort(-arc_longueur, kind="stable"):  # le plus court écrit en dernier
        arc_entre[(int(arc_de[arc]), int(arc_vers[arc]))] = int(arc)

    return Graphe(
        x=reseau.noeud_x[anciens],
        y=reseau.noeud_y[anciens],
        z=reseau.noeud_z[anciens],
        arc_de=arc_de,
        arc_vers=arc_vers,
        arc_longueur=arc_longueur,
        arc_gain=arc_gain,
        arc_troncon=np.repeat(troncons, 2),
        arc_chemin=np.repeat(reseau.chemin[troncons], 2),
        cap_debut=cap_debut,
        cap_fin=cap_fin,
        profils=profils,
        debut_points=np.concatenate([[0], np.cumsum(tailles)]).astype(np.int64),
        points_x=np.concatenate(morceaux_x),
        points_y=np.concatenate(morceaux_y),
        matrice=_matrice(u, v, longueur, len(anciens)),
        arc_entre=arc_entre,
        depart=int(nouveau[origine]),
    )
