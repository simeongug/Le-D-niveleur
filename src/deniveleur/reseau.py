"""Réseau de chemins : carrefours, tronçons, et altitude de chaque tronçon.

Un tronçon relie deux carrefours. Pour chacun on connaît sa longueur, son D+
dans les deux sens, sa pente maximale et son revêtement. C'est sur ce réseau
que le moteur (étape 3) cherchera des boucles.
"""

import heapq
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from deniveleur import profil
from deniveleur.donnees.altitude import ModeleAltitude
from deniveleur.donnees.osm import Voie

journal = logging.getLogger(__name__)

Tableau = NDArray[np.float64]


@dataclass
class Reseau:
    """Le réseau prêt à l'emploi. Les tronçons sont décrits par des colonnes alignées."""

    # Carrefours
    noeud_x: Tableau
    noeud_y: Tableau
    noeud_z: Tableau
    # Tronçons : carrefour de départ et d'arrivée (positions dans les colonnes ci-dessus)
    depart: NDArray[np.int32]
    arrivee: NDArray[np.int32]
    longueur: Tableau
    # D+ en allant de `depart` vers `arrivee`. Dans l'autre sens, le D+ vaut `gain_retour`.
    gain_aller: Tableau
    gain_retour: Tableau
    pente_max: Tableau  # en %
    chemin: NDArray[np.bool_]  # vrai = sentier ou piste, faux = revêtement dur
    escalier: NDArray[np.bool_]
    ouvrage: NDArray[np.bool_]  # pont ou tunnel
    type_voie: NDArray[np.int16]  # position dans `types_voie`
    nom: NDArray[np.int32]  # position dans `noms` (0 = sans nom)
    voie_osm: NDArray[np.int64]
    # Tracé détaillé : les points du tronçon i sont trace_*[debut_trace[i]:debut_trace[i+1]]
    debut_trace: NDArray[np.int64]
    trace_x: Tableau
    trace_y: Tableau
    trace_z: Tableau
    types_voie: list[str]
    noms: list[str]
    infos: dict[str, Any]

    @property
    def nombre_troncons(self) -> int:
        return len(self.depart)

    def trace(self, troncon: int) -> tuple[Tableau, Tableau, Tableau]:
        debut, fin = self.debut_trace[troncon], self.debut_trace[troncon + 1]
        return self.trace_x[debut:fin], self.trace_y[debut:fin], self.trace_z[debut:fin]

    def pente_moyenne(self) -> Tableau:
        """Pente moyenne de chaque tronçon, en % (toujours positive)."""
        denivele = np.abs(self.noeud_z[self.arrivee] - self.noeud_z[self.depart])
        return denivele / np.maximum(self.longueur, 1.0) * 100

    def resume(self) -> dict[str, Any]:
        km = self.longueur.sum() / 1000
        return {
            "carrefours": len(self.noeud_x),
            "troncons": self.nombre_troncons,
            "km_total": round(float(km), 1),
            "part_chemin_pct": round(float(self.longueur[self.chemin].sum() / 10 / km), 1),
            "km_escaliers": round(float(self.longueur[self.escalier].sum() / 1000), 1),
            "altitude_min_m": round(float(self.trace_z.min()), 1),
            "altitude_max_m": round(float(self.trace_z.max()), 1),
        }

    def enregistrer(self, dossier: Path) -> None:
        dossier.mkdir(parents=True, exist_ok=True)
        colonnes = {
            cle: valeur for cle, valeur in vars(self).items() if isinstance(valeur, np.ndarray)
        }
        np.savez_compressed(dossier / "reseau.npz", **colonnes)
        annexe = {"types_voie": self.types_voie, "noms": self.noms, "infos": self.infos}
        (dossier / "reseau.json").write_text(
            json.dumps(annexe, ensure_ascii=False, indent=1) + "\n", "utf-8"
        )

    @classmethod
    def charger(cls, dossier: Path) -> "Reseau":
        if not (dossier / "reseau.npz").exists():
            raise FileNotFoundError(
                f"Pas de réseau dans {dossier}. Lancer d'abord « deniveleur donnees reseau »."
            )
        annexe = json.loads((dossier / "reseau.json").read_text("utf-8"))
        with np.load(dossier / "reseau.npz") as colonnes:
            return cls(**{cle: colonnes[cle] for cle in colonnes.files}, **annexe)


