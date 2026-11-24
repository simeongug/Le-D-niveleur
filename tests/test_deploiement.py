"""Tests du script de mise à jour du serveur, sur un faux serveur.

On rejoue deploiement/mettre-a-jour.sh dans un dossier temporaire : un dépôt « GitHub »
local, une copie du code, un faux site (curl), un faux systemctl et un faux deniveleur.
Le faux site répond « ok » sauf si le code contient le fichier `casse-site` ou si le
réseau a été construit avec le fichier `casse-reseau` présent.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "deploiement" / "mettre-a-jour.sh"
ZONE = "ouest-parisien"

pytestmark = pytest.mark.skipif(
    not (shutil.which("git") and shutil.which("flock") and shutil.which("bash")),
    reason="git, flock et bash nécessaires",
)

FAUX = {
    "sudo": 'shift 2; exec "$@"',
    "systemctl": 'echo "$*" >> "$JOURNAL_SYSTEMCTL"',
    "sleep": "exit 0",
    "curl": """
if [ -e "$CODE/casse-site" ] || grep -q casse "$DONNEES/ouest-parisien/reseau.npz" 2>/dev/null; then
  exit 22
fi
echo '{"etat":"ok"}'
""",
}
FAUX_VENV = {
    "pip": '[ -e "$CODE/casse-install" ] && exit 1; exit 0',
    "deniveleur": """
if [ "$2" = reseau ]; then
  mkdir -p "$DONNEES/ouest-parisien"
  if [ -e "$CODE/casse-reseau" ]; then contenu=casse; else contenu=bon; fi
  echo "$contenu-$(git -C "$CODE" rev-parse --short HEAD)" > "$DONNEES/ouest-parisien/reseau.npz"
  echo "{}" > "$DONNEES/ouest-parisien/reseau.json"
fi
""",
}


def ecrire_executable(chemin: Path, corps: str) -> None:
    chemin.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    chemin.chmod(0o755)


def git(*args: str, cwd: Path) -> str:
    resultat = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return resultat.stdout.strip()


class FauxServeur:
    def __init__(self, racine: Path):
        self.origine = racine / "origine.git"
        self.travail = racine / "travail"
        self.code = racine / "code"
        self.donnees = racine / "donnees"
        self.etat = racine / "etat"
        self.journal_systemctl = racine / "systemctl.log"
        faux = racine / "faux"
        for dossier in (self.travail, self.donnees, faux):
            dossier.mkdir()
        for nom, corps in FAUX.items():
            ecrire_executable(faux / nom, corps)
        git("init", "-q", "--bare", "-b", "main", str(self.origine), cwd=racine)
        git("init", "-q", "-b", "main", cwd=self.travail)
        git("remote", "add", "origin", str(self.origine), cwd=self.travail)
        self.commit("depart", {"README.md": "v1"})
        git("push", "-q", "origin", "main", cwd=self.travail)
        # Comme sur le serveur : clone peu profond qui ne suit que main.
        git(
            "clone",
            "-q",
            "--depth",
            "50",
            "--branch",
            "main",
            f"file://{self.origine}",
            str(self.code),
            cwd=racine,
        )
        (self.code / ".git" / "info" / "exclude").write_text(".venv/\n")
        (self.code / ".venv" / "bin").mkdir(parents=True)
        for nom, corps in FAUX_VENV.items():
            ecrire_executable(self.code / ".venv" / "bin" / nom, corps)
        self.env = {
            **os.environ,
            "PATH": f"{faux}:{os.environ['PATH']}",
            "CODE": str(self.code),
            "DONNEES": str(self.donnees),
            "ETAT": str(self.etat),
            "VERROU": str(racine / "verrou"),
            "ATTENTE_SANTE_S": "1",
            "JOURNAL_SYSTEMCTL": str(self.journal_systemctl),
        }

    def commit(self, message: str, ajouts: dict[str, str], retraits: tuple[str, ...] = ()) -> str:
        for nom, contenu in ajouts.items():
            chemin = self.travail / nom
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(contenu)
        for nom in retraits:
            (self.travail / nom).unlink()
        git("add", "-A", cwd=self.travail)
        git("commit", "-q", "-m", message, cwd=self.travail)
        return git("rev-parse", "HEAD", cwd=self.travail)

    def publier(self, message: str, ajouts: dict[str, str], retraits: tuple[str, ...] = ()) -> str:
        """Un commit sur main, aussitôt publié sur production (comme l'action Production)."""
        sha = self.commit(message, ajouts, retraits)
        git("push", "-q", "origin", "main", "main:production", cwd=self.travail)
        return sha

    def mettre_a_jour(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), *args], env=self.env, capture_output=True, text=True
        )

    def installe(self) -> str:
        return git("rev-parse", "HEAD", cwd=self.code)

    def etat_publie(self) -> dict[str, str]:
        return json.loads((self.donnees / "deploiement.json").read_text())

    def reseau(self) -> str:
        return (self.donnees / ZONE / "reseau.npz").read_text().strip()

    def redemarrages(self) -> int:
        if not self.journal_systemctl.exists():
            return 0
        return self.journal_systemctl.read_text().count("restart")


