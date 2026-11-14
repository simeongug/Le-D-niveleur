"""Ligne de commande du Déniveleur.

À l'étape 2, elle prépare les données (chemins + altitude), dessine la carte de
contrôle et mesure le D+ d'un tracé existant. La génération d'itinéraires
arrive à l'étape 3.
"""

import argparse
import logging
import time
from collections.abc import Sequence
from pathlib import Path

from deniveleur import __version__, parametres
from deniveleur.regions import REGION_PAR_DEFAUT, REGIONS

journal = logging.getLogger("deniveleur")


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="deniveleur",
        description="Génère des boucles trail à dénivelé positif maximal ou ciblé.",
    )
    analyseur.add_argument("--version", action="version", version=f"deniveleur {__version__}")
    commandes = analyseur.add_subparsers(dest="commande", title="commandes")
    commandes.add_parser("regions", help="liste les régions couvertes")

    donnees = commandes.add_parser("donnees", help="prépare les chemins et l'altitude")
    donnees.add_argument(
        "action",
        choices=["telecharger", "reseau", "carte", "tout"],
        help="telecharger : récupère OSM et l'altitude IGN ; reseau : construit le réseau "
        "de chemins ; carte : dessine la carte de contrôle ; tout : les trois à la suite",
    )
    _options_communes(donnees)
    donnees.add_argument("--centre", help="carte : centre « latitude,longitude » d'un zoom")
    donnees.add_argument("--rayon", type=float, default=2.0, help="carte : rayon du zoom en km")
    donnees.add_argument("--sortie", type=Path, help="carte : fichier image à écrire")

    denivele = commandes.add_parser("denivele", help="mesure le D+ d'un fichier GPX")
    denivele.add_argument("gpx", type=Path, help="fichier GPX à mesurer")
    _options_communes(denivele)
    return analyseur


def _options_communes(analyseur: argparse.ArgumentParser) -> None:
    analyseur.add_argument("--zone", default=parametres.ZONE_PAR_DEFAUT, help="zone à traiter")
    analyseur.add_argument(
        "--donnees", type=Path, default=parametres.DOSSIER_DONNEES, help="dossier des données"
    )


def afficher_regions() -> None:
    for region in REGIONS.values():
        marque = " (par défaut)" if region.identifiant == REGION_PAR_DEFAUT else ""
        print(f"{region.identifiant} : {region.nom}{marque}")


def telecharger(zone: str, dossier: Path) -> None:
    from deniveleur.donnees import altitude, osm

    reglages = parametres.charger()
    emprise = tuple(parametres.zone(zone)["emprise_l93"])
    fichier = osm.telecharger_extrait(reglages["osm"], dossier)
    print(f"Chemins OpenStreetMap : {fichier.name}")
    nouvelles = altitude.telecharger_dalles(reglages["altitude"], emprise, dossier)
    total = len(altitude.coins_des_dalles(emprise, reglages["altitude"]["taille_dalle_m"]))
    print(f"Altitude IGN : {total} dalles, dont {nouvelles} téléchargées maintenant")
    print(f"Versions et empreintes notées dans {dossier / 'manifeste.json'}")


def construire_reseau(zone: str, dossier: Path) -> None:
    from deniveleur import reseau
    from deniveleur.donnees import altitude, osm
    from deniveleur.donnees import telechargement as tele

    reglages = parametres.charger()
    emprise = tuple(parametres.zone(zone)["emprise_l93"])
    manifeste = tele.lire_manifeste(dossier)
    if "osm" not in manifeste:
        raise SystemExit("Données absentes. Lancer d'abord : deniveleur donnees telecharger")
    debut = time.perf_counter()
    voies = osm.extraire_voies(dossier / manifeste["osm"]["fichier"], emprise, reglages["osm"])
    osm.enregistrer_voies(voies, dossier / zone / "voies.json.gz")
    modele = altitude.ModeleAltitude.charger(reglages["altitude"], emprise, dossier)
    infos = {
        "zone": zone,
        "construit_le": tele.maintenant(),
        "extrait_osm": manifeste["osm"]["fichier"],
        "md5_extrait_osm": manifeste["osm"]["md5"],
        "resolution_altitude_m": reglages["altitude"]["resolution_m"],
    }
    resultat = reseau.construire(voies, modele, reglages, infos)
    resultat.enregistrer(dossier / zone)
    bilan = resultat.resume()
    print(f"Réseau construit en {time.perf_counter() - debut:.0f} s :")
    print(f"  {bilan['troncons']} tronçons, {bilan['carrefours']} carrefours")
    print(f"  {bilan['km_total']} km de voies, dont {bilan['part_chemin_pct']} % de chemin")
    print(f"  altitude de {bilan['altitude_min_m']} m à {bilan['altitude_max_m']} m")


