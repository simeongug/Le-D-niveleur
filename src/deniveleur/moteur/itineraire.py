"""Une boucle prête à être montrée : tracé, profil, chiffres, montées, alertes."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from deniveleur import geo
from deniveleur.moteur.boucle import Mesure
from deniveleur.moteur.graphe import Graphe
from deniveleur.reseau import Reseau

Tableau = NDArray[np.float64]


@dataclass
class Montee:
    numero: int
    nom: str
    debut_m: float  # distance depuis le départ
    longueur_m: float
    denivele_m: float
    pente_moyenne_pct: float
    pente_max_pct: float
    bas: tuple[float, float, float]  # longitude, latitude, altitude
    haut: tuple[float, float, float]


@dataclass
class Intervalles:
    """Structure d'une séance d'intervalles : échauffement, N × (montée + redescente), retour."""

    repetitions: int
    echauffement_m: float
    montee_m: float  # longueur d'une montée (la redescente fait la même longueur)
    denivele_m: float  # D+ d'une montée
    retour_m: float


@dataclass
class Boucle:
    longitudes: Tableau
    latitudes: Tableau
    altitudes: Tableau
    distances: Tableau  # distance cumulée depuis le départ, en mètres
    x: Tableau  # mêmes points en Lambert-93, pour les cartes
    y: Tableau
    distance_m: float
    dplus_m: float
    dmoins_m: float
    altitude_min_m: float
    altitude_max_m: float
    part_chemin: float
    escaliers_m: float
    double_m: float
    montees: list[Montee] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)
    troncons: NDArray[np.int32] = field(default_factory=lambda: np.empty(0, np.int32))
    intervalles: Intervalles | None = None


def reperer_montees(
    distances: Tableau, altitudes: Tableau, reglages: dict[str, Any]
) -> list[tuple[int, int]]:
    """Positions (bas, haut) des montées principales le long du profil.

    Une montée va d'un point bas à un point haut ; elle peut contenir de petits
    replats ou redescentes, tant qu'ils restent sous `replat_max_m`.
    """
    replat = reglages["replat_max_m"]
    montees: list[tuple[int, int]] = []
    bas = haut = 0
    monte = False
    for position in range(1, len(altitudes)):
        altitude = altitudes[position]
        if monte:
            if altitude > altitudes[haut]:
                haut = position
            elif altitudes[haut] - altitude > replat:
                montees.append((bas, haut))
                bas, monte = position, False
        elif altitude <= altitudes[bas]:  # sur un plat, le pied de côte avance
            bas = position
        elif altitude - altitudes[bas] > replat:
            haut, monte = position, True
    if monte:
        montees.append((bas, haut))
    minimum = reglages["denivele_min_m"]
    return [(b, h) for b, h in montees if altitudes[h] - altitudes[b] >= minimum]


def _pente_max(distances: Tableau, altitudes: Tableau, fenetre_m: float) -> float:
    if len(distances) < 2:
        return 0.0
    cibles = distances + fenetre_m
    garde = cibles <= distances[-1]
    if not garde.any():
        return float((altitudes[-1] - altitudes[0]) / max(distances[-1] - distances[0], 1) * 100)
    plus_loin = np.interp(cibles[garde], distances, altitudes)
    return float(((plus_loin - altitudes[garde]) / fenetre_m).max() * 100)


def assembler(
    arcs: list[int],
    mesure: Mesure,
    graphe: Graphe,
    reseau: Reseau,
    reglages_montees: dict[str, Any],
    structure: tuple[int, int, int, int] | None = None,
) -> Boucle:
    """Transforme une suite d'arcs en boucle complète, avec ses chiffres et ses montées.

    `structure` : pour une séance d'intervalles, (répétitions, arcs d'échauffement, arcs
    d'une montée, arcs de retour).
    """
    depart = int(graphe.arc_de[arcs[0]])
    x = np.concatenate([[graphe.x[depart]], *[graphe.points(arc)[0] for arc in arcs]])
    y = np.concatenate([[graphe.y[depart]], *[graphe.points(arc)[1] for arc in arcs]])
    z = np.concatenate([[graphe.z[depart]], *[np.asarray(graphe.profils[arc]) for arc in arcs]])
    distances = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    longitudes, latitudes = geo.l93_vers_gps(x, y)

    tableau = np.asarray(arcs)
    troncons = graphe.arc_troncon[tableau]
    longueurs = graphe.arc_longueur[tableau]
    # Tronçon auquel appartient chaque point du tracé (pour retrouver les noms de rue).
    tailles = [len(graphe.profils[arc]) for arc in arcs]
    troncon_du_point = np.concatenate([[troncons[0]], np.repeat(troncons, tailles)])

    montees = []
    for numero, (bas, haut) in enumerate(reperer_montees(distances, z, reglages_montees), 1):
        d, a = distances[bas : haut + 1], z[bas : haut + 1]
        longueur = float(d[-1] - d[0])
        noms: dict[str, float] = {}
        pas = np.diff(d)
        for troncon, metres in zip(troncon_du_point[bas + 1 : haut + 1], pas, strict=True):
            nom = reseau.noms[reseau.nom[troncon]]
            noms[nom] = noms.get(nom, 0.0) + float(metres)
        nommes = {nom: metres for nom, metres in noms.items() if nom}
        if nommes and max(nommes.values()) >= 0.3 * longueur:
            nom = max(nommes, key=lambda cle: nommes[cle])
        else:
            sur_chemin = reseau.chemin[troncon_du_point[bas + 1 : haut + 1]].mean() > 0.5
            nom = "sentier sans nom" if sur_chemin else "rue sans nom"
        montees.append(
            Montee(
                numero=numero,
                nom=nom,
                debut_m=float(d[0]),
                longueur_m=longueur,
                denivele_m=float(a[-1] - a[0]),
                pente_moyenne_pct=float((a[-1] - a[0]) / max(longueur, 1) * 100),
                pente_max_pct=_pente_max(d, a, reglages_montees["fenetre_pente_m"]),
                bas=(float(longitudes[bas]), float(latitudes[bas]), float(z[bas])),
                haut=(float(longitudes[haut]), float(latitudes[haut]), float(z[haut])),
            )
        )

    escaliers = float(longueurs[reseau.escalier[troncons]].sum())
    alertes = []
    intervalles = None
    if structure is not None:
        repetitions, n_echauffement, n_montee, n_retour = structure
        # Distance cumulée à la fin de chaque morceau (un arc = len(profils[arc]) points).
        fins = np.cumsum([0, *(len(graphe.profils[arc]) for arc in arcs)])
        fin_echauffement = float(distances[fins[n_echauffement]])
        fin_montee = float(distances[fins[n_echauffement + n_montee]])
        intervalles = Intervalles(
            repetitions=repetitions,
            echauffement_m=fin_echauffement,
            montee_m=fin_montee - fin_echauffement,
            denivele_m=float(z[fins[n_echauffement + n_montee]] - z[fins[n_echauffement]]),
            retour_m=float(distances[-1] - distances[fins[len(arcs) - n_retour]]),
        )
        alertes.append(
            f"{repetitions} montées de {intervalles.montee_m:.0f} m "
            f"(+{intervalles.denivele_m:.0f} m), redescente par le même chemin"
        )
    else:
        if mesure.double_m > 0:
            alertes.append(
                f"{mesure.double_m:.0f} m passent tout près d'une autre partie du parcours"
            )
        if mesure.double_exact_m > 0:
            alertes.append(f"{mesure.double_exact_m:.0f} m sont empruntés deux fois")
        if mesure.demi_tours:
            alertes.append(f"{mesure.demi_tours} demi-tour(s)")
    if escaliers > 0:
        alertes.append(f"{escaliers:.0f} m d'escaliers")
    alertes.append(
        "horaires d'ouverture des parcs non vérifiés (parc de Saint-Cloud fermé la nuit)"
    )
    return Boucle(
        longitudes=longitudes,
        latitudes=latitudes,
        altitudes=z,
        distances=distances,
        x=x,
        y=y,
        distance_m=mesure.longueur_m,
        dplus_m=mesure.dplus_m,
        dmoins_m=mesure.dmoins_m,
        altitude_min_m=float(z.min()),
        altitude_max_m=float(z.max()),
        part_chemin=float(longueurs[reseau.chemin[troncons]].sum() / longueurs.sum()),
        escaliers_m=escaliers,
        double_m=mesure.double_m,
        montees=montees,
        alertes=alertes,
        troncons=np.unique(troncons),
        intervalles=intervalles,
    )
