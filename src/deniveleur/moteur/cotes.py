"""Côtes pour intervalles : trouver, près du départ, des montées qui tiennent une durée.

On cherche des montées régulières (sans vraie redescente au milieu) dont le temps
estimé à l'allure d'intervalle est proche de la durée demandée — par exemple une côte
d'environ 4 minutes pour des répétitions de 4 minutes. Voir docs/algorithme.md.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse.csgraph import dijkstra

from deniveleur import geo
from deniveleur.moteur import graphe as module_graphe
from deniveleur.moteur import temps
from deniveleur.moteur.boucle import Evaluateur
from deniveleur.moteur.chemins import choisir_ancres
from deniveleur.moteur.itineraire import Boucle, assembler
from deniveleur.reseau import Reseau


@dataclass
class Cote:
    """Une côte proposée, avec son tracé (du bas vers le haut)."""

    nom: str
    trace: Boucle  # tracé et profil de la montée seule
    longueur_m: float
    denivele_m: float
    pente_moyenne_pct: float
    pente_max_pct: float
    duree_s: float  # temps estimé d'une montée à l'allure d'intervalle
    approche_m: float  # distance à parcourir depuis le départ pour en atteindre le bas
    part_chemin: float
    escaliers_m: float


def _candidates(
    graphe: module_graphe.Graphe,
    sortants: list[list[int]],
    bas: int,
    duree_s: float,
    allure: float,
    r: dict[str, Any],
    dplus_par_km: float,
) -> list[tuple[list[int], float]]:
    """Montées qui partent du carrefour `bas`, explorées en profondeur.

    À chaque carrefour on ne suit que les `branches` continuations qui montent le
    plus, sans demi-tour ; on s'arrête dès qu'on redescend de plus de `replat_max_m`
    sous le point le plus haut atteint, ou que le temps dépasse la fourchette.
    """
    duree_min = duree_s * (1 - r["tolerance_duree"])
    duree_max = duree_s * (1 + r["tolerance_duree"])
    cos_demi_tour = math.cos(math.radians(r["angle_virage_max_deg"]))
    z, longueurs, gains = graphe.z, graphe.arc_longueur, graphe.arc_gain
    trouvees: list[tuple[list[int], float]] = []
    pile: list[tuple[list[int], float, float, float]] = [([], 0.0, 0.0, float(z[bas]))]
    explorees = 0
    while pile and explorees < r["chemins_explores_par_bas"]:
        arcs, longueur, montee, haut = pile.pop()
        explorees += 1
        ici = int(graphe.arc_vers[arcs[-1]]) if arcs else bas
        if arcs:
            duree = (longueur / 1000 + montee / dplus_par_km) * allure
            pente = (z[ici] - z[bas]) / max(longueur, 1.0) * 100
            if duree_min <= duree <= duree_max and pente >= r["pente_min_pct"]:
                trouvees.append((arcs, duree))
            if duree >= duree_max:
                continue
        vus = {int(graphe.arc_de[a]) for a in arcs} | {ici}
        suites = []
        for arc in sortants[ici]:
            vers = int(graphe.arc_vers[arc])
            if vers in vus:
                continue
            if arcs:
                cosinus = float((graphe.cap_fin[arcs[-1]] * graphe.cap_debut[arc]).sum())
                if cosinus < cos_demi_tour:
                    continue
            nouveau_haut = max(haut, float(z[vers]))
            if nouveau_haut - z[vers] > r["replat_max_m"]:
                continue
            # Ce qui monte le plus par mètre d'abord.
            suites.append(((z[vers] - z[ici]) / max(longueurs[arc], 1.0), arc, nouveau_haut))
        suites.sort(reverse=True)
        for _, arc, nouveau_haut in reversed(suites[: r["branches"]]):
            pile.append(
                (arcs + [arc], longueur + longueurs[arc], montee + gains[arc], nouveau_haut)
            )
    return trouvees


def chercher(
    reseau: Reseau,
    parametres: dict[str, Any],
    latitude: float,
    longitude: float,
    duree_s: float,
    allure_s_par_km: float | None = None,
    rayon_m: float | None = None,
    escaliers: bool = True,
    nombre: int | None = None,
) -> list[Cote]:
    """Côtes proches du départ dont la montée prend environ `duree_s` secondes.

    `allure_s_par_km` : allure à plat pendant l'intervalle (le temps en côte est
    estimé avec la règle « 100 m de D+ ≈ 1 km de plat »). Les côtes sont rangées de
    la meilleure (pente franche, régulière, proche) à la moins bonne.
    """
    r = parametres["cotes"]
    rayon_m = r["rayon_m"] if rayon_m is None else rayon_m
    nombre = r["nombre"] if nombre is None else nombre
    allure = r["allure_s_par_km"] if allure_s_par_km is None else allure_s_par_km
    dplus_par_km = parametres["temps"]["dplus_par_km_effort_m"]

    reglages = dict(parametres["moteur"])
    reglages["escaliers"] = escaliers
    # Une côte peut finir en cul-de-sac : on les garde.
    reglages["culs_de_sac_gardes"] = True
    x, y = geo.gps_vers_l93(np.array([longitude]), np.array([latitude]))
    distance_equivalente = rayon_m / reglages["rayon_max_part"]
    graphe = module_graphe.construire(
        reseau, float(x[0]), float(y[0]), distance_equivalente, reglages
    )
    approche = dijkstra(graphe.matrice, directed=False, indices=graphe.depart)

    sortants: list[list[int]] = [[] for _ in range(graphe.nombre_noeuds)]
    for arc, de in enumerate(graphe.arc_de.tolist()):
        sortants[de].append(arc)

    # Points de départ des côtes : bas de versant, et carrefours plus bas que tous
    # leurs voisins.
    ancres = choisir_ancres(graphe, {**reglages, "ancre_case_m": r["case_bas_m"]})
    voisins_min = np.full(graphe.nombre_noeuds, np.inf)
    np.minimum.at(voisins_min, graphe.arc_de, graphe.z[graphe.arc_vers])
    creux = np.flatnonzero(graphe.z <= voisins_min)
    bas_possibles = np.unique(np.concatenate([ancres, creux]))

    candidates: list[tuple[list[int], float, float]] = []
    for bas in bas_possibles.tolist():
        if not np.isfinite(approche[bas]) or approche[bas] > rayon_m:
            continue
        for arcs, duree in _candidates(graphe, sortants, bas, duree_s, allure, r, dplus_par_km):
            denivele = float(graphe.z[graphe.arc_vers[arcs[-1]]] - graphe.z[bas])
            tableau = np.asarray(arcs)
            descente = float(graphe.arc_gain[tableau ^ 1].sum())
            escaliers_m = float(graphe.arc_longueur[tableau[graphe.arc_escalier[tableau]]].sum())
            note = (
                denivele
                - r["penalite_descente"] * descente
                - r["penalite_escaliers_par_m"] * escaliers_m
                - r["penalite_approche_par_km"] * approche[bas] / 1000
                - r["penalite_ecart_duree_par_pct"] * abs(duree / duree_s - 1) * 100
            )
            candidates.append((arcs, note, float(approche[bas])))

    evaluateur = Evaluateur(
        graphe, reglages, parametres["profil"]["hysteresis_m"], parametres["profil"]["pas_m"]
    )
    reglages_montees = parametres["montees"]
    candidates.sort(key=lambda c: -c[1])
    choisies: list[Cote] = []
    pris: list[set[int]] = []
    for arcs, _, approche_m in candidates:
        troncons = {arc >> 1 for arc in arcs}
        longueur = float(graphe.arc_longueur[arcs].sum())
        if any(
            graphe.arc_longueur[[2 * t for t in troncons & autres]].sum()
            > r["recouvrement_max_part"] * longueur
            for autres in pris
        ):
            continue
        trace = assembler(arcs, evaluateur.mesurer(arcs), graphe, reseau, reglages_montees)
        denivele = float(trace.altitudes[-1] - trace.altitudes[0])
        nom = trace.montees[0].nom if trace.montees else "côte sans nom"
        pente_max = max((m.pente_max_pct for m in trace.montees), default=0.0)
        choisies.append(
            Cote(
                nom=nom,
                trace=trace,
                longueur_m=trace.distance_m,
                denivele_m=denivele,
                pente_moyenne_pct=denivele / max(trace.distance_m, 1.0) * 100,
                pente_max_pct=pente_max,
                duree_s=temps.estimer_s(
                    trace.distance_m, trace.dplus_m, parametres["temps"], allure
                ),
                approche_m=approche_m,
                part_chemin=trace.part_chemin,
                escaliers_m=trace.escaliers_m,
            )
        )
        pris.append(troncons)
        if len(choisies) == nombre:
            break
    return choisies
