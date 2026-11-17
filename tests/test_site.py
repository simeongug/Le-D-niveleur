"""Tests du site : on lance l'API sur le petit terrain artificiel des tests du moteur."""

import time

import pytest
from fastapi.testclient import TestClient

from deniveleur import parametres
from deniveleur.site.api import creer_application
from tests.test_moteur import COTE, depart_gps, reseau_essai


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("donnees")
    reseau_essai().enregistrer(dossier / "essai")
    reglages = parametres.charger()
    reglages = {**reglages, "site": {**reglages["site"], "budget_s": 2, "file_max": 3}}
    app = creer_application(dossier, "essai", reglages, (0, 0, COTE + 200, COTE + 200))
    with TestClient(app) as client:
        yield client


def attendre(client, identifiant, delai_s=40):
    fin = time.time() + delai_s
    while time.time() < fin:
        reponse = client.get(f"/api/calculs/{identifiant}").json()
        if reponse["etat"] in ("termine", "erreur"):
            return reponse
        time.sleep(0.3)
    raise AssertionError("calcul trop long")


def demande(**autres):
    latitude, longitude = depart_gps()
    return {"latitude": latitude, "longitude": longitude, "distance_km": 5, **autres}


def test_page_et_infos(client):
    assert "Le Déniveleur" in client.get("/").text
    assert client.get("/statique/app.js").status_code == 200
    assert client.get("/statique/vendor/maplibre-gl.js").status_code == 200
    infos = client.get("/api/infos").json()
    assert infos["budget_s"] == 2
    assert len(infos["couleurs_pente"]) == len(infos["paliers_pente"]) + 1


def test_calcul_complet_et_gpx(client):
    reponse = client.post("/api/calculs", json=demande(propositions=2))
    assert reponse.status_code == 202
    fini = attendre(client, reponse.json()["id"])
    assert fini["etat"] == "termine", fini["erreur"]
    propositions = fini["resultat"]["propositions"]
    assert propositions
    premiere = propositions[0]
    assert 4750 <= premiere["distance_m"] <= 5250
    assert premiere["points"][0][:2] == pytest.approx(premiere["points"][-1][:2], abs=1e-5)
    assert premiere["temps_texte"]
    gpx = client.get(f"/api/calculs/{fini['id']}/gpx/1")
    assert gpx.status_code == 200
    assert "attachment" in gpx.headers["content-disposition"]
    assert gpx.text.count("<trkpt") > 100
    assert client.get(f"/api/calculs/{fini['id']}/gpx/9").status_code == 404


def test_dplus_cible(client):
    reponse = client.post("/api/calculs", json=demande(dplus_cible=80, propositions=1))
    fini = attendre(client, reponse.json()["id"])
    assert fini["etat"] == "termine"
    assert abs(fini["resultat"]["propositions"][0]["dplus_m"] - 80) <= 8


def test_demandes_refusees(client):
    assert client.post("/api/calculs", json=demande(distance_km=100)).status_code == 422
    loin = {"latitude": 0.0, "longitude": 0.0, "distance_km": 5}
    assert client.post("/api/calculs", json=loin).status_code == 422
    assert client.get("/api/calculs/inconnu").status_code == 404
