"""Export d'une boucle au format GPX (Strava, Garmin Connect, Suunto, Coros)."""

from pathlib import Path
from xml.sax.saxutils import escape

from deniveleur.moteur.itineraire import Boucle

EN_TETE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx version="1.1" creator="Le Déniveleur" xmlns="http://www.topografix.com/GPX/1/1" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
    'http://www.topografix.com/GPX/1/1/gpx.xsd">\n'
)


def en_gpx(boucle: Boucle, nom: str) -> str:
    """Texte GPX : la trace, plus un repère en bas et en haut de chaque montée principale."""
    lignes = [EN_TETE, f"  <metadata><name>{escape(nom)}</name></metadata>\n"]
    for montee in boucle.montees:
        for (longitude, latitude, altitude), titre in (
            (montee.bas, f"Bas côte {montee.numero}"),
            (montee.haut, f"Haut côte {montee.numero} (+{montee.denivele_m:.0f} m)"),
        ):
            lignes.append(
                f'  <wpt lat="{latitude:.6f}" lon="{longitude:.6f}"><ele>{altitude:.1f}</ele>'
                f"<name>{escape(titre)}</name><desc>{escape(montee.nom)}</desc></wpt>\n"
            )
    lignes.append(f"  <trk><name>{escape(nom)}</name><type>running</type><trkseg>\n")
    for longitude, latitude, altitude in zip(
        boucle.longitudes, boucle.latitudes, boucle.altitudes, strict=True
    ):
        lignes.append(
            f'    <trkpt lat="{latitude:.6f}" lon="{longitude:.6f}">'
            f"<ele>{altitude:.1f}</ele></trkpt>\n"
        )
    lignes.append("  </trkseg></trk>\n</gpx>\n")
    return "".join(lignes)


def ecrire(boucle: Boucle, chemin: Path, nom: str) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(en_gpx(boucle, nom), "utf-8")
    return chemin
