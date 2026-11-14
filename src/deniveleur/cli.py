"""Ligne de commande du Déniveleur.

À l'étape 1, elle sait seulement se présenter (`--version`) et lister les
régions connues (`regions`). La génération d'itinéraires arrive à l'étape 3.
"""

import argparse
from collections.abc import Sequence

from deniveleur import __version__
from deniveleur.regions import REGION_PAR_DEFAUT, REGIONS


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="deniveleur",
        description="Génère des boucles trail à dénivelé positif maximal ou ciblé.",
    )
    analyseur.add_argument("--version", action="version", version=f"deniveleur {__version__}")
    commandes = analyseur.add_subparsers(dest="commande", title="commandes")
    commandes.add_parser("regions", help="liste les régions couvertes")
    return analyseur


def afficher_regions() -> None:
    for region in REGIONS.values():
        marque = " (par défaut)" if region.identifiant == REGION_PAR_DEFAUT else ""
        print(f"{region.identifiant} : {region.nom}{marque}")


def main(arguments: Sequence[str] | None = None) -> int:
    analyseur = construire_analyseur()
    options = analyseur.parse_args(arguments)
    if options.commande == "regions":
        afficher_regions()
        return 0
    analyseur.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
