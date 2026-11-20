"""File d'attente des calculs : un seul calcul à la fois, les autres attendent leur tour.

Un calcul dure environ 30 secondes et occupe le processeur : en lancer plusieurs en
même temps les ralentirait tous. Les résultats sont gardés en mémoire un moment, le
temps de télécharger les GPX.
"""

import logging
import queue
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from deniveleur import gpx, moteur
from deniveleur.moteur import temps
from deniveleur.moteur.itineraire import Boucle
from deniveleur.reseau import Reseau

journal = logging.getLogger(__name__)


@dataclass
class Demande:
    latitude: float
    longitude: float
    distance_km: float
    tolerance_pct: float
    dplus_cible: float | None
    chemin_min_pct: float
    sans_escaliers: bool
    pente_max_pct: float | None
    sans_bitume: bool
    doublons: bool
    repetitions: int | None
    propositions: int
    allure_s_par_km: float


@dataclass
class Calcul:
    identifiant: str
    demande: Demande
    cree_le: float = field(default_factory=time.time)
    etat: str = "en_attente"  # en_attente, en_cours, termine, erreur
    debut: float | None = None
    fin: float | None = None
    boucles: list[Boucle] = field(default_factory=list)
    resultat: dict[str, Any] | None = None
    erreur: str | None = None


class FileDeCalculs:
    def __init__(self, reseau: Reseau, parametres: dict[str, Any]):
        self.reseau = reseau
        self.parametres = parametres
        self.reglages = parametres["site"]
        self._file: queue.Queue[str] = queue.Queue()
        self._calculs: OrderedDict[str, Calcul] = OrderedDict()
        self._verrou = threading.Lock()
        self._ouvrier = threading.Thread(target=self._travailler, daemon=True, name="calculs")
        self._ouvrier.start()

    # ------------------------------------------------------------------ accès

    def soumettre(self, demande: Demande) -> Calcul:
        with self._verrou:
            en_attente = sum(1 for c in self._calculs.values() if c.etat == "en_attente")
            if en_attente >= self.reglages["file_max"]:
                raise OverflowError("Trop de demandes en attente, réessaie dans une minute.")
            calcul = Calcul(uuid.uuid4().hex[:12], demande)
            self._calculs[calcul.identifiant] = calcul
            while len(self._calculs) > self.reglages["calculs_gardes"]:
                self._calculs.popitem(last=False)
        self._file.put(calcul.identifiant)
        return calcul

    def obtenir(self, identifiant: str) -> Calcul | None:
        return self._calculs.get(identifiant)

    def position(self, calcul: Calcul) -> int:
        """Nombre de calculs à passer avant celui-ci (0 = c'est son tour)."""
        if calcul.etat != "en_attente":
            return 0
        avant = 0
        for autre in self._calculs.values():
            if autre is calcul:
                break
            avant += autre.etat in ("en_attente", "en_cours")
        return avant

    def avancement(self, calcul: Calcul) -> float:
        """Estimation entre 0 et 1, d'après le temps écoulé."""
        if calcul.etat in ("termine", "erreur"):
            return 1.0
        if calcul.etat == "en_attente" or calcul.debut is None:
            return 0.0
        prevu = self.reglages["budget_s"] + self.reglages["preparation_prevue_s"]
        return min(0.97, (time.time() - calcul.debut) / prevu)

    # ---------------------------------------------------------------- travail

    def _travailler(self) -> None:
        while True:
            identifiant = self._file.get()
            calcul = self._calculs.get(identifiant)
            if calcul is None:
                continue
            calcul.etat, calcul.debut = "en_cours", time.time()
            try:
                self._executer(calcul)
                calcul.etat = "termine"
            except Exception as exc:  # une erreur ne doit pas arrêter le serveur
                journal.exception("Calcul %s en échec", identifiant)
                calcul.etat = "erreur"
                calcul.erreur = str(exc) or exc.__class__.__name__
            calcul.fin = time.time()

    def _executer(self, calcul: Calcul) -> None:
        d = calcul.demande
        boucles, rapport = moteur.generer(
            self.reseau,
            self.parametres,
            d.latitude,
            d.longitude,
            d.distance_km * 1000,
            tolerance=d.tolerance_pct / 100,
            budget_s=self.reglages["budget_s"],
            propositions=d.propositions,
            chemin_min=d.chemin_min_pct / 100,
            escaliers=False if d.sans_escaliers else None,
            pente_max_pct=d.pente_max_pct,
            sans_bitume=d.sans_bitume,
            doublons=d.doublons,
            repetitions=d.repetitions,
            dplus_cible=d.dplus_cible,
        )
        calcul.boucles = boucles
        calcul.resultat = {
            "duree_s": round(rapport.duree_s, 1),
            "boucles_construites": rapport.constructions,
            "boucles_valides": rapport.valides,
            "ecart_depart_m": round(rapport.ecart_depart_m),
            "propositions": [
                decrire(boucle, rang, self.parametres, d.allure_s_par_km)
                for rang, boucle in enumerate(boucles, 1)
            ],
        }

    def gpx(self, calcul: Calcul, rang: int) -> tuple[str, str]:
        """(nom de fichier, contenu GPX) de la proposition n° `rang`."""
        boucle = calcul.boucles[rang - 1]
        nom = f"deniveleur-{boucle.distance_m / 1000:.1f}km-{boucle.dplus_m:.0f}m"
        titre = f"Le Déniveleur — {boucle.distance_m / 1000:.1f} km, D+ {boucle.dplus_m:.0f} m"
        return f"{nom}.gpx", gpx.en_gpx(boucle, titre)


