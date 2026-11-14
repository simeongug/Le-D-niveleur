import numpy as np
import pytest

from deniveleur import profil


def test_densifier_garde_les_extremites_et_la_longueur():
    x, y, distances = profil.densifier(np.array([0.0, 100.0]), np.array([0.0, 0.0]), 5)
    assert len(x) == 21
    assert (x[0], x[-1]) == (0.0, 100.0)
    assert distances[-1] == pytest.approx(100.0)


def test_densifier_suit_les_virages():
    x, y, distances = profil.densifier(np.array([0.0, 30.0, 30.0]), np.array([0.0, 0.0, 40.0]), 5)
    assert distances[-1] == pytest.approx(70.0)
    assert (x[-1], y[-1]) == (30.0, 40.0)


def test_lisser_conserve_les_altitudes_des_extremites():
    hasard = np.random.default_rng(1)
    z = np.linspace(50, 80, 60) + hasard.normal(0, 1, 60)
    lisse = profil.lisser(z, 5, 30)
    assert lisse[0] == pytest.approx(z[0])
    assert lisse[-1] == pytest.approx(z[-1])
    assert np.abs(np.diff(lisse)).sum() < np.abs(np.diff(z)).sum()


def test_lisser_ne_deforme_pas_une_pente_reguliere():
    z = np.linspace(10, 20, 21)
    assert profil.lisser(z, 5, 30) == pytest.approx(z)


def test_gains_bruts_montee_puis_descente():
    assert profil.gains_bruts(np.array([10.0, 30.0, 25.0, 40.0])) == (35.0, 5.0)


def test_hysteresis_ignore_le_bruit():
    # Une vraie montée de 20 m, parsemée d'oscillations de 1 m.
    z = np.linspace(100, 120, 41) + np.tile([0.5, -0.5], 21)[:41]
    brut, _ = profil.gains_bruts(z)
    filtre, descente = profil.gains_hysteresis(z, 2)
    assert brut >= 30
    assert filtre == pytest.approx(20, abs=1.5)
    assert descente == 0


def test_hysteresis_compte_montees_et_descentes_franches():
    z = np.array([0.0, 10.0, 0.0, 10.0])
    assert profil.gains_hysteresis(z, 2) == (20.0, 10.0)


def test_pente_max():
    distances = np.arange(0, 105, 5.0)
    z = np.where(distances < 50, 0, (distances - 50) * 0.2)
    assert profil.pente_max(z, distances) == pytest.approx(20)
