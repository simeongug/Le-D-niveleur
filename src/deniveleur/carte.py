"""Carte de contrôle : les chemins du réseau, colorés selon leur pente."""

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import numpy as np

from deniveleur import geo
from deniveleur.donnees import telechargement as tele
from deniveleur.reseau import Reseau

journal = logging.getLogger(__name__)

ATTRIBUTION = "Chemins © les contributeurs d'OpenStreetMap (ODbL) — Fond et altitude © IGN"
# Longueur (en nombre de pas du profil) sur laquelle la pente est mesurée pour la couleur.
PAS_PAR_SEGMENT = 4


def telecharger_fond(
    parametres: dict[str, Any], emprise: geo.Emprise, destination: Path
) -> Path | None:
    """Récupère le Plan IGN de l'emprise. Renvoie None si le service ne répond pas."""
    ouest, sud, est, nord = emprise
    cote = parametres["taille_px"]
    largeur = cote if est - ouest >= nord - sud else round(cote * (est - ouest) / (nord - sud))
    hauteur = cote if nord - sud >= est - ouest else round(cote * (nord - sud) / (est - ouest))
    requete = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": parametres["couche_fond"],
        "STYLES": "",
        "CRS": "EPSG:2154",
        "BBOX": f"{ouest},{sud},{est},{nord}",
        "WIDTH": largeur,
        "HEIGHT": hauteur,
        "FORMAT": "image/png",
    }
    try:
        tele.telecharger(f"{parametres['url_fond']}?{urlencode(requete)}", destination)
    except ConnectionError as erreur:
        journal.warning("Fond de carte indisponible (%s) : carte sans fond.", erreur)
        return None
    return destination


def segments_colores(reseau: Reseau, emprise: geo.Emprise) -> tuple[np.ndarray, np.ndarray]:
    """Découpe chaque tronçon en petits segments ; renvoie (segments, pentes en %)."""
    ouest, sud, est, nord = emprise
    segments, pentes = [], []
    for i in range(reseau.nombre_troncons):
        x, y, z = reseau.trace(i)
        if x.max() < ouest or x.min() > est or y.max() < sud or y.min() > nord:
            continue
        positions = np.arange(0, len(x), PAS_PAR_SEGMENT)
        if positions[-1] != len(x) - 1:
            positions = np.append(positions, len(x) - 1)
        for debut, fin in zip(positions[:-1], positions[1:], strict=True):
            longueur = np.hypot(np.diff(x[debut : fin + 1]), np.diff(y[debut : fin + 1])).sum()
            segments.append(np.column_stack([x[debut : fin + 1], y[debut : fin + 1]]))
            pentes.append(abs(z[fin] - z[debut]) / max(longueur, 1e-6) * 100)
    return np.array(segments, dtype=object), np.array(pentes)