def decrire(
    boucle: Boucle, rang: int, parametres: dict[str, Any], allure_s_par_km: float
) -> dict[str, Any]:
    """Tout ce que l'interface affiche pour une proposition (format JSON)."""
    pas = parametres["site"]["pas_trace_m"]
    distances = boucle.distances
    # Points tous les `pas` mètres environ pour alléger l'envoi (et toujours le dernier).
    garde = [0]
    for i in range(1, len(distances)):
        if distances[i] - distances[garde[-1]] >= pas:
            garde.append(i)
    if garde[-1] != len(distances) - 1:
        garde.append(len(distances) - 1)
    secondes = temps.estimer_s(
        boucle.distance_m, boucle.dplus_m, parametres["temps"], allure_s_par_km
    )
    return {
        "rang": rang,
        "distance_m": round(boucle.distance_m),
        "dplus_m": round(boucle.dplus_m),
        "dmoins_m": round(boucle.dmoins_m),
        "altitude_min_m": round(boucle.altitude_min_m),
        "altitude_max_m": round(boucle.altitude_max_m),
        "part_chemin_pct": round(boucle.part_chemin * 100),
        "escaliers_m": round(boucle.escaliers_m),
        "temps_s": round(secondes),
        "temps_texte": temps.formater(secondes),
        "alertes": boucle.alertes,
        "montees": [
            {
                "numero": m.numero,
                "nom": m.nom,
                "debut_m": round(m.debut_m),
                "longueur_m": round(m.longueur_m),
                "denivele_m": round(m.denivele_m),
                "pente_moyenne_pct": round(m.pente_moyenne_pct, 1),
                "pente_max_pct": round(m.pente_max_pct, 1),
                "bas": [round(m.bas[0], 6), round(m.bas[1], 6)],
                "haut": [round(m.haut[0], 6), round(m.haut[1], 6)],
            }
            for m in boucle.montees
        ],
        "points": [
            [
                round(float(boucle.longitudes[i]), 6),
                round(float(boucle.latitudes[i]), 6),
                round(float(boucle.altitudes[i]), 1),
                round(float(distances[i])),
            ]
            for i in garde
        ],
    }
