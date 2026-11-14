"""Profil d'altitude d'un tracé : découpage régulier, lissage, calcul du D+.

Tout est en mètres. Ce module ne lit aucun fichier : il ne fait que du calcul,
ce qui le rend facile à tester.
"""

import numpy as np
from numpy.typing import NDArray

Tableau = NDArray[np.float64]


def abscisses(x: Tableau, y: Tableau) -> Tableau:
    """Distance cumulée le long de la ligne, en partant de 0."""
    pas = np.hypot(np.diff(x), np.diff(y))
    return np.concatenate([[0.0], np.cumsum(pas)])


def densifier(x: Tableau, y: Tableau, pas_m: float) -> tuple[Tableau, Tableau, Tableau]:
    """Place un point tous les `pas_m` environ le long de la ligne.

    Renvoie (x, y, distance cumulée). Les deux extrémités sont conservées.
    """
    cumul = abscisses(x, y)
    longueur = float(cumul[-1])
    if longueur == 0.0:
        return x[:1].copy(), y[:1].copy(), np.zeros(1)
    nombre = max(1, int(np.ceil(longueur / pas_m)))
    cibles = np.linspace(0.0, longueur, nombre + 1)
    return np.interp(cibles, cumul, x), np.interp(cibles, cumul, y), cibles


def lisser(z: Tableau, pas_m: float, lissage_m: float) -> Tableau:
    """Moyenne glissante sur `lissage_m`, en gardant les deux altitudes d'extrémité.

    Garder les extrémités est indispensable : deux chemins qui se rejoignent
    doivent avoir la même altitude au carrefour.
    """
    demi = int(round(lissage_m / pas_m / 2))
    if demi < 1 or len(z) < 3:
        return z.copy()
    demi = min(demi, len(z) - 1)
    # Prolonge le profil par symétrie centrale autour de chaque extrémité : une
    # pente régulière reste régulière, et les altitudes d'extrémité ne bougent pas.
    avant = 2 * z[0] - z[demi:0:-1]
    apres = 2 * z[-1] - z[-2 : -demi - 2 : -1]
    etendu = np.concatenate([avant, z, apres])
    noyau = np.ones(2 * demi + 1) / (2 * demi + 1)
    return np.convolve(etendu, noyau, mode="valid")


def gains_bruts(z: Tableau) -> tuple[float, float]:
    """Somme des montées et somme des descentes, sans seuil (valeurs positives)."""
    ecarts = np.diff(z)
    return float(ecarts[ecarts > 0].sum()), float(-ecarts[ecarts < 0].sum())


def gains_hysteresis(z: Tableau, seuil_m: float) -> tuple[float, float]:
    """D+ et D− en ignorant les variations plus petites que `seuil_m`.

    On garde une altitude de référence ; elle ne bouge que lorsque l'altitude
    s'en écarte d'au moins `seuil_m`. C'est la méthode habituelle des montres
    et des plateformes pour ne pas compter le bruit comme du dénivelé.
    """
    if len(z) == 0:
        return 0.0, 0.0
    reference = float(z[0])
    montee = descente = 0.0
    for altitude in z[1:]:
        ecart = float(altitude) - reference
        if ecart >= seuil_m:
            montee += ecart
            reference = float(altitude)
        elif ecart <= -seuil_m:
            descente -= ecart
            reference = float(altitude)
    return montee, descente


def pente_max(z: Tableau, distances: Tableau, fenetre_m: float = 20.0) -> float:
    """Plus forte pente (en %, valeur absolue) mesurée sur `fenetre_m`."""
    if len(z) < 2 or distances[-1] <= 0:
        return 0.0
    pas = float(distances[1] - distances[0])
    saut = max(1, int(round(fenetre_m / pas)))
    saut = min(saut, len(z) - 1)
    pentes = (z[saut:] - z[:-saut]) / (distances[saut:] - distances[:-saut])
    return float(np.abs(pentes).max() * 100)
