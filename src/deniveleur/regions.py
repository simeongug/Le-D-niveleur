"""Régions couvertes par l'application.

Une région est une simple fiche de configuration : ajouter une région ne doit
jamais demander de toucher au moteur (voir docs/decisions/0003).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Zone géographique pour laquelle on prépare un réseau de chemins."""

    identifiant: str
    nom: str
    # Emprise : (longitude ouest, latitude sud, longitude est, latitude nord), en degrés.
    emprise: tuple[float, float, float, float]

    def contient(self, longitude: float, latitude: float) -> bool:
        ouest, sud, est, nord = self.emprise
        return ouest <= longitude <= est and sud <= latitude <= nord


REGIONS: dict[str, Region] = {
    "ile-de-france": Region(
        identifiant="ile-de-france",
        nom="Île-de-France",
        emprise=(1.44, 48.12, 3.56, 49.25),
    ),
}

REGION_PAR_DEFAUT = "ile-de-france"
