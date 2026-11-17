"""Lance les cas de référence du moteur et écrit le rapport `benchmarks/rapport.md`.

    python benchmarks/lancer.py            # tous les cas
    python benchmarks/lancer.py --cartes   # avec une carte par cas dans sorties/benchmarks/

Il faut avoir préparé les données avant (`deniveleur donnees tout`).
"""

import argparse
import tomllib
from datetime import date
from pathlib import Path

from deniveleur import carte, gpx, moteur, parametres
from deniveleur.reseau import Reseau

ICI = Path(__file__).parent


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--cartes", action="store_true", help="dessine une carte par cas")
    analyseur.add_argument("--donnees", type=Path, default=parametres.DOSSIER_DONNEES)
    analyseur.add_argument("--zone", default=parametres.ZONE_PAR_DEFAUT)
    options = analyseur.parse_args()

    reglages = parametres.charger()
    reseau = Reseau.charger(options.donnees / options.zone)
    cas = tomllib.loads((ICI / "cas.toml").read_text("utf-8"))["cas"]
    lignes = [
        "# Rapport de benchmark du moteur",
        "",
        f"Généré le {date.today().isoformat()} par `python benchmarks/lancer.py`, "
        f"réseau construit à partir de `{reseau.infos.get('extrait_osm', '?')}`.",
        "",
        "| Cas | Distance | D+ | D+ par km | Chemin | Escaliers | En double | Durée "
        "| Plancher | État |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    echecs = 0
    sorties = Path("sorties") / "benchmarks"
    for numero, fiche in enumerate(cas, 1):
        latitude, longitude = fiche["depart"]
        boucles, rapport = moteur.generer(
            reseau,
            reglages,
            latitude,
            longitude,
            fiche["distance_km"] * 1000,
            chemin_min=fiche.get("chemin_min", 0.0),
            escaliers=fiche.get("escaliers"),
        )
        plancher = fiche["dplus_min_m"]
        if not boucles:
            echecs += 1
            lignes.append(
                f"| {fiche['nom']} | — | — | — | — | — | — | "
                f"{rapport.duree_s:.0f} s | {plancher} m | ❌ aucune boucle |"
            )
            continue
        boucle = boucles[0]
        reussi = boucle.dplus_m >= plancher
        echecs += not reussi
        lignes.append(
            f"| {fiche['nom']} | {boucle.distance_m / 1000:.1f} km | {boucle.dplus_m:.0f} m | "
            f"{boucle.dplus_m / boucle.distance_m * 1000:.0f} m | "
            f"{boucle.part_chemin * 100:.0f} % | "
            f"{boucle.escaliers_m:.0f} m | {boucle.double_m:.0f} m | {rapport.duree_s:.0f} s | "
            f"{plancher} m | {'✅' if reussi else '❌'} |"
        )
        print(lignes[-1])
        gpx.ecrire(boucle, sorties / f"cas-{numero}.gpx", fiche["nom"])
        if options.cartes:
            marge = 300
            emprise = (
                round(boucle.x.min() - marge),
                round(boucle.y.min() - marge),
                round(boucle.x.max() + marge),
                round(boucle.y.max() + marge),
            )
            fond = carte.telecharger_fond(
                {**reglages["carte"], "taille_px": 2000},
                emprise,
                options.donnees / options.zone / f"fond_benchmark_{numero}.png",
            )
            titre = f"{fiche['nom']} : {boucle.distance_m / 1000:.1f} km, D+ {boucle.dplus_m:.0f} m"
            carte.dessiner_boucle(
                boucle, reglages["carte"], sorties / f"cas-{numero}.png", fond, emprise, titre
            )
    lignes += [
        "",
        "Toutes les boucles respectent : retour au départ, longueur dans la tolérance (±5 %), "
        "aucun tronçon emprunté deux fois, aucun demi-tour.",
        "« En double » : longueur qui passe à moins de 15-30 m d'une autre partie du parcours "
        "(hors croisements).",
        "",
        "Notes :",
        *[f"- {fiche['nom']} : {fiche['note']}" for fiche in cas if "note" in fiche],
    ]
    (ICI / "rapport.md").write_text("\n".join(lignes) + "\n", "utf-8")
    print(f"Rapport écrit : {ICI / 'rapport.md'}")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