def est_chemin(etiquettes: dict[str, str], parametres_osm: dict[str, Any]) -> bool:
    """Vrai pour un sentier ou une piste ; faux pour du bitume, des pavés, un escalier."""
    if etiquettes.get("highway") == "steps":
        return False
    surface = etiquettes.get("surface")
    if surface:
        return surface not in parametres_osm["surfaces_dures"]
    return etiquettes.get("highway") in parametres_osm["voies_chemin"]


def est_ouvrage(etiquettes: dict[str, str]) -> bool:
    return etiquettes.get("bridge", "no") != "no" or etiquettes.get("tunnel", "no") != "no"


def decouper(voies: list[Voie]) -> list[tuple[Voie, int, int]]:
    """Coupe chaque voie aux carrefours : [(voie, position de début, position de fin)]."""
    usages: Counter[int] = Counter()
    for voie in voies:
        usages.update(voie.noeuds)
        usages[voie.noeuds[0]] += 1
        usages[voie.noeuds[-1]] += 1
    morceaux = []
    for voie in voies:
        debut = 0
        for position in range(1, len(voie.noeuds)):
            if usages[voie.noeuds[position]] > 1 or position == len(voie.noeuds) - 1:
                morceaux.append((voie, debut, position))
                debut = position
    return morceaux


def construire(
    voies: list[Voie],
    altitude: ModeleAltitude,
    parametres: dict[str, Any],
    infos: dict[str, Any] | None = None,
) -> Reseau:
    """Assemble le réseau et calcule l'altitude de chaque tronçon."""
    reglages = parametres["profil"]
    pas, lissage = reglages["pas_m"], reglages["lissage_m"]
    morceaux = decouper(voies)

    indices: dict[int, int] = {}
    noeud_x: list[float] = []
    noeud_y: list[float] = []

    def indice(voie: Voie, position: int) -> int:
        identifiant = voie.noeuds[position]
        if identifiant not in indices:
            indices[identifiant] = len(noeud_x)
            noeud_x.append(voie.x[position])
            noeud_y.append(voie.y[position])
        return indices[identifiant]

    depart, arrivee, traces = [], [], []
    for voie, debut, fin in morceaux:
        depart.append(indice(voie, debut))
        arrivee.append(indice(voie, fin))
        x = np.array(voie.x[debut : fin + 1])
        y = np.array(voie.y[debut : fin + 1])
        traces.append(profil.densifier(x, y, pas))

    ouvrage = np.array([est_ouvrage(voie.etiquettes) for voie, _, _ in morceaux])
    longueur = np.array([float(distances[-1]) for _, _, distances in traces])
    a_depart, a_arrivee = np.array(depart, np.int32), np.array(arrivee, np.int32)
    noeud_z = altitude.altitude(np.array(noeud_x), np.array(noeud_y))
    noeud_z = corriger_ouvrages(noeud_z, a_depart, a_arrivee, longueur, ouvrage)

    debut_trace = np.concatenate([[0], np.cumsum([len(x) for x, _, _ in traces])])
    trace_x = np.concatenate([x for x, _, _ in traces])
    trace_y = np.concatenate([y for _, y, _ in traces])
    trace_z = altitude.altitude(trace_x, trace_y)

    nombre = len(morceaux)
    gain_aller, gain_retour, pente = np.zeros(nombre), np.zeros(nombre), np.zeros(nombre)
    for i, (_, _, distances) in enumerate(traces):
        z = trace_z[debut_trace[i] : debut_trace[i + 1]]
        z_debut, z_fin = noeud_z[a_depart[i]], noeud_z[a_arrivee[i]]
        if ouvrage[i]:
            # Sur un pont le modèle de terrain voit l'eau, sous un tunnel la colline :
            # on relie simplement les deux extrémités par une pente régulière.
            z[:] = np.linspace(z_debut, z_fin, len(z))
        else:
            z[0], z[-1] = z_debut, z_fin
            z[:] = profil.lisser(z, pas, lissage)
        gain_aller[i], gain_retour[i] = profil.gains_bruts(z)
        pente[i] = profil.pente_max(z, distances)

    types_voie = sorted({voie.etiquettes["highway"] for voie in voies})
    noms = ["", *sorted({voie.etiquettes["name"] for voie in voies if "name" in voie.etiquettes})]
    rang_type = {valeur: rang for rang, valeur in enumerate(types_voie)}
    rang_nom = {valeur: rang for rang, valeur in enumerate(noms)}
    etiquettes = [voie.etiquettes for voie, _, _ in morceaux]
    return Reseau(
        noeud_x=np.array(noeud_x),
        noeud_y=np.array(noeud_y),
        noeud_z=noeud_z,
        depart=a_depart,
        arrivee=a_arrivee,
        longueur=longueur,
        gain_aller=gain_aller,
        gain_retour=gain_retour,
        pente_max=pente,
        chemin=np.array([est_chemin(e, parametres["osm"]) for e in etiquettes]),
        escalier=np.array([e["highway"] == "steps" for e in etiquettes]),
        ouvrage=ouvrage,
        type_voie=np.array([rang_type[e["highway"]] for e in etiquettes], np.int16),
        nom=np.array([rang_nom[e.get("name", "")] for e in etiquettes], np.int32),
        voie_osm=np.array([voie.identifiant for voie, _, _ in morceaux], np.int64),
        debut_trace=debut_trace.astype(np.int64),
        trace_x=trace_x,
        trace_y=trace_y,
        trace_z=trace_z,
        types_voie=types_voie,
        noms=noms,
        infos={**(infos or {}), "profil": dict(reglages)},
    )


