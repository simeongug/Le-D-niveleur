"""Mesure d'une boucle : longueur, D+, portions en double, demi-tours."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from deniveleur.moteur.graphe import Graphe

# Les clés de case sont x_case * _BASE + y_case : _BASE doit dépasser le nombre de cases en y.
_BASE = 1 << 20


@dataclass
class Mesure:
    longueur_m: float
    dplus_m: float
    dmoins_m: float
    double_m: float  # passages à quelques mètres d'un autre passage (hors croisements)
    double_exact_m: float  # tronçons empruntés deux fois
    demi_tours: int
    chemin_m: float = 0.0  # longueur sur sentier ou piste


def sans_allers_retours(arcs: list[int]) -> list[int]:
    """Supprime les allers-retours immédiats (un arc suivi de son inverse)."""
    pile: list[int] = []
    for arc in arcs:
        if pile and pile[-1] == arc ^ 1:
            pile.pop()
        else:
            pile.append(arc)
    return pile


class Evaluateur:
    """Calcule les mesures d'une boucle donnée comme une suite d'arcs."""

    def __init__(self, graphe: Graphe, reglages: dict[str, Any], hysteresis_m: float, pas_m: float):
        self.g = graphe
        self.seuil = hysteresis_m
        self.pas = pas_m
        case = reglages["double_case_m"]
        self.cles = (graphe.points_x // case).astype(np.int64) * _BASE + (
            graphe.points_y // case
        ).astype(np.int64)
        self.ecart_points = int(reglages["double_ecart_min_m"] / pas_m)
        self.serie_min = int(reglages["croisement_max_m"] / pas_m)
        self.cos_demi_tour = float(np.cos(np.radians(reglages["angle_demi_tour_deg"])))
        self._voisines = np.array([dx * _BASE + dy for dx in (-1, 0, 1) for dy in (-1, 0, 1)])

    def denivele(self, arcs: list[int]) -> tuple[float, float]:
        """D+ et D− avec seuil, sur le profil complet de la boucle."""
        profils = self.g.profils
        seuil = self.seuil
        reference = float(self.g.z[self.g.arc_de[arcs[0]]])
        montee = descente = 0.0
        for arc in arcs:
            for altitude in profils[arc]:
                ecart = altitude - reference
                if ecart >= seuil:
                    montee += ecart
                    reference = altitude
                elif ecart <= -seuil:
                    descente -= ecart
                    reference = altitude
        return montee, descente

    def en_double(self, arcs: list[int]) -> NDArray[np.bool_]:
        """Pour chaque point de la boucle : passe-t-on ailleurs à quelques mètres de là ?

        « Ailleurs » = à plus de `double_ecart_min_m` le long du parcours. Deux
        trottoirs d'une même rue ou deux allées collées comptent donc comme un
        aller-retour, même si ce sont des tronçons différents.
        """
        debut = self.g.debut_points
        cles = np.concatenate([self.cles[debut[a] : debut[a + 1]] for a in arcs])
        nombre = len(cles)
        rang = np.arange(nombre)
        ordre = np.argsort(cles, kind="stable")
        triees = cles[ordre]
        cases, premier = np.unique(triees, return_index=True)
        dernier = np.append(premier[1:], nombre) - 1
        rang_min, rang_max = ordre[premier], ordre[dernier]
        proche = np.zeros(nombre, bool)
        for decalage in self._voisines:
            cible = cles + decalage
            position = np.minimum(np.searchsorted(cases, cible), len(cases) - 1)
            existe = cases[position] == cible
            loin = (rang_max[position] - rang > self.ecart_points) | (
                rang - rang_min[position] > self.ecart_points
            )
            proche |= existe & loin
        return proche

    def longueur_en_double(self, arcs: list[int]) -> float:
        """Longueur des passages en double, croisements courts non comptés."""
        proche = self.en_double(arcs)
        bords = np.diff(np.concatenate([[0], proche.view(np.int8), [0]]))
        tailles = np.flatnonzero(bords == -1) - np.flatnonzero(bords == 1)
        return float(tailles[tailles > self.serie_min].sum() * self.pas)

    def mesurer(self, arcs: list[int]) -> Mesure:
        g = self.g
        tableau = np.asarray(arcs)
        longueurs = g.arc_longueur[tableau]
        troncons, passages = np.unique(tableau >> 1, return_counts=True)
        repetes = troncons[passages > 1]
        double_exact = float((g.arc_longueur[2 * repetes] * (passages[passages > 1] - 1)).sum())
        cosinus = (g.cap_fin[tableau[:-1]] * g.cap_debut[tableau[1:]]).sum(axis=1)
        montee, descente = self.denivele(arcs)
        return Mesure(
            longueur_m=float(longueurs.sum()),
            dplus_m=montee,
            dmoins_m=descente,
            double_m=self.longueur_en_double(arcs),
            double_exact_m=double_exact,
            demi_tours=int((cosinus < self.cos_demi_tour).sum()),
            chemin_m=float(longueurs[g.arc_chemin[tableau]].sum()),
        )
