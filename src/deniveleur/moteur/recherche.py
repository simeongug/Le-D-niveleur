"""Recherche de boucles à D+ maximal.

Principe : on construit beaucoup de boucles candidates en zigzaguant sur les
versants (monter, redescendre un peu plus loin, remonter…) tout en tournant
autour d'un centre pour revenir vers le départ, puis on garde les meilleures.
Voir docs/algorithme.md.
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from deniveleur.moteur.boucle import Evaluateur, Mesure, sans_allers_retours
from deniveleur.moteur.chemins import Chemins
from deniveleur.moteur.graphe import Graphe

journal = logging.getLogger(__name__)

_BASE = 1 << 20  # même codage des cases que dans boucle.py


@dataclass(frozen=True)
class Guide:
    """Réglages tirés au hasard pour une construction.

    Le parcours tourne autour d'un centre placé à `rayon` mètres du départ dans
    la direction `angle` ; `cout` dit combien de D+ doit rapporter chaque mètre
    parcouru, `rappel` avec quelle force on est ramené vers le cercle.
    """

    angle: float
    rayon: float
    sens: int
    cout: float
    rappel: float
    # Poids donné au dénivelé dans le choix des étapes : 1 pour le D+ maximal ; plus bas,
    # voire négatif, quand on vise un D+ modéré.
    poids_vertical: float = 1.0


@dataclass
class Candidat:
    arcs: list[int]
    mesure: Mesure
    note: float
    valide: bool
    guide: Guide | None = None


@dataclass
class Bilan:
    constructions: int = 0
    abouties: int = 0
    valides: int = 0
    duree_s: float = 0.0


class Occupation:
    """Ce que le parcours en cours occupe déjà : tronçons pris et cases traversées.

    Les derniers mètres du parcours ne comptent pas dans les cases : la suite
    part forcément de là.
    """

    def __init__(self, recherche: "Recherche"):
        self.recherche = recherche
        self.pris: set[int] = set()
        self.cases: set[int] = set()
        self.inclus = 0  # nombre d'arcs du parcours déjà versés dans `cases`
        self.taille = 0

    def mettre_a_jour(self, parcours: list[int]) -> None:
        recherche = self.recherche
        coupe, cumul = len(parcours), 0.0
        while coupe > 0 and cumul < recherche.r["double_ecart_min_m"]:
            coupe -= 1
            cumul += recherche.longueurs[parcours[coupe]]
        if coupe < self.inclus or len(parcours) < self.taille:
            self.cases, self.inclus = set(), 0
            self.pris = {arc >> 1 for arc in parcours}
        else:
            self.pris.update(arc >> 1 for arc in parcours[self.taille :])
        for arc in parcours[self.inclus : coupe]:
            self.cases |= recherche.alentours(arc)
        self.inclus, self.taille = coupe, len(parcours)


class Recherche:
    def __init__(
        self,
        graphe: Graphe,
        chemins: Chemins,
        evaluateur: Evaluateur,
        distance_m: float,
        tolerance: float,
        reglages: dict[str, Any],
        graine: int = 0,
        chemin_min: float = 0.0,
        dplus_cible: float | None = None,
    ):
        self.g = graphe
        self.c = chemins
        self.ev = evaluateur
        self.r = reglages
        self.distance = distance_m
        self.chemin_min = chemin_min
        self.dplus_cible = dplus_cible
        # Si une part minimale de chemin est demandée, chaque mètre de chemin rapporte un peu.
        self.prime_chemin = reglages["prime_chemin_par_m"] if chemin_min > 0 else 0.0
        self.l_min = distance_m * (1 - tolerance)
        self.l_max = distance_m * (1 + tolerance)
        # On vise le haut de la fourchette : plus de distance, c'est plus de D+.
        self.cible = distance_m * (1 + tolerance * reglages["visee_dans_tolerance"])
        self.rayons = tuple(part * distance_m for part in reglages["guide_rayon_part"])
        self.bande = reglages["guide_bande_part"] * distance_m
        self.rappel_des = reglages["rappel_depart_des_part"] * distance_m
        self.hasard = np.random.default_rng(graine)
        self.longueurs: list[float] = graphe.arc_longueur.tolist()
        case = reglages["double_case_m"]
        self._cles = (graphe.points_x // case).astype(np.int64) * _BASE + (
            graphe.points_y // case
        ).astype(np.int64)
        self._cases: dict[int, frozenset[int]] = {}
        self._alentours: dict[int, frozenset[int]] = {}
        self._preparer_retour()

    # ------------------------------------------------------------------ notes

    def noter(self, mesure: Mesure) -> float:
        """Note d'une boucle : son D+ (ou sa proximité au D+ visé), moins les défauts."""
        r = self.r
        if self.dplus_cible is None:
            note = mesure.dplus_m + self.prime_chemin * mesure.chemin_m
        else:
            # D+ cible : on veut l'écart le plus petit ; à écart égal, plus de sentier.
            part_chemin = mesure.chemin_m / max(mesure.longueur_m, 1.0)
            note = -abs(mesure.dplus_m - self.dplus_cible) + r["cible_bonus_chemin_m"] * part_chemin
        note -= r["penalite_double_par_m"] * mesure.double_m
        note -= r["penalite_double_exact_par_m"] * mesure.double_exact_m
        note -= r["penalite_demi_tour_m"] * mesure.demi_tours
        if mesure.longueur_m > self.l_max:
            note -= r["penalite_trop_long_par_m"] * (mesure.longueur_m - self.l_max)
        if mesure.longueur_m < self.l_min:
            note -= r["penalite_trop_court_par_m"] * (self.l_min - mesure.longueur_m)
        return note

    def valide_hors_chemin(self, mesure: Mesure) -> bool:
        """Bonne longueur, aucun tronçon pris deux fois, aucun demi-tour."""
        return (
            self.l_min <= mesure.longueur_m <= self.l_max
            and mesure.double_exact_m == 0
            and mesure.demi_tours == 0
            and mesure.double_m <= self.r["double_tolere_part"] * self.distance
        )

    def valide(self, mesure: Mesure) -> bool:
        return (
            self.valide_hors_chemin(mesure)
            and mesure.chemin_m >= self.chemin_min * mesure.longueur_m
        )

    def candidat(self, arcs: list[int]) -> Candidat:
        mesure = self.ev.mesurer(arcs)
        return Candidat(arcs, mesure, self.noter(mesure), self.valide(mesure))

    # ------------------------------------------------------------- occupation

    def cases_de(self, arc: int) -> frozenset[int]:
        troncon = arc >> 1
        cases = self._cases.get(troncon)
        if cases is None:
            debut = self.g.debut_points
            cases = frozenset(self._cles[debut[2 * troncon] : debut[2 * troncon + 1]].tolist())
            self._cases[troncon] = cases
        return cases

    def alentours(self, arc: int) -> frozenset[int]:
        """Cases traversées par l'arc, plus les cases qui les touchent."""
        troncon = arc >> 1
        alentours = self._alentours.get(troncon)
        if alentours is None:
            alentours = frozenset(
                case + dx * _BASE + dy
                for case in self.cases_de(arc)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
            )
            self._alentours[troncon] = alentours
        return alentours

    def _greffe(
        self, parcours: list[int], liaison: list[int], occupation: Occupation
    ) -> tuple[int, list[int]] | None:
        """Vérifie qu'on peut ajouter `liaison` au bout de `parcours`.

        Renvoie (nombre d'arcs du parcours à retirer, arcs à ajouter), ou None.
        Si la liaison commence par rebrousser chemin, on raccourcit le parcours
        d'autant au lieu de faire un aller-retour.
        """
        recul = 0
        while (
            recul < len(liaison)
            and recul < len(parcours)
            and parcours[-1 - recul] == liaison[recul] ^ 1
        ):
            recul += 1
        reste = liaison[recul:]
        if not reste or recul > len(liaison) * self.r["recul_max_part"]:
            return None
        if len(parcours) > recul:
            dernier = parcours[-1 - recul]
            cosinus = float((self.g.cap_fin[dernier] * self.g.cap_debut[reste[0]]).sum())
            if cosinus < self.c.cos_demi_tour:
                return None
        pris, occupees = occupation.pris, occupation.cases
        recouvrement = 0
        for arc in reste:
            if (arc >> 1) in pris:
                return None
            recouvrement += len(self.cases_de(arc) & occupees)
        if recouvrement > self.r["recouvrement_max_cases"]:
            return None
        return recul, reste

    # ----------------------------------------------------------- construction

    def tirer_guide(self) -> Guide:
        r, h = self.r, self.hasard
        return Guide(
            angle=float(h.uniform(0, 2 * math.pi)),
            rayon=float(h.uniform(*self.rayons)),
            sens=1 if h.random() < 0.5 else -1,
            cout=float(h.uniform(*r["cout_par_m"])),
            rappel=float(h.uniform(*r["rappel_guide"])),
            poids_vertical=(
                1.0 if self.dplus_cible is None else float(h.uniform(*r["poids_vertical_cible"]))
            ),
        )

    def varier(self, guide: Guide) -> Guide:
        """Un guide voisin d'un guide qui a bien marché."""
        r, h = self.r, self.hasard
        ampleur = r["variation_guide"]
        return Guide(
            angle=guide.angle + float(h.normal(0, ampleur)),
            rayon=float(np.clip(guide.rayon * h.uniform(1 - ampleur, 1 + ampleur), *self.rayons)),
            sens=guide.sens,
            cout=float(np.clip(guide.cout * h.uniform(1 - ampleur, 1 + ampleur), *r["cout_par_m"])),
            rappel=float(
                np.clip(guide.rappel * h.uniform(1 - ampleur, 1 + ampleur), *r["rappel_guide"])
            ),
            poids_vertical=(
                1.0
                if self.dplus_cible is None
                else float(
                    np.clip(
                        guide.poids_vertical + h.normal(0, ampleur),
                        *r["poids_vertical_cible"],
                    )
                )
            ),
        )

    def construire(self, guide: Guide) -> list[int] | None:
        """Construit une boucle en zigzag. Renvoie ses arcs, ou None en cas d'échec."""
        r, c, h = self.r, self.c, self.hasard
        angle, rayon, sens, cout, rappel = (
            guide.angle,
            guide.rayon,
            guide.sens,
            guide.cout,
            guide.rappel,
        )
        centre_x = c.x[0] + rayon * math.cos(angle)
        centre_y = c.y[0] + rayon * math.sin(angle)
        angle_depart = angle + math.pi
        parcours: list[int] = []
        vues: set[int] = set()
        ici, longueur = 0, 0.0
        occupation = Occupation(self)
        # Mémoire des étapes, pour revenir en arrière quand on se retrouve coincé.
        etapes: list[tuple[list[int], int, float]] = []
        retours_arriere = 0
        while True:
            reste = self.cible - longueur
            if parcours and reste < c.retour[ici] * r["marge_retour"] + r["marge_retour_m"]:
                break
            occupation.mettre_a_jour(parcours)
            liaisons = c.liaisons(ici)
            voisines = liaisons.voisines
            possible = (
                np.isfinite(liaisons.longueur)
                & (liaisons.longueur > r["liaison_min_m"])
                & (voisines != 0)
                & (c.retour[voisines] * r["marge_retour"] <= reste - liaisons.longueur)
            )
            choix = None
            if possible.any():
                rangs = np.flatnonzero(possible)
                longueurs = liaisons.longueur[rangs]
                vertical = (liaisons.montee[rangs] + liaisons.descente[rangs]) / 2
                avancement = (longueur + longueurs) / self.cible
                cap = angle_depart + sens * 2 * math.pi * avancement
                ecart = np.hypot(
                    c.x[voisines[rangs]] - (centre_x + rayon * np.cos(cap)),
                    c.y[voisines[rangs]] - (centre_y + rayon * np.sin(cap)),
                )
                # Plus la distance restante se resserre, plus on favorise ce qui rapproche
                # du départ.
                mou = reste - c.retour[ici] * r["marge_retour"]
                envie_de_rentrer = r["rappel_depart"] * max(0.0, 1 - mou / self.rappel_des)
                notes = (
                    guide.poids_vertical * vertical
                    - cout * longueurs
                    + self.prime_chemin * liaisons.chemin[rangs]
                    - rappel * np.maximum(0.0, ecart - self.bande)
                    + envie_de_rentrer * (c.retour[ici] - c.retour[voisines[rangs]])
                    + h.normal(0, r["bruit_m"], len(rangs))
                )
                for position in np.argsort(-notes):
                    rang = int(rangs[position])
                    voisine = int(voisines[rang])
                    if voisine in vues:
                        continue
                    arcs = liaisons.arcs[rang]
                    greffe = self._greffe(parcours, arcs, occupation) if arcs else None
                    if greffe:
                        choix = (voisine, *greffe)
                        break
            if choix is None:
                # Coincé : on annule la dernière étape et on essaie autre chose.
                if not etapes or retours_arriere >= r["retours_arriere_max"]:
                    break
                retours_arriere += 1
                parcours, ici, longueur = etapes.pop()
                continue
            voisine, recul, ajout = choix
            etapes.append((list(parcours), ici, longueur))
            if recul:
                longueur -= sum(self.longueurs[a] for a in parcours[-recul:])
                del parcours[-recul:]
            parcours += ajout
            longueur += sum(self.longueurs[a] for a in ajout)
            ici = voisine
            vues.add(voisine)
        # Fermeture : on rentre au départ ; si ça ne passe pas, on recule d'une étape.
        etapes.append((parcours, ici, longueur))
        for parcours, ici, longueur in reversed(etapes[-r["fermetures_max"] :]):
            if not parcours or longueur + c.retour[ici] > self.l_max:
                continue
            retour = self._retour(parcours, int(c.ancres[ici]), self.l_max - longueur)
            if retour is None:
                continue
            boucle = sans_allers_retours(parcours + retour)
            if longueur + sum(self.longueurs[a] for a in retour) < self.l_min:
                break  # reculer davantage ne ferait que raccourcir
            return boucle
        return None

    # ----------------------------------------------------------------- retour

    def _preparer_retour(self) -> None:
        """Index utiles pour fermer la boucle : où est chaque tronçon dans la matrice,
        et quels tronçons passent par chaque case."""
        g = self.g
        matrice = g.matrice
        matrice.sort_indices()
        nombre = matrice.shape[0]
        lignes = np.repeat(np.arange(nombre, dtype=np.int64), np.diff(matrice.indptr))
        self._positions = lignes * nombre + matrice.indices
        debut = g.debut_points
        tailles = (debut[1::2] - debut[0:-1:2]).astype(np.int64)  # points par tronçon
        troncon_du_point = np.repeat(np.arange(len(tailles), dtype=np.int64), tailles)
        masque = np.zeros(len(self._cles), bool)
        for d, f in ((debut[0:-1:2], debut[1::2]),):
            # Les points des arcs pairs (sens du tronçon) suffisent.
            bornes = np.zeros(len(self._cles) + 1, np.int32)
            np.add.at(bornes, d, 1)
            np.add.at(bornes, f, -1)
            masque = np.cumsum(bornes[:-1]) > 0
        paires = np.unique(self._cles[masque] * (1 << 22) + troncon_du_point)
        self._case_des_paires = paires >> 22
        self._troncon_des_paires = (paires & ((1 << 22) - 1)).astype(np.int64)
        self._cases_par_troncon = np.bincount(self._troncon_des_paires, minlength=len(tailles))

    def _troncons_proches(self, cases: set[int]) -> NDArray[np.int64]:
        """Tronçons dont une bonne part passe dans les cases données."""
        if not cases:
            return np.empty(0, np.int64)
        demandees = np.fromiter(cases, np.int64, len(cases))
        gauche = np.searchsorted(self._case_des_paires, demandees, "left")
        droite = np.searchsorted(self._case_des_paires, demandees, "right")
        nombre = droite - gauche
        garde = nombre > 0
        gauche, nombre = gauche[garde], nombre[garde]
        positions = np.repeat(gauche - np.cumsum(nombre) + nombre, nombre) + np.arange(nombre.sum())
        touches = np.bincount(
            self._troncon_des_paires[positions], minlength=len(self._cases_par_troncon)
        )
        part = touches / np.maximum(self._cases_par_troncon, 1)
        return np.flatnonzero(part >= self.r["retour_part_proche"])

    def _retour(self, parcours: list[int], noeud: int, longueur_max: float) -> list[int] | None:
        """Chemin vers le départ qui évite ce que le parcours occupe déjà.

        Les tronçons déjà pris, et ceux qui les longent, sont comptés beaucoup
        plus longs qu'ils ne sont : le plus court chemin les contourne. Renvoie
        None s'il n'y a pas de retour propre dans la longueur permise.
        """
        g, r = self.g, self.r
        matrice = g.matrice
        nombre = matrice.shape[0]
        occupation = Occupation(self)
        occupation.mettre_a_jour(parcours)
        poids = matrice.data.copy()

        def alourdir(troncons: NDArray[np.int64], facteur: float) -> None:
            de = g.arc_de[2 * troncons].astype(np.int64)
            vers = g.arc_vers[2 * troncons].astype(np.int64)
            cles = np.concatenate([de * nombre + vers, vers * nombre + de])
            poids[np.searchsorted(self._positions, cles)] *= facteur

        alourdir(self._troncons_proches(occupation.cases), r["retour_penalite_proche"])
        alourdir(
            np.fromiter(occupation.pris, np.int64, len(occupation.pris)), r["retour_penalite_pris"]
        )
        penalisee = csr_matrix((poids, matrice.indices, matrice.indptr), shape=matrice.shape)
        distances, precedent = dijkstra(
            penalisee, directed=False, indices=noeud, return_predecessors=True, limit=longueur_max
        )
        if not np.isfinite(distances[g.depart]):
            return None
        arcs: list[int] = []
        courant = g.depart
        while courant != noeud:
            avant = int(precedent[courant])
            arcs.append(g.arc_entre[(avant, courant)])
            courant = avant
        arcs.reverse()
        if not self.c.sans_demi_tour(arcs):
            return None
        cosinus = float((g.cap_fin[parcours[-1]] * g.cap_debut[arcs[0]]).sum())
        if cosinus < self.c.cos_demi_tour or arcs[0] == parcours[-1] ^ 1:
            return None
        return arcs

    # ---------------------------------------------------------------- pilotage

    def chercher(self, budget_s: float) -> tuple[list[Candidat], Bilan]:
        """Construit des candidats pendant `budget_s` secondes ; les meilleurs d'abord.

        D'abord des guides tirés au hasard (exploration), puis des variantes des
        guides qui ont donné les meilleures boucles (approfondissement).
        """
        r = self.r
        bilan = Bilan()
        debut = time.perf_counter()
        candidats: list[Candidat] = []
        meilleurs: list[Candidat] = []
        while (ecoule := time.perf_counter() - debut) < budget_s:
            if ecoule < budget_s * r["part_exploration"] or not meilleurs:
                guide = self.tirer_guide()
            else:
                guide = self.varier(meilleurs[int(self.hasard.integers(len(meilleurs)))].guide)
            arcs = self.construire(guide)
            bilan.constructions += 1
            if not arcs:
                continue
            bilan.abouties += 1
            candidat = self.candidat(arcs)
            candidat.guide = guide
            candidats.append(candidat)
            if candidat.valide:
                meilleurs.append(candidat)
                meilleurs.sort(key=lambda c: -c.note)
                del meilleurs[r["guides_gardes"] :]
        candidats.sort(key=lambda candidat: (-candidat.valide, -candidat.note))
        bilan.valides = sum(candidat.valide for candidat in candidats)
        bilan.duree_s = time.perf_counter() - debut
        return candidats, bilan
