"""Chemins OpenStreetMap : téléchargement de l'extrait régional et tri des voies."""

import gzip
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from deniveleur import geo
from deniveleur.donnees import telechargement as tele

journal = logging.getLogger(__name__)

ETIQUETTES_GARDEES = (
    "highway",
    "name",
    "surface",
    "access",
    "foot",
    "bridge",
    "tunnel",
    "sac_scale",
    "trail_visibility",
    "opening_hours",
)
PIETON_AUTORISE = ("yes", "designated", "permissive", "official")


@dataclass
class Voie:
    """Un morceau de voie OSM entièrement situé dans la zone."""

    identifiant: int
    noeuds: list[int]
    x: list[float]
    y: list[float]
    etiquettes: dict[str, str]


def telecharger_extrait(parametres: dict[str, Any], dossier: Path) -> Path:
    """Télécharge le dernier extrait régional, vérifie son empreinte, note sa version."""
    base, nom = parametres["url_base"], parametres["fichier"]
    md5_publie = tele.lire(f"{base}/{nom}.md5").decode().split()[0]
    manifeste = tele.lire_manifeste(dossier)
    connu = manifeste.get("osm", {})
    if connu.get("md5") == md5_publie and (dossier / connu.get("fichier", "?")).exists():
        journal.info("Extrait OSM déjà à jour (%s).", connu["fichier"])
        return dossier / connu["fichier"]

    nom_date = _nom_date(base, nom)
    destination = dossier / nom_date
    journal.info("Téléchargement de %s…", nom_date)
    source = tele.telecharger(f"{base}/{nom_date}", destination)
    md5_recu = tele.empreinte(destination, "md5")
    if md5_recu != md5_publie:
        destination.unlink()
        raise ValueError(
            f"Empreinte incorrecte pour {nom_date} : reçu {md5_recu}, attendu {md5_publie}."
        )
    manifeste["osm"] = {
        "fichier": nom_date,
        "source": source,
        "telecharge_le": tele.maintenant(),
        "taille_octets": destination.stat().st_size,
        "md5": md5_recu,
        "sha256": tele.empreinte(destination),
        "licence": "ODbL — © les contributeurs d'OpenStreetMap",
    }
    tele.ecrire_manifeste(dossier, manifeste)
    return destination


def _nom_date(base: str, nom: str) -> str:
    """Nom daté vers lequel pointe « latest » (ex. ile-de-france-261113.osm.pbf)."""
    import urllib.error

    for url in tele.variantes(f"{base}/{nom}"):
        try:
            tele.ouvrir(url, suivre_redirections=False).close()
        except urllib.error.HTTPError as reponse:
            cible = reponse.headers.get("Location", "")
            trouve = re.search(r"[^/]+-\d{6}\.osm\.pbf$", cible)
            if trouve:
                return trouve.group(0)
        except (urllib.error.URLError, OSError):
            continue
    return nom


def voie_autorisee(etiquettes: dict[str, str], parametres: dict[str, Any]) -> bool:
    """Vrai si un piéton a le droit d'emprunter cette voie."""
    if etiquettes.get("highway") not in parametres["voies"]:
        return False
    interdit = parametres["acces_interdit"]
    pied = etiquettes.get("foot")
    if pied in interdit:
        return False
    if pied in PIETON_AUTORISE:
        return True
    if etiquettes.get("access") in interdit:
        return False
    # Allées privées de maisons : presque toujours fermées, rarement étiquetées.
    return etiquettes.get("service") not in ("driveway", "parking_aisle")


def extraire_voies(
    fichier_pbf: Path, emprise_l93: geo.Emprise, parametres: dict[str, Any]
) -> list[Voie]:
    """Lit l'extrait et garde les voies praticables à pied situées dans l'emprise."""
    import osmium

    ouest, sud, est, nord = geo.emprise_gps(emprise_l93, marge_m=200)
    lecteur = (
        osmium.FileProcessor(str(fichier_pbf), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    brutes: list[tuple[int, list[int], list[float], list[float], dict[str, str]]] = []
    for objet in lecteur:
        if not objet.is_way():
            continue
        etiquettes = {
            cle: objet.tags[cle] for cle in (*ETIQUETTES_GARDEES, "service") if cle in objet.tags
        }
        if not voie_autorisee(etiquettes, parametres):
            continue
        etiquettes.pop("service", None)
        noeuds = [n for n in objet.nodes if n.location.valid()]
        if len(noeuds) < 2:
            continue
        longitudes = [n.lon for n in noeuds]
        latitudes = [n.lat for n in noeuds]
        if (
            max(longitudes) < ouest
            or min(longitudes) > est
            or max(latitudes) < sud
            or min(latitudes) > nord
        ):
            continue
        brutes.append((objet.id, [n.ref for n in noeuds], longitudes, latitudes, etiquettes))

    voies: list[Voie] = []
    for identifiant, noeuds_ids, longitudes, latitudes, etiquettes in brutes:
        x, y = geo.gps_vers_l93(np.array(longitudes), np.array(latitudes))
        dedans = (
            (x >= emprise_l93[0])
            & (x <= emprise_l93[2])
            & (y >= emprise_l93[1])
            & (y <= emprise_l93[3])
        )
        for debut, fin in _plages(dedans):
            voies.append(
                Voie(
                    identifiant,
                    noeuds_ids[debut:fin],
                    [round(float(v), 2) for v in x[debut:fin]],
                    [round(float(v), 2) for v in y[debut:fin]],
                    etiquettes,
                )
            )
    journal.info("%d voies gardées dans la zone.", len(voies))
    return voies


def _plages(masque: np.ndarray) -> list[tuple[int, int]]:
    """Suites d'au moins deux positions consécutives vraies : [(début, fin exclue)]."""
    plages: list[tuple[int, int]] = []
    debut: int | None = None
    for position, valeur in enumerate([*masque.tolist(), False]):
        if valeur and debut is None:
            debut = position
        elif not valeur and debut is not None:
            if position - debut >= 2:
                plages.append((debut, position))
            debut = None
    return plages


def enregistrer_voies(voies: list[Voie], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(chemin, "wt", encoding="utf-8") as sortie:
        json.dump([asdict(v) for v in voies], sortie, ensure_ascii=False)


def charger_voies(chemin: Path) -> list[Voie]:
    with gzip.open(chemin, "rt", encoding="utf-8") as entree:
        return [Voie(**v) for v in json.load(entree)]
