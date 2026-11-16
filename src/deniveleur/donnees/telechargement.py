"""Téléchargements, empreintes de contrôle et manifeste des données.

Le manifeste (`data/manifeste.json`) note pour chaque fichier téléchargé d'où
il vient, quand, sa taille et son empreinte : c'est ce qui rend la préparation
des données reproductible et vérifiable.
"""

import hashlib
import http.client
import json
import logging
import shutil
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

journal = logging.getLogger(__name__)

AGENT = "deniveleur (https://github.com/simeongug/Le-D-niveleur)"
DELAI_S = 600
# Erreurs de réseau après lesquelles on réessaie (coupure, réponse tronquée…).
ERREURS_RESEAU = (urllib.error.URLError, OSError, http.client.HTTPException)


def ouvrir(url: str, suivre_redirections: bool = True) -> Any:
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
    if suivre_redirections:
        return urllib.request.urlopen(requete, timeout=DELAI_S)

    class SansRedirection(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args: Any, **kwargs: Any) -> None:
            return None

    return urllib.request.build_opener(SansRedirection).open(requete, timeout=DELAI_S)


def variantes(url: str) -> list[str]:
    """Adresses à essayer dans l'ordre : deux fois celle demandée, puis sa version http.

    Certains réseaux coupent le https vers Geofabrik. Le repli en http reste
    sûr parce que l'empreinte du fichier est vérifiée après coup.
    """
    if url.startswith("https://"):
        return [url, url, "http://" + url.removeprefix("https://")]
    return [url, url]


def lire(url: str) -> bytes:
    erreur: Exception | None = None
    for candidate in variantes(url):
        try:
            with ouvrir(candidate) as reponse:
                return bytes(reponse.read())
        except ERREURS_RESEAU as exc:
            erreur = exc
            journal.debug("Échec sur %s : %s", candidate, exc)
    raise ConnectionError(f"Téléchargement impossible : {url} ({erreur})")


def telecharger(url: str, destination: Path) -> str:
    """Télécharge `url` vers `destination` ; renvoie l'adresse qui a fonctionné."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    provisoire = destination.with_suffix(destination.suffix + ".partiel")
    erreur: Exception | None = None
    for candidate in variantes(url):
        try:
            with ouvrir(candidate) as reponse, provisoire.open("wb") as sortie:
                shutil.copyfileobj(reponse, sortie, length=1 << 20)
            provisoire.replace(destination)
            return candidate
        except ERREURS_RESEAU as exc:
            erreur = exc
            journal.debug("Échec sur %s : %s", candidate, exc)
    provisoire.unlink(missing_ok=True)
    raise ConnectionError(f"Téléchargement impossible : {url} ({erreur})")


def empreinte(chemin: Path, algorithme: str = "sha256") -> str:
    calcul = hashlib.new(algorithme)
    with chemin.open("rb") as fichier:
        while bloc := fichier.read(1 << 20):
            calcul.update(bloc)
    return calcul.hexdigest()


def maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def lire_manifeste(dossier: Path) -> dict[str, Any]:
    chemin = dossier / "manifeste.json"
    if chemin.exists():
        return dict(json.loads(chemin.read_text("utf-8")))
    return {}


def ecrire_manifeste(dossier: Path, manifeste: dict[str, Any]) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(manifeste, indent=2, ensure_ascii=False, sort_keys=True)
    (dossier / "manifeste.json").write_text(texte + "\n", "utf-8")