PARAMETRES = "src/deniveleur/config/parametres.toml"


def test_scenario_complet(tmp_path):
    s = FauxServeur(tmp_path)
    depart = s.installe()

    # 1. Pas encore de branche production : on suit main, et on construit le réseau manquant.
    r = s.mettre_a_jour()
    assert r.returncode == 0, r.stderr
    assert "suit main" in r.stderr
    assert s.reseau() == f"bon-{depart[:7]}"
    assert s.etat_publie()["resultat"] == "ok"
    assert s.redemarrages() == 1

    # 2. Rien de nouveau : on ne touche à rien.
    assert s.mettre_a_jour().returncode == 0
    assert s.redemarrages() == 1

    # 3. Une version ordinaire : installée, réseau inchangé.
    v2 = s.publier("ordinaire", {"a.txt": "a"})
    r = s.mettre_a_jour()
    assert r.returncode == 0, r.stderr
    assert s.installe() == v2
    assert s.reseau() == f"bon-{depart[:7]}"
    etat = s.etat_publie()
    assert (etat["resultat"], etat["commit"], etat["branche"], etat["refusee"]) == (
        "ok",
        v2,
        "production",
        "",
    )

    # 4. Une version qui casse le site : retour à v2, version refusée.
    v3 = s.publier("casse le site", {"casse-site": ""})
    r = s.mettre_a_jour()
    assert r.returncode == 1
    assert s.installe() == v2
    etat = s.etat_publie()
    assert (etat["resultat"], etat["commit"], etat["refusee"]) == ("retour-arriere", v2, v3)

    # 5. Tant que production reste sur la version refusée, on ne la réessaie pas.
    avant = s.redemarrages()
    r = s.mettre_a_jour()
    assert r.returncode == 0
    assert "déjà été refusée" in r.stderr
    assert s.installe() == v2
    assert s.redemarrages() == avant

    # 6. Une version qui reconstruit un réseau cassé : on remet l'ancien code ET l'ancien réseau.
    v4 = s.publier(
        "réseau cassé", {PARAMETRES: "x = 1", "casse-reseau": ""}, retraits=("casse-site",)
    )
    r = s.mettre_a_jour()
    assert r.returncode == 1
    assert s.installe() == v2
    assert s.reseau() == f"bon-{depart[:7]}"
    assert s.etat_publie()["refusee"] == v4

    # 7. La correction : installée, réseau reconstruit, plus rien de refusé.
    v5 = s.publier("correction", {PARAMETRES: "x = 2"}, retraits=("casse-reseau",))
    r = s.mettre_a_jour()
    assert r.returncode == 0, r.stderr
    assert s.installe() == v5
    assert s.reseau() == f"bon-{v5[:7]}"
    etat = s.etat_publie()
    assert (etat["resultat"], etat["commit"], etat["refusee"]) == ("ok", v5, "")
    assert not (s.etat / "refusee").exists()


def test_donnees_mensuelles_cassees_restaurees(tmp_path):
    """--donnees reconstruit le réseau ; s'il casse le site, l'ancien réseau revient."""
    s = FauxServeur(tmp_path)
    assert s.mettre_a_jour().returncode == 0
    bon = s.reseau()
    (s.code / "casse-reseau").write_text("")  # simule des données OSM du mois défectueuses
    r = s.mettre_a_jour("--donnees")
    assert r.returncode == 1
    assert s.reseau() == bon
    assert s.etat_publie()["resultat"] == "retour-arriere"
    assert s.etat_publie()["refusee"] == ""  # le code n'est pas en cause


def test_installation_impossible(tmp_path):
    """Si la nouvelle version ne s'installe pas, on reste sur l'ancienne."""
    s = FauxServeur(tmp_path)
    assert s.mettre_a_jour().returncode == 0
    v1 = s.installe()
    s.publier("dépendance introuvable", {"casse-install": ""})
    r = s.mettre_a_jour()
    assert r.returncode == 1
    # L'ancienne version est réinstallée (son pip passe, le fichier casse-install n'y est plus).
    assert s.installe() == v1
    assert s.etat_publie()["resultat"] == "retour-arriere"