def dessiner(
    reseau: Reseau,
    parametres: dict[str, Any],
    emprise: geo.Emprise,
    sortie: Path,
    fond: Path | None = None,
    titre: str = "",
    reperes: list[tuple[float, float, str]] | None = None,
) -> Path:
    """Écrit la carte au format PNG. `reperes` : [(x, y, texte)] à marquer."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    ouest, sud, est, nord = emprise
    paliers, couleurs = parametres["paliers_pente"], parametres["couleurs"]
    segments, pentes = segments_colores(reseau, emprise)
    classes = np.digitize(pentes, paliers)

    cote = parametres["taille_px"] / 200
    rapport = (nord - sud) / (est - ouest)
    figure, axe = plt.subplots(figsize=(cote, cote * rapport + 0.6), dpi=200)
    if fond is not None:
        image = plt.imread(fond)[..., :3]
        gris = image.mean(axis=2, keepdims=True)
        # Fond pâli et presque gris : les couleurs de pente doivent ressortir.
        axe.imshow(0.5 + 0.5 * (0.4 * image + 0.6 * gris), extent=(ouest, est, sud, nord))
    epaisseur = float(np.clip(9000 / (est - ouest), 0.5, 2.5))
    for classe, couleur in enumerate(couleurs):
        choisis = list(segments[classes == classe])
        axe.add_collection(
            LineCollection(choisis, colors=couleur, linewidths=epaisseur, capstyle="round")
        )
    for x, y, texte in reperes or []:
        axe.plot(x, y, marker="*", color="black", markersize=14, markeredgecolor="white")
        axe.annotate(
            texte,
            (x, y),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=9,
            bbox={"boxstyle": "round", "fc": "white", "ec": "none", "alpha": 0.85},
        )
    bornes = [0, *paliers]
    libelles = [f"{a} à {b} %" for a, b in zip(bornes[:-1], bornes[1:], strict=True)]
    libelles.append(f"plus de {paliers[-1]} %")
    axe.legend(
        handles=[Line2D([0], [0], color=c, lw=3) for c in couleurs],
        labels=libelles,
        title="Pente",
        loc="upper right",
        framealpha=0.95,
    )
    axe.set_xlim(ouest, est)
    axe.set_ylim(sud, nord)
    axe.set_aspect("equal")
    axe.set_axis_off()
    axe.set_title(titre, fontsize=12)
    figure.text(0.5, 0.005, ATTRIBUTION, ha="center", fontsize=7, color="#444444")
    figure.tight_layout()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(sortie)
    plt.close(figure)
    return sortie


def dessiner_boucle(
    boucle: "Boucle",  # noqa: F821 - type défini dans deniveleur.moteur
    parametres: dict[str, Any],
    sortie: Path,
    fond: Path | None,
    emprise: geo.Emprise,
    titre: str,
) -> Path:
    """Carte d'une boucle (tracé coloré par la pente) avec son profil d'altitude dessous."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    ouest, sud, est, nord = emprise
    paliers, couleurs = parametres["paliers_pente"], parametres["couleurs"]
    x, y, z, d = boucle.x, boucle.y, boucle.altitudes, boucle.distances
    positions = np.arange(0, len(x), PAS_PAR_SEGMENT)
    if positions[-1] != len(x) - 1:
        positions = np.append(positions, len(x) - 1)
    pentes = np.abs(np.diff(z[positions])) / np.maximum(np.diff(d[positions]), 1e-6) * 100
    classes = np.digitize(pentes, paliers)
    segments = [
        np.column_stack([x[a : b + 1], y[a : b + 1]])
        for a, b in zip(positions[:-1], positions[1:], strict=True)
    ]

    largeur = 10.0
    hauteur_carte = largeur * (nord - sud) / (est - ouest)
    figure, (axe, axe_profil) = plt.subplots(
        2,
        1,
        figsize=(largeur, hauteur_carte + 3.2),
        dpi=160,
        height_ratios=[hauteur_carte, 2.4],
    )
    if fond is not None:
        image = plt.imread(fond)[..., :3]
        gris = image.mean(axis=2, keepdims=True)
        axe.imshow(0.35 + 0.65 * (0.5 * image + 0.5 * gris), extent=(ouest, est, sud, nord))
    axe.add_collection(
        LineCollection(segments, colors="white", linewidths=5.5, capstyle="round", zorder=2)
    )
    for classe, couleur in enumerate(couleurs):
        choisis = [s for s, c in zip(segments, classes, strict=True) if c == classe]
        axe.add_collection(
            LineCollection(choisis, colors=couleur, linewidths=3.2, capstyle="round", zorder=3)
        )
    # Un repère par kilomètre pour lire le sens du parcours.
    for km in range(1, int(d[-1] // 1000) + 1):
        i = int(np.searchsorted(d, km * 1000))
        axe.annotate(
            str(km),
            (x[i], y[i]),
            ha="center",
            va="center",
            fontsize=6.5,
            zorder=5,
            bbox={"boxstyle": "circle,pad=0.15", "fc": "white", "ec": "#333333", "lw": 0.6},
        )
    axe.plot(
        x[0], y[0], marker="*", color="black", markersize=18, markeredgecolor="white", zorder=6
    )
    bornes = [0, *paliers]
    libelles = [f"{a} à {b} %" for a, b in zip(bornes[:-1], bornes[1:], strict=True)]
    libelles.append(f"plus de {paliers[-1]} %")
    axe.legend(
        handles=[Line2D([0], [0], color=c, lw=3) for c in couleurs],
        labels=libelles,
        title="Pente",
        loc="upper left",
        framealpha=0.95,
        fontsize=8,
    )
    axe.set_xlim(ouest, est)
    axe.set_ylim(sud, nord)
    axe.set_aspect("equal")
    axe.set_axis_off()
    axe.set_title(titre, fontsize=11)

    km = d / 1000
    axe_profil.fill_between(km, z, z.min() - 8, color="#d9d9d9")
    axe_profil.plot(km, z, color="#444444", lw=0.8)
    for montee in boucle.montees:
        dans = (d >= montee.debut_m) & (d <= montee.debut_m + montee.longueur_m)
        axe_profil.fill_between(km[dans], z[dans], z.min() - 8, color="#f0641e", alpha=0.75)
    axe_profil.set_xlim(0, km[-1])
    axe_profil.set_ylim(z.min() - 8, z.max() + 10)
    axe_profil.set_xlabel("km")
    axe_profil.set_ylabel("altitude (m)")
    axe_profil.grid(alpha=0.3)
    figure.text(0.5, 0.004, ATTRIBUTION, ha="center", fontsize=6.5, color="#444444")
    figure.tight_layout()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(sortie)
    plt.close(figure)
    return sortie
