"""Conversions de coordonnées.

On travaille en Lambert-93 (EPSG:2154), la projection officielle française :
les coordonnées y sont en mètres, ce qui rend les distances immédiates.
"""

from functools import cache

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer

Tableau = NDArray[np.float64]
Emprise = tuple[float, float, float, float]  # ouest, sud, est, nord


@cache
def _vers_l93() -> Transformer:
    return Transformer.from_crs(4326, 2154, always_xy=True)


@cache
def _vers_gps() -> Transformer:
    return Transformer.from_crs(2154, 4326, always_xy=True)


def gps_vers_l93(longitudes: Tableau, latitudes: Tableau) -> tuple[Tableau, Tableau]:
    x, y = _vers_l93().transform(np.asarray(longitudes), np.asarray(latitudes))
    return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)


def l93_vers_gps(x: Tableau, y: Tableau) -> tuple[Tableau, Tableau]:
    longitudes, latitudes = _vers_gps().transform(np.asarray(x), np.asarray(y))
    return np.asarray(longitudes, dtype=np.float64), np.asarray(latitudes, dtype=np.float64)


def emprise_gps(emprise_l93: Emprise, marge_m: float = 0.0) -> Emprise:
    """Rectangle en degrés qui englobe l'emprise Lambert-93 (plus une marge)."""
    ouest, sud, est, nord = emprise_l93
    xs = np.array([ouest, est, est, ouest]) + np.array([-1, 1, 1, -1]) * marge_m
    ys = np.array([sud, sud, nord, nord]) + np.array([-1, -1, 1, 1]) * marge_m
    longitudes, latitudes = l93_vers_gps(xs, ys)
    return (
        float(longitudes.min()),
        float(latitudes.min()),
        float(longitudes.max()),
        float(latitudes.max()),
    )
