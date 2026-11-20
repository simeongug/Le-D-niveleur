"""Estimation du temps de parcours (version simple, à affiner avec Strava plus tard)."""

from typing import Any


def kilometres_effort(distance_m: float, dplus_m: float, reglages: dict[str, Any]) -> float:
    """Distance « à plat équivalente » : chaque tranche de D+ ajoute un kilomètre."""
    return distance_m / 1000 + dplus_m / reglages["dplus_par_km_effort_m"]


def estimer_s(
    distance_m: float,
    dplus_m: float,
    reglages: dict[str, Any],
    allure_s_par_km: float | None = None,
) -> float:
    """Temps estimé en secondes pour une allure à plat donnée (secondes par km)."""
    allure = reglages["allure_plat_s_par_km"] if allure_s_par_km is None else allure_s_par_km
    return kilometres_effort(distance_m, dplus_m, reglages) * allure


def formater_precis(secondes: float) -> str:
    """4 min 05 (pour des durées courtes, à la seconde près)."""
    minutes, secondes = divmod(round(secondes), 60)
    return f"{minutes} min {secondes:02d}"


def formater(secondes: float) -> str:
    """1 h 05, 45 min…"""
    minutes = round(secondes / 60)
    heures, minutes = divmod(minutes, 60)
    return f"{heures} h {minutes:02d}" if heures else f"{minutes} min"
