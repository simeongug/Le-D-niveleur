"""Tests du moteur sur un petit terrain artificiel (aucune donnée à télécharger)."""

import xml.etree.ElementTree as ET
from functools import cache

import numpy as np
import pytest

from deniveleur import geo, gpx, moteur, parametres, reseau
from deniveleur.donnees.altitude import ModeleAltitude
from deniveleur.donnees.osm import Voie
from deniveleur.moteur.boucle import sans_allers_retours
from deniveleur.moteur.itineraire import reperer_montees

PARAMETRES = parametres.charger()
COTE, PAS = 2000, 100  # quadrillage de rues de 2 km de côté, une rue tous les 100 m


def altitude_terrain(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Collines et vallons : environ 60 m d'écart entre haut et bas."""
    return 60 + 15 * np.sin(x / 300) + 15 * np.cos(y / 250)


@cache
def reseau_essai(tout_en_chemin: bool = False) -> reseau.Reseau:
    centres = np.arange(1.0, COTE + 200, 2.0)
    gx, gy = np.meshgrid(centres, centres[::-1])
    modele = ModeleAltitude(
        altitude_terrain(gx, gy).astype(np.float32), (0, 0, COTE + 200, COTE + 200), 2.0
    )
    lignes = np.arange(100, COTE + 101, PAS, dtype=float)
    nombre = len(lignes)
    voies = []
    for i, valeur in enumerate(lignes):
        # Rues est-ouest (identifiants de nœud i*nombre + j) puis nord-sud.
        voies.append(
            Voie(
                i,
                [i * nombre + j for j in range(nombre)],
                list(lignes),
                [valeur] * nombre,
                {"highway": "path"},
            )
        )
        voies.append(
            Voie(
                1000 + i,
                [j * nombre + i for j in range(nombre)],
                [valeur] * nombre,
                list(lignes),
                {"highway": "path"}
                if tout_en_chemin
                else {"highway": "residential", "name": f"Rue {i}"},
            )
        )
    return reseau.construire(voies, modele, PARAMETRES)


def depart_gps() -> tuple[float, float]:
    longitude, latitude = geo.l93_vers_gps(np.array([1100.0]), np.array([1100.0]))
    return float(latitude[0]), float(longitude[0])


@cache
def boucles_essai() -> tuple:
    latitude, longitude = depart_gps()
    return moteur.generer(
        reseau_essai(), PARAMETRES, latitude, longitude, 5000, budget_s=3, propositions=2
    )


def test_le_moteur_trouve_une_boucle():
    boucles, rapport = boucles_essai()
    assert boucles, "aucune boucle trouvée"
    assert rapport.valides >= 1
    assert rapport.ecart_depart_m < 1


def test_boucle_fermee_et_dans_la_tolerance():
    boucle = boucles_essai()[0][0]
    assert (boucle.x[0], boucle.y[0]) == pytest.approx((boucle.x[-1], boucle.y[-1]))
    assert 4750 <= boucle.distance_m <= 5250
    assert boucle.distances[-1] == pytest.approx(boucle.distance_m, rel=1e-6)


def test_aucun_troncon_pris_deux_fois_ni_demi_tour():
    boucle = boucles_essai()[0][0]
    # Chaque point intermédiaire n'est visité qu'une fois, sauf aux croisements :
    # on vérifie plutôt qu'aucun segment de 5 m n'est parcouru deux fois.
    segments = {
        tuple(sorted(((round(x0), round(y0)), (round(x1), round(y1)))))
        for x0, y0, x1, y1 in zip(
            boucle.x[:-1], boucle.y[:-1], boucle.x[1:], boucle.y[1:], strict=True
        )
    }
    assert len(segments) == len(boucle.x) - 1
    dx, dy = np.diff(boucle.x), np.diff(boucle.y)
    longueur = np.hypot(dx, dy)
    garde = longueur > 0.5
    ux, uy = dx[garde] / longueur[garde], dy[garde] / longueur[garde]
    cosinus = ux[:-1] * ux[1:] + uy[:-1] * uy[1:]
    assert cosinus.min() > np.cos(np.radians(160))


def test_le_dplus_annonce_correspond_au_profil():
    boucle = boucles_essai()[0][0]
    from deniveleur import profil

    dplus, dmoins = profil.gains_hysteresis(boucle.altitudes, PARAMETRES["profil"]["hysteresis_m"])
    assert boucle.dplus_m == pytest.approx(dplus)
    assert boucle.dplus_m == pytest.approx(boucle.dmoins_m, abs=5)  # on revient au départ
    assert boucle.dplus_m > 100  # le terrain permet nettement mieux qu'un tour à plat


def test_propositions_differentes():
    boucles = boucles_essai()[0]
    if len(boucles) < 2:
        pytest.skip("une seule proposition trouvée en 3 s")
    commun = np.intersect1d(boucles[0].troncons, boucles[1].troncons)
    assert len(commun) < 0.8 * min(len(boucles[0].troncons), len(boucles[1].troncons))


def test_part_de_chemin_demandee():
    latitude, longitude = depart_gps()
    boucles, _ = moteur.generer(
        reseau_essai(), PARAMETRES, latitude, longitude, 5000, budget_s=3, chemin_min=0.6
    )
    assert boucles
    boucle = boucles[0]
    alerte = any("non atteinte" in texte for texte in boucle.alertes)
    assert boucle.part_chemin >= 0.6 or alerte


def test_export_gpx_lisible():
    boucle = boucles_essai()[0][0]
    racine = ET.fromstring(gpx.en_gpx(boucle, "Essai & test"))
    espace = "{http://www.topografix.com/GPX/1/1}"
    points = racine.findall(f".//{espace}trkpt")
    reperes = racine.findall(f"{espace}wpt")
    assert len(points) == len(boucle.x)
    assert len(reperes) == 2 * len(boucle.montees)
    assert points[0].find(f"{espace}ele") is not None
    assert racine.find(f"{espace}metadata/{espace}name").text == "Essai & test"


def test_sans_allers_retours():
    assert sans_allers_retours([2, 4, 5, 3, 6]) == [6]
    assert sans_allers_retours([2, 4, 6]) == [2, 4, 6]


def test_reperer_montees():
    distances = np.arange(0, 1000, 5.0)
    # Plat, montée de 40 m avec un petit replat de 3 m, descente, petite bosse de 8 m.
    altitudes = np.interp(
        distances, [0, 100, 300, 320, 500, 700, 800, 850, 999], [0, 0, 25, 22, 40, 10, 10, 18, 10]
    )
    montees = reperer_montees(distances, altitudes, PARAMETRES["montees"])
    assert len(montees) == 1
    bas, haut = montees[0]
    assert distances[bas] == pytest.approx(100)
    assert distances[haut] == pytest.approx(500)


def _generer(tout_en_chemin=False, **options):
    latitude, longitude = depart_gps()
    return moteur.generer(
        reseau_essai(tout_en_chemin), PARAMETRES, latitude, longitude, 5000, budget_s=3, **options
    )


def test_pente_max_ecarte_les_troncons_raides():
    r = reseau_essai()
    pente = float(np.percentile(r.pente_max[~r.escalier], 60))
    boucles, _ = _generer(pente_max_pct=pente)
    if not boucles:
        pytest.skip("aucune boucle sous cette pente sur le terrain d'essai")
    interdits = set(np.flatnonzero(r.pente_max > pente))
    assert not interdits & set(boucles[0].troncons.tolist())


def test_sans_bitume_n_emprunte_que_des_chemins():
    r = reseau_essai(True)
    boucles, _ = _generer(tout_en_chemin=True, sans_bitume=True)
    assert boucles
    assert r.chemin[boucles[0].troncons].all()


def test_sans_bitume_sans_assez_de_chemins_donne_un_message_clair():
    # Ici seules les rues est-ouest sont des sentiers : aucune boucle n'est possible.
    with pytest.raises(ValueError, match="préférences"):
        _generer(sans_bitume=True)


def test_doublons_autorises_ne_reduisent_pas_le_dplus():
    sans, _ = _generer()
    avec, _ = _generer(doublons=True)
    assert sans and avec
    assert avec[0].dplus_m >= 0.9 * sans[0].dplus_m
