from deniveleur.regions import REGION_PAR_DEFAUT, REGIONS


def test_la_region_par_defaut_existe():
    assert REGION_PAR_DEFAUT in REGIONS


def test_saint_cloud_est_en_ile_de_france():
    # Rue Dailly, Saint-Cloud : point de départ habituel.
    assert REGIONS["ile-de-france"].contient(longitude=2.219, latitude=48.846)


def test_lyon_n_est_pas_en_ile_de_france():
    assert not REGIONS["ile-de-france"].contient(longitude=4.835, latitude=45.764)


def test_les_emprises_sont_coherentes():
    for region in REGIONS.values():
        ouest, sud, est, nord = region.emprise
        assert ouest < est
        assert sud < nord
