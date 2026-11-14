import pytest

from deniveleur import __version__
from deniveleur.cli import main


def test_version_affiche_le_numero(capsys):
    with pytest.raises(SystemExit) as sortie:
        main(["--version"])
    assert sortie.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_regions_liste_l_ile_de_france(capsys):
    assert main(["regions"]) == 0
    affichage = capsys.readouterr().out
    assert "ile-de-france" in affichage
    assert "par défaut" in affichage


def test_sans_commande_affiche_l_aide(capsys):
    assert main([]) == 0
    assert "deniveleur" in capsys.readouterr().out
