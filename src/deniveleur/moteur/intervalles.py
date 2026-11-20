"""Intervalles en côte : monter et redescendre N fois la même côte.

Le moteur « boucle » interdit les demi-tours et les passages en double. Ici, c'est
tout le contraire, mais de façon voulue : le parcours est

    échauffement (départ → pied de la côte)
    N × [ montée, puis redescente par le même chemin ]
    retour au départ (par un autre chemin si possible)

On ne cherche donc pas au hasard : on passe en revue toutes les côtes possibles
autour du départ (entre deux points d'ancrage), on garde celles dont la longueur
totale tient dans la distance demandée, et on retient celles qui rapportent le plus
de D+.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from deniveleur.moteur.boucle import Evaluateur, Mesure
from deniveleur.moteur.chemins import Chemins
from deniveleur.moteur.graphe import Graphe


@dataclass
class Plan:
    """Un parcours d'intervalles : ses arcs, sa mesure et sa structure."""

    arcs: list[int]
    mesure: Mesure
    repetitions: int
    arcs_echauffement: int
    arcs_montee: int
    arcs_retour: int
    bas: int  # numéro de carrefour du pied de côte
    haut: int
    montee_m: float
    denivele_m: float


def _chemin_vers(graphe: Graphe, precedent: np.ndarray, cible: int) -> list[int] | None:
    arcs: list[int] = []
    courant = cible
    while courant != graphe.depart:
        avant = int(precedent[courant])
        if avant < 0:
            return None
        arcs.append(graphe.arc_entre[(avant, courant)])
        courant = avant
    arcs.reverse()
    return arcs


def _alourdir(matrice: csr_matrix, graphe: Graphe, arcs: list[int], facteur: float) -> csr_matrix:
    """Copie de la matrice où les tronçons de `arcs` comptent `facteur` fois plus longs."""
    poids = matrice.data.copy()
    for arc in arcs:
        u, v = int(graphe.arc_de[arc]), int(graphe.arc_vers[arc])
        for ligne, colonne in ((u, v), (v, u)):
            debut, fin = matrice.indptr[ligne], matrice.indptr[ligne + 1]
            position = debut + np.searchsorted(matrice.indices[debut:fin], colonne)
            if position < fin and matrice.indices[position] == colonne:
                poids[position] *= facteur
    return csr_matrix((poids, matrice.indices, matrice.indptr), shape=matrice.shape)


def chercher(
    graphe: Graphe,
    chemins: Chemins,
    evaluateur: Evaluateur,
    r: dict[str, Any],
    distance_m: float,
    tolerance: float,
    repetitions: int,
    propositions: int,
) -> tuple[list[Plan], int, int]:
    """Meilleurs plans d'intervalles. Renvoie (plans, côtes examinées, plans réalisables)."""
    l_min, l_max = distance_m * (1 - tolerance), distance_m * (1 + tolerance)

    # 1. Toutes les côtes possibles : de chaque ancre vers chacune de ses voisines.
    montees: list[tuple[float, int, int, list[int], float, float]] = []
    for ancre in range(1, len(chemins.ancres)):
        liaisons = chemins.liaisons(ancre)
        for rang, voisine in enumerate(liaisons.voisines):
            arcs = liaisons.arcs[rang]
            longueur = float(liaisons.longueur[rang])
            if not arcs or not np.isfinite(longueur):
                continue
            net = float(liaisons.montee[rang] - liaisons.descente[rang])
            if not r["longueur_min_m"] <= longueur <= r["longueur_max_m"]:
                continue
            if net < r["denivele_min_m"] or net < r["rectitude_min"] * liaisons.montee[rang]:
                continue
            pente = net / longueur * 100
            if not r["pente_moyenne_min_pct"] <= pente <= r["pente_moyenne_max_pct"]:
                continue
            montees.append((net, ancre, int(voisine), arcs, longueur, pente))

    # 2. Pré-tri grossier : longueur à peu près compatible, le plus de D+ d'abord.
    retour = chemins.retour
    candidates = []
    for net, bas, haut, arcs, longueur, _ in montees:
        approche = float(retour[bas])
        total = 2 * repetitions * longueur + 2 * approche
        if 0.8 * l_min <= total <= l_max * 1.02:
            candidates.append((repetitions * net - 0.2 * approche, net, bas, haut, arcs, longueur))
    candidates.sort(key=lambda c: -c[0])

    # 3. Construction complète des meilleures : échauffement, répétitions, retour.
    _, precedent = dijkstra(
        graphe.matrice, directed=False, indices=graphe.depart, return_predecessors=True
    )
    plans: list[Plan] = []
    for _, net, bas, haut, montee, longueur in candidates[: r["candidats_max"]]:
        noeud_bas = int(chemins.ancres[bas])
        echauffement = _chemin_vers(graphe, precedent, noeud_bas)
        if echauffement is None:
            continue
        # Le retour évite l'échauffement (et la côte) tant que ce n'est pas trop long.
        penalisee = _alourdir(
            graphe.matrice,
            graphe,
            echauffement + montee,
            r["retour_penalite"],
        )
        _, prec = dijkstra(penalisee, directed=False, indices=noeud_bas, return_predecessors=True)
        retour_arcs: list[int] = []
        courant = graphe.depart
        while courant != noeud_bas:
            avant = int(prec[courant])
            if avant < 0:
                retour_arcs = []
                break
            retour_arcs.append(graphe.arc_entre[(avant, courant)])
            courant = avant
        else:
            retour_arcs.reverse()
        if not retour_arcs and noeud_bas != graphe.depart:
            continue
        descente = [arc ^ 1 for arc in reversed(montee)]
        arcs = echauffement + (montee + descente) * repetitions + retour_arcs
        total = float(graphe.arc_longueur[np.asarray(arcs)].sum())
        if not l_min <= total <= l_max:
            continue
        mesure = evaluateur.mesurer(arcs)
        plans.append(
            Plan(
                arcs=arcs,
                mesure=mesure,
                repetitions=repetitions,
                arcs_echauffement=len(echauffement),
                arcs_montee=len(montee),
                arcs_retour=len(retour_arcs),
                bas=noeud_bas,
                haut=int(chemins.ancres[haut]),
                montee_m=longueur,
                denivele_m=net,
            )
        )

    # 4. Les meilleurs, sans deux fois la même côte.
    plans.sort(key=lambda p: -p.mesure.dplus_m)
    retenus: list[Plan] = []
    for plan in plans:
        cote = {arc >> 1 for arc in plan.arcs[plan.arcs_echauffement :][: plan.arcs_montee]}
        deja = [
            {arc >> 1 for arc in autre.arcs[autre.arcs_echauffement :][: autre.arcs_montee]}
            for autre in retenus
        ]
        if any(len(cote & d) > 0.5 * min(len(cote), len(d)) for d in deja):
            continue
        if any(
            np.hypot(graphe.x[plan.bas] - graphe.x[a.bas], graphe.y[plan.bas] - graphe.y[a.bas])
            < r["distance_min_entre_cotes_m"]
            for a in retenus
        ):
            continue
        retenus.append(plan)
        if len(retenus) == propositions:
            break
    return retenus, len(montees), len(plans)