def corriger_ouvrages(
    noeud_z: Tableau,
    depart: NDArray[np.int32],
    arrivee: NDArray[np.int32],
    longueur: Tableau,
    ouvrage: NDArray[np.bool_],
) -> Tableau:
    """Recalcule l'altitude des carrefours situés au milieu d'un pont ou d'un tunnel.

    Un grand pont est souvent découpé en plusieurs tronçons : les carrefours
    intermédiaires sont au-dessus du vide et le modèle de terrain y donne
    l'altitude de l'eau. On leur donne une altitude interpolée entre les deux
    points d'appui (carrefours qui touchent la terre ferme) les plus proches,
    en suivant l'ouvrage.
    """
    sur_terre = np.zeros(len(noeud_z), bool)
    sur_terre[depart[~ouvrage]] = True
    sur_terre[arrivee[~ouvrage]] = True
    voisins: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for i in np.flatnonzero(ouvrage):
        voisins[int(depart[i])].append((int(arrivee[i]), float(longueur[i])))
        voisins[int(arrivee[i])].append((int(depart[i]), float(longueur[i])))
    corrige = noeud_z.copy()
    for noeud in voisins:
        if sur_terre[noeud]:
            continue
        appuis = _appuis_proches(noeud, voisins, sur_terre)
        if len(appuis) >= 2:
            (d1, n1), (d2, n2) = appuis[:2]
            corrige[noeud] = (noeud_z[n1] * d2 + noeud_z[n2] * d1) / (d1 + d2)
        elif appuis:
            corrige[noeud] = noeud_z[appuis[0][1]]
    return corrige


def _appuis_proches(
    origine: int, voisins: dict[int, list[tuple[int, float]]], sur_terre: NDArray[np.bool_]
) -> list[tuple[float, int]]:
    """Points d'appui atteignables en suivant l'ouvrage, du plus proche au plus lointain."""
    distances = {origine: 0.0}
    file = [(0.0, origine)]
    appuis = []
    while file:
        distance, noeud = heapq.heappop(file)
        if distance > distances.get(noeud, np.inf):
            continue
        if sur_terre[noeud]:
            appuis.append((distance, noeud))
            continue  # on ne traverse pas la terre ferme
        for suivant, pas in voisins[noeud]:
            if distance + pas < distances.get(suivant, np.inf):
                distances[suivant] = distance + pas
                heapq.heappush(file, (distance + pas, suivant))
    return appuis
