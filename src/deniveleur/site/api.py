"""Le site : une petite API et la page web qui l'utilise.

    deniveleur site            # puis ouvrir http://localhost:8000

Routes :
    GET  /                          la page web
    GET  /api/infos                 zone couverte, valeurs par défaut
    POST /api/calculs               lance un calcul, renvoie son identifiant
    GET  /api/calculs/{id}          état du calcul et, une fois fini, les propositions
    GET  /api/calculs/{id}/gpx/{n}  fichier GPX de la proposition n
    GET  /api/calculs/{id}/fit/parcours/{n}      parcours FIT (montre)
    GET  /api/calculs/{id}/fit/entrainement/{n}  séance FIT (intervalles seulement)
"""

import logging
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from deniveleur import __version__, geo, parametres
from deniveleur.reseau import Reseau
from deniveleur.site.calculs import Demande, FileDeCalculs

journal = logging.getLogger(__name__)
STATIQUE = Path(str(resources.files("deniveleur.site").joinpath("statique")))


class DemandeWeb(BaseModel):
    """Ce que la page envoie pour lancer un calcul."""

    latitude: float
    longitude: float
    distance_km: float = Field(ge=3, le=40)
    tolerance_pct: float = Field(default=5, ge=1, le=15)
    dplus_cible: float | None = Field(default=None, ge=0, le=3000)
    chemin_min_pct: float = Field(default=0, ge=0, le=90)
    sans_escaliers: bool = False
    pente_max_pct: float | None = Field(default=None, ge=5, le=45)
    sans_bitume: bool = False
    doublons: bool = False
    repetitions: int | None = Field(default=None, ge=2, le=20)
    propositions: int = Field(default=3, ge=1, le=3)
    allure_s_par_km: float | None = Field(default=None, ge=150, le=1200)
    # Côtes pour intervalles (type « cotes ») : durée d'une répétition et distance
    # maximale entre le départ et le bas de la côte.
    type: Literal["boucle", "cotes"] = "boucle"
    duree_intervalle_s: float = Field(default=240, ge=30, le=900)
    rayon_cotes_km: float = Field(default=3, ge=0.5, le=8)