def dessiner_carte(
    zone: str, dossier: Path, centre: str | None, rayon_km: float, sortie: Path | None
) -> None:
    import numpy as np

    from deniveleur import carte, geo
    from deniveleur.reseau import Reseau

    reglages = parametres.charger()
    fiche = parametres.zone(zone)
    emprise = tuple(fiche["emprise_l93"])
    reperes = []
    nom_fond, titre = "fond.png", fiche["nom"]
    if centre:
        latitude, longitude = (float(v) for v in centre.split(","))
        x, y = geo.gps_vers_l93(np.array([longitude]), np.array([latitude]))
        rayon = rayon_km * 1000
        emprise = (
            max(emprise[0], round(x[0] - rayon)),
            max(emprise[1], round(y[0] - rayon)),
            min(emprise[2], round(x[0] + rayon)),
            min(emprise[3], round(y[0] + rayon)),
        )
        reperes.append((float(x[0]), float(y[0]), "Centre"))
        nom_fond = f"fond_{emprise[0]}_{emprise[1]}_{emprise[2]}_{emprise[3]}.png"
        titre += f" — {rayon_km:g} km autour de {latitude:.4f}, {longitude:.4f}"
    reseau = Reseau.charger(dossier / zone)
    fond: Path | None = dossier / zone / nom_fond
    if fond is not None and not fond.exists():
        fond = carte.telecharger_fond(reglages["carte"], emprise, fond)
    sortie = sortie or Path("sorties") / ("carte-pentes-zoom.png" if centre else "carte-pentes.png")
    carte.dessiner(reseau, reglages["carte"], emprise, sortie, fond, titre, reperes)
    print(f"Carte écrite : {sortie}")


def mesurer_gpx(gpx: Path, zone: str, dossier: Path) -> None:
    from deniveleur import trace
    from deniveleur.donnees.altitude import ModeleAltitude

    reglages = parametres.charger()
    emprise = tuple(parametres.zone(zone)["emprise_l93"])
    modele = ModeleAltitude.charger(reglages["altitude"], emprise, dossier)
    longitudes, latitudes = trace.lire_gpx(gpx)
    mesure = trace.mesurer(longitudes, latitudes, modele, reglages["profil"])
    print(f"Distance : {mesure.distance_m / 1000:.2f} km")
    print(f"D+ : {mesure.dplus_m:.0f} m   D− : {mesure.dmoins_m:.0f} m")
    print(f"Altitude : de {mesure.altitude_min_m:.0f} m à {mesure.altitude_max_m:.0f} m")


def main(arguments: Sequence[str] | None = None) -> int:
    analyseur = construire_analyseur()
    options = analyseur.parse_args(arguments)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if options.commande == "regions":
        afficher_regions()
    elif options.commande == "donnees":
        if options.action in ("telecharger", "tout"):
            telecharger(options.zone, options.donnees)
        if options.action in ("reseau", "tout"):
            construire_reseau(options.zone, options.donnees)
        if options.action in ("carte", "tout"):
            dessiner_carte(
                options.zone, options.donnees, options.centre, options.rayon, options.sortie
            )
    elif options.commande == "denivele":
        mesurer_gpx(options.gpx, options.zone, options.donnees)
    else:
        analyseur.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
