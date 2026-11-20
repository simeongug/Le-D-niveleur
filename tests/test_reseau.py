import numpy as np
import pytest

from deniveleur import parametres, reseau, trace
from deniveleur.donnees.altitude import ModeleAltitude
from deniveleur.donnees.osm import Voie

REGLAGES = parametres.charger()


def terrain_incline() -> ModeleAltitude:
    """Terrain de 400 m de côté qui monte de 10 % vers l'est (altitude = x / 10)."""
    centres = np.arange(1.0, 400.0, 2.0)
    grille = np.tile(centres / 10, (200, 1)).astype(np.float32)
    return ModeleAltitude(grille, (0, 0, 400, 400), 2.0)


def voies_en_croix() -> list[Voie]:
    # Une voie ouest-est (dans la pente) et une voie sud-nord (à plat) qui se croisent.
    return [
        Voie(1, [1, 2, 3], [100.0, 200.0, 300.0], [200.0, 200.0, 200.0], {"highway": "path"}),
        Voie(
            2,
            [4, 2, 5],
            [200.0, 200.0, 200.0],
            [100.0, 200.0, 300.0],
            {"highway": "residential", "name": "Rue Plate"},
        ),
    ]


def test_decouper_coupe_aux_carrefours():
    morceaux = reseau.decouper(voies_en_croix())
    assert [(voie.identifiant, debut, fin) for voie, debut, fin in morceaux] == [
        (1, 0, 1),
        (1, 1, 2),
        (2, 0, 1),
        (2, 1, 2),
    ]


def test_construire_calcule_longueurs_et_denivele():
    resultat = reseau.construire(voies_en_croix(), terrain_incline(), REGLAGES)
    assert resultat.nombre_troncons == 4
    assert len(resultat.noeud_x) == 5
    assert resultat.longueur == pytest.approx([100, 100, 100, 100])
    # Dans la pente : 10 m de D+ à l'aller, rien au retour.
    assert resultat.gain_aller[:2] == pytest.approx([10, 10], abs=0.05)
    assert resultat.gain_retour[:2] == pytest.approx([0, 0], abs=0.05)
    assert resultat.pente_max[:2] == pytest.approx([10, 10], abs=0.1)
    # À plat : aucun dénivelé.
    assert resultat.gain_aller[2:] == pytest.approx([0, 0], abs=0.05)
    assert list(resultat.chemin) == [True, True, False, False]
    assert resultat.noms[resultat.nom[2]] == "Rue Plate"


def test_reseau_aller_retour_sur_disque(tmp_path):
    resultat = reseau.construire(voies_en_croix(), terrain_incline(), REGLAGES, {"zone": "test"})
    resultat.enregistrer(tmp_path)
    relu = reseau.Reseau.charger(tmp_path)
    assert relu.resume() == resultat.resume()
    assert relu.infos["zone"] == "test"
    x, y, z = relu.trace(0)
    assert (x[0], x[-1]) == (100.0, 200.0)
    assert z[-1] - z[0] == pytest.approx(10, abs=0.05)


def test_pont_altitude_interpolee_entre_les_rives():
    # Vallée : sol à 50 m sur les rives (x < 100 ou x > 300), à 20 m au milieu (l'eau).
    centres = np.arange(1.0, 400.0, 2.0)
    profil_vallee = np.where((centres < 100) | (centres > 300), 50.0, 20.0)
    modele = ModeleAltitude(
        np.tile(profil_vallee, (200, 1)).astype(np.float32), (0, 0, 400, 400), 2
    )
    y = [200.0, 200.0]
    voies = [
        Voie(1, [1, 2], [20.0, 80.0], y, {"highway": "residential"}),
        # Pont en deux morceaux : le carrefour 3 est au-dessus de l'eau.
        Voie(2, [2, 3], [80.0, 200.0], y, {"highway": "residential", "bridge": "yes"}),
        Voie(3, [3, 4], [200.0, 320.0], y, {"highway": "residential", "bridge": "yes"}),
        Voie(4, [4, 5], [320.0, 380.0], y, {"highway": "residential"}),
    ]
    resultat = reseau.construire(voies, modele, REGLAGES)
    assert resultat.noeud_z == pytest.approx([50, 50, 50, 50, 50])
    assert resultat.gain_aller.sum() == pytest.approx(0, abs=0.01)
    assert resultat.gain_retour.sum() == pytest.approx(0, abs=0.01)


def test_mesurer_un_trace_dans_la_pente():
    # 200 m vers l'est sur le terrain incliné à 10 % : 20 m de D+.
    modele = terrain_incline()
    from deniveleur import geo

    longitudes, latitudes = geo.l93_vers_gps(np.array([100.0, 300.0]), np.array([200.0, 200.0]))
    # Le terrain d'essai est posé à l'origine du Lambert-93 : on mesure en repassant par le GPS.
    # Un point tous les 5 m monte de 0,5 m : avec le seuil réel de 2 m, chaque « marche »
    # tomberait pile sur le seuil et l'arrondi (altitudes en float32) déciderait selon la
    # machine (20 m sous Linux, 18 m sous Windows). Un seuil de 1,8 m laisse 0,2 m de marge.
    reglages = {**REGLAGES["profil"], "hysteresis_m": 1.8}
    mesure = trace.mesurer(longitudes, latitudes, modele, reglages)
    assert mesure.distance_m == pytest.approx(200, abs=0.5)
    assert mesure.dplus_m == pytest.approx(20, abs=0.5)
    assert mesure.dmoins_m == 0