def creer_application(
    dossier_donnees: Path,
    zone: str,
    reglages: dict[str, Any] | None = None,
    emprise_l93: tuple[float, float, float, float] | None = None,
) -> FastAPI:
    """Construit le site. `reglages` et `emprise_l93` servent aux tests (terrain d'essai)."""
    if reglages is None:
        reglages = parametres.charger(
            parametres.profil_de(zone) if emprise_l93 is None else parametres.PROFIL_PAR_DEFAUT
        )
    fiche_zone = parametres.zone(zone) if emprise_l93 is None else {"nom": zone}
    emprise = emprise_l93 or tuple(fiche_zone["emprise_l93"])
    etat: dict[str, Any] = {}

    @asynccontextmanager
    async def cycle_de_vie(_: FastAPI):  # type: ignore[no-untyped-def]
        # Le réseau est chargé une seule fois, au démarrage.
        reseau = Reseau.charger(dossier_donnees / zone)
        etat["file"] = FileDeCalculs(reseau, reglages)
        journal.info("Réseau %s chargé : %d tronçons.", zone, reseau.nombre_troncons)
        yield

    app = FastAPI(title="Le Déniveleur", version=__version__, lifespan=cycle_de_vie)

    def file() -> FileDeCalculs:
        return etat["file"]  # type: ignore[no-any-return]

    @app.get("/api/infos")
    def infos() -> dict[str, Any]:
        ouest, sud, est, nord = emprise
        longitudes, latitudes = geo.l93_vers_gps(
            np.array([ouest, est, est, ouest]), np.array([sud, sud, nord, nord])
        )
        return {
            "version": __version__,
            "zone": fiche_zone["nom"],
            # Rectangle en degrés entièrement contenu dans la zone : ouest, sud, est, nord.
            "emprise": [
                float(longitudes[[0, 3]].max()),
                float(latitudes[[0, 1]].max()),
                float(longitudes[[1, 2]].min()),
                float(latitudes[[2, 3]].min()),
            ],
            "depart_defaut": reglages["site"]["depart_defaut"],
            "allure_defaut_s_par_km": reglages["temps"]["allure_plat_s_par_km"],
            "allure_intervalle_defaut_s_par_km": reglages["cotes"]["allure_s_par_km"],
            "budget_s": reglages["site"]["budget_s"],
            "paliers_pente": reglages["carte"]["paliers_pente"],
            "couleurs_pente": reglages["carte"]["couleurs"],
        }

    @app.post("/api/calculs", status_code=202)
    def lancer(demande: DemandeWeb) -> dict[str, Any]:
        x, y = geo.gps_vers_l93(np.array([demande.longitude]), np.array([demande.latitude]))
        rayon = demande.distance_km * 1000 * reglages["moteur"]["rayon_max_part"]
        ouest, sud, est, nord = emprise
        if not (ouest <= x[0] <= est and sud <= y[0] <= nord):
            raise HTTPException(422, "Le départ est en dehors de la zone couverte.")
        if min(x[0] - ouest, est - x[0], y[0] - sud, nord - y[0]) < rayon * 0.3:
            journal.info("Départ proche du bord de la zone : boucles possiblement limitées.")
        if demande.type == "cotes":
            allure = demande.allure_s_par_km or reglages["cotes"]["allure_s_par_km"]
        else:
            allure = demande.allure_s_par_km or reglages["temps"]["allure_plat_s_par_km"]
        try:
            calcul = file().soumettre(
                Demande(
                    latitude=demande.latitude,
                    longitude=demande.longitude,
                    distance_km=demande.distance_km,
                    tolerance_pct=demande.tolerance_pct,
                    dplus_cible=demande.dplus_cible,
                    chemin_min_pct=demande.chemin_min_pct,
                    sans_escaliers=demande.sans_escaliers,
                    pente_max_pct=demande.pente_max_pct,
                    sans_bitume=demande.sans_bitume,
                    doublons=demande.doublons,
                    repetitions=demande.repetitions,
                    type=demande.type,
                    duree_intervalle_s=demande.duree_intervalle_s,
                    rayon_cotes_m=demande.rayon_cotes_km * 1000,
                    propositions=demande.propositions,
                    allure_s_par_km=allure,
                )
            )
        except OverflowError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"id": calcul.identifiant}

    @app.get("/api/calculs/{identifiant}")
    def suivre(identifiant: str) -> dict[str, Any]:
        calcul = file().obtenir(identifiant)
        if calcul is None:
            raise HTTPException(404, "Calcul inconnu ou expiré.")
        return {
            "id": calcul.identifiant,
            "etat": calcul.etat,
            "position": file().position(calcul),
            "avancement": round(file().avancement(calcul), 3),
            "erreur": calcul.erreur,
            "resultat": calcul.resultat,
        }

    @app.get("/api/calculs/{identifiant}/gpx/{rang}")
    def telecharger(identifiant: str, rang: int) -> Response:
        calcul = file().obtenir(identifiant)
        if calcul is None or calcul.etat != "termine":
            raise HTTPException(404, "Calcul inconnu, expiré ou pas encore terminé.")
        if not 1 <= rang <= len(calcul.boucles):
            raise HTTPException(404, "Proposition inconnue.")
        nom, contenu = file().gpx(calcul, rang)
        return Response(
            contenu,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f'attachment; filename="{nom}"'},
        )

    @app.get("/api/calculs/{identifiant}/fit/{genre}/{rang}")
    def telecharger_fit(identifiant: str, genre: str, rang: int) -> Response:
        calcul = file().obtenir(identifiant)
        if calcul is None or calcul.etat != "termine":
            raise HTTPException(404, "Calcul inconnu, expiré ou pas encore terminé.")
        if not 1 <= rang <= len(calcul.boucles):
            raise HTTPException(404, "Proposition inconnue.")
        if genre not in ("parcours", "entrainement"):
            raise HTTPException(404, "Type de fichier inconnu : parcours ou entrainement.")
        if genre == "entrainement" and calcul.boucles[rang - 1].intervalles is None:
            raise HTTPException(404, "Pas de séance d'intervalles pour cette proposition.")
        nom, contenu = file().fit(calcul, rang, genre)
        return Response(
            contenu,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{nom}"'},
        )

    @app.get("/sante")
    def sante() -> dict[str, str]:
        return {"etat": "ok" if "file" in etat else "demarrage"}

    @app.get("/", include_in_schema=False)
    def accueil() -> FileResponse:
        return FileResponse(STATIQUE / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/statique", StaticFiles(directory=STATIQUE), name="statique")
    return app
