import numpy as np
import pytest

from deniveleur import parametres, trace
from deniveleur.donnees import altitude, osm, telechargement

OSM = parametres.charger()["osm"]


def test_parametres_zone_par_defaut():
    zone = parametres.zone(parametres.ZONE_PAR_DEFAUT)
    ouest, sud, est, nord = zone["emprise_l93"]
    assert ouest < est and sud < nord


def test_zone_inconnue():
    with pytest.raises(KeyError):
        parametres.zone("atlantide")


@pytest.mark.parametrize(
    ("etiquettes", "attendu"),
    [
        ({"highway": "path"}, True),
        ({"highway": "motorway"}, False),
        ({"highway": "path", "access": "private"}, False),
        ({"highway": "path", "access": "private", "foot": "yes"}, True),
        ({"highway": "residential", "foot": "no"}, False),
        ({"highway": "service", "service": "driveway"}, False),
        ({"highway": "steps"}, True),
    ],
)
def test_voie_autorisee(etiquettes, attendu):
    assert osm.voie_autorisee(etiquettes, OSM) is attendu


def test_plages_dans_la_zone():
    masque = np.array([True, True, False, True, False, True, True, True])
    assert osm._plages(masque) == [(0, 2), (5, 8)]


def test_voies_aller_retour_sur_disque(tmp_path):
    voies = [osm.Voie(1, [10, 11], [0.0, 5.0], [0.0, 1.0], {"highway": "path", "name": "Allée"})]
    osm.enregistrer_voies(voies, tmp_path / "voies.json.gz")
    assert osm.charger_voies(tmp_path / "voies.json.gz") == voies


def test_variantes_repli_http():
    assert telechargement.variantes("https://exemple.fr/a") == [
        "https://exemple.fr/a",
        "https://exemple.fr/a",
        "http://exemple.fr/a",
    ]


def test_coins_des_dalles():
    coins = altitude.coins_des_dalles((0, 0, 4000, 2000), 2000)
    assert coins == [(0, 0), (2000, 0)]
    with pytest.raises(ValueError):
        altitude.coins_des_dalles((0, 0, 3000, 2000), 2000)


def test_altitude_interpolee_sur_un_plan_incline():
    # Terrain qui monte de 1 m par mètre vers l'est : l'altitude vaut x.
    resolution = 2.0
    centres = np.arange(1.0, 100.0, resolution)
    grille = np.tile(centres, (50, 1)).astype(np.float32)
    modele = altitude.ModeleAltitude(grille, (0, 0, 100, 100), resolution)
    x = np.array([10.0, 33.3, 71.5])
    assert modele.altitude(x, np.array([50.0, 12.0, 88.0])) == pytest.approx(x, abs=1e-4)


def test_decoder_polyline_exemple_de_reference():
    # Exemple de la documentation du format.
    longitudes, latitudes = trace.decoder_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert latitudes == pytest.approx([38.5, 40.7, 43.252])
    assert longitudes == pytest.approx([-120.2, -120.95, -126.453])


def test_lire_gpx(tmp_path):
    fichier = tmp_path / "t.gpx"
    fichier.write_text(
        '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
        '<trkpt lat="48.84" lon="2.22"/><trkpt lat="48.85" lon="2.23"/>'
        "</trkseg></trk></gpx>"
    )
    longitudes, latitudes = trace.lire_gpx(fichier)
    assert list(longitudes) == [2.22, 2.23]
    assert list(latitudes) == [48.84, 48.85]


def _faux_reseau(monkeypatch, contenu: bytes, en_panne: str) -> list[str]:
    """Remplace le réseau : les adresses contenant `en_panne` ne répondent pas."""
    import hashlib
    import urllib.error

    demandes: list[str] = []

    def repondre(url: str) -> None:
        demandes.append(url)
        if en_panne in url:
            raise ConnectionError(f"Téléchargement impossible : {url}")

    def lire(url: str) -> bytes:
        repondre(url)
        return f"{hashlib.md5(contenu).hexdigest()}  extrait.osm.pbf\n".encode()

    def telecharger(url: str, destination):
        repondre(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contenu)
        return url

    def ouvrir(url: str, suivre_redirections: bool = True):
        raise urllib.error.URLError("pas de redirection")

    monkeypatch.setattr(telechargement, "lire", lire)
    monkeypatch.setattr(telechargement, "telecharger", telecharger)
    monkeypatch.setattr(telechargement, "ouvrir", ouvrir)
    return demandes


SOURCES_ESSAI = {
    "sources": [
        {"nom": "Principale", "url_base": "https://principale.test/fr", "fichier": "a.osm.pbf"},
        {"nom": "Secours", "url_base": "https://secours.test/fr", "fichier": "b.osm.pbf"},
    ]
}


def test_extrait_osm_bascule_sur_la_source_de_secours(monkeypatch, tmp_path):
    demandes = _faux_reseau(monkeypatch, b"donnees osm", en_panne="principale.test")
    fichier = osm.telecharger_extrait(SOURCES_ESSAI, tmp_path)
    assert fichier == tmp_path / "b.osm.pbf"
    assert fichier.read_bytes() == b"donnees osm"
    manifeste = telechargement.lire_manifeste(tmp_path)
    assert manifeste["osm"]["source"] == "https://secours.test/fr/b.osm.pbf"
    assert demandes[0].startswith("https://principale.test")


def test_extrait_osm_aucune_source_disponible(monkeypatch, tmp_path):
    _faux_reseau(monkeypatch, b"donnees osm", en_panne=".test")
    with pytest.raises(ConnectionError, match="Principale.*\n.*Secours"):
        osm.telecharger_extrait(SOURCES_ESSAI, tmp_path)


def test_sources_osm_configurees():
    noms = [source["nom"] for source in OSM["sources"]]
    assert noms[0] == "Geofabrik"
    assert len(noms) >= 2
