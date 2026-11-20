"""Export au format FIT (montres Garmin, Coros…).

Deux fichiers, parce qu'un FIT ne peut être qu'une chose à la fois :

- le **parcours** (`parcours`) : la trace à suivre avec la montre, plus un repère au
  pied et au sommet de chaque montée principale ;
- l'**entraînement** (`entrainement`) : la structure d'une séance d'intervalles
  (échauffement, N × [montée, redescente], retour), avec des étapes à distance fixe.
"""

import time

import numpy as np
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.course_message import CourseMessage
from fit_tool.profile.messages.course_point_message import CoursePointMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    CoursePoint,
    Event,
    EventType,
    FileType,
    Intensity,
    Manufacturer,
    Sport,
    WorkoutStepDuration,
    WorkoutStepTarget,
)

from deniveleur.moteur.itineraire import Boucle

PAS_MIN_M = 10.0  # on n'écrit pas plus d'un point tous les 10 m
POINTS_MAX = 4000
ALLURE_S_PAR_KM = 360  # sert seulement à dater les points (la montre n'en tient pas compte)
NOM_MAX = 15  # longueur max d'un nom de repère sur la montre


def _en_tete(type_fichier: FileType, maintenant_ms: int) -> FileIdMessage:
    en_tete = FileIdMessage()
    en_tete.type = type_fichier
    en_tete.manufacturer = Manufacturer.DEVELOPMENT.value
    en_tete.product = 0
    en_tete.time_created = maintenant_ms
    en_tete.serial_number = 0x44454E49  # « DENI »
    return en_tete


def _indices(distances: np.ndarray) -> np.ndarray:
    """Positions des points gardés : un tous les `PAS_MIN_M` (au moins), toujours les deux bouts."""
    pas = max(PAS_MIN_M, float(distances[-1]) / POINTS_MAX)
    gardes = [0]
    for i in range(1, len(distances) - 1):
        if distances[i] - distances[gardes[-1]] >= pas:
            gardes.append(i)
    gardes.append(len(distances) - 1)
    return np.asarray(gardes)


def parcours(boucle: Boucle, nom: str) -> bytes:
    """Fichier FIT « parcours » : trace, altitude, et repères de montées."""
    debut_ms = int(time.time() * 1000)
    constructeur = FitFileBuilder(auto_define=True, min_string_size=50)
    constructeur.add(_en_tete(FileType.COURSE, debut_ms))

    cours = CourseMessage()
    cours.course_name = nom[:31]
    cours.sport = Sport.RUNNING
    constructeur.add(cours)

    gardes = _indices(boucle.distances)
    duree_ms = lambda distance_m: int(distance_m / 1000 * ALLURE_S_PAR_KM * 1000)  # noqa: E731
    fin_ms = debut_ms + duree_ms(float(boucle.distances[-1]))

    tour = LapMessage()
    tour.timestamp = fin_ms
    tour.start_time = debut_ms
    tour.total_elapsed_time = (fin_ms - debut_ms) / 1000
    tour.total_timer_time = (fin_ms - debut_ms) / 1000
    tour.total_distance = float(boucle.distances[-1])
    tour.start_position_lat = float(boucle.latitudes[0])
    tour.start_position_long = float(boucle.longitudes[0])
    tour.end_position_lat = float(boucle.latitudes[-1])
    tour.end_position_long = float(boucle.longitudes[-1])
    constructeur.add(tour)

    demarrage = EventMessage()
    demarrage.event = Event.TIMER
    demarrage.event_type = EventType.START
    demarrage.timestamp = debut_ms
    constructeur.add(demarrage)

    for i in gardes:
        point = RecordMessage()
        point.position_lat = float(boucle.latitudes[i])
        point.position_long = float(boucle.longitudes[i])
        point.altitude = float(boucle.altitudes[i])
        point.distance = float(boucle.distances[i])
        point.timestamp = debut_ms + duree_ms(float(boucle.distances[i]))
        constructeur.add(point)

    arret = EventMessage()
    arret.event = Event.TIMER
    arret.event_type = EventType.STOP_ALL
    arret.timestamp = fin_ms
    constructeur.add(arret)

    # Repères : pied (« Bas ») et sommet (« Haut ») de chaque montée, 100 au plus.
    reperes = []
    for montee in boucle.montees:
        reperes.append((montee.debut_m, montee.bas, CoursePoint.VALLEY, f"Bas {montee.numero}"))
        reperes.append(
            (
                montee.debut_m + montee.longueur_m,
                montee.haut,
                CoursePoint.SUMMIT,
                f"Haut {montee.numero} +{montee.denivele_m:.0f}",
            )
        )
    for distance, (longitude, latitude, _), type_repere, titre in reperes[:100]:
        repere = CoursePointMessage()
        repere.timestamp = debut_ms + duree_ms(distance)
        repere.position_lat = latitude
        repere.position_long = longitude
        repere.distance = distance
        repere.type = type_repere
        repere.course_point_name = titre[:NOM_MAX]
        constructeur.add(repere)
    return constructeur.build().to_bytes()


def _etape(
    numero: int, nom: str, intensite: Intensity, distance_m: float | None
) -> WorkoutStepMessage:
    etape = WorkoutStepMessage()
    etape.message_index = numero
    etape.workout_step_name = nom
    etape.intensity = intensite
    etape.target_type = WorkoutStepTarget.OPEN
    if distance_m is None:
        etape.duration_type = WorkoutStepDuration.OPEN
    else:
        etape.duration_type = WorkoutStepDuration.DISTANCE
        etape.duration_distance = round(distance_m)
    return etape


def entrainement(boucle: Boucle, nom: str) -> bytes:
    """Fichier FIT « entraînement » d'une séance d'intervalles (une boucle avec `intervalles`)."""
    plan = boucle.intervalles
    if plan is None:
        raise ValueError("Cette proposition n'est pas une séance d'intervalles.")
    constructeur = FitFileBuilder(auto_define=True, min_string_size=50)
    constructeur.add(_en_tete(FileType.WORKOUT, int(time.time() * 1000)))

    etapes: list[WorkoutStepMessage] = [
        _etape(0, "Echauffement", Intensity.WARMUP, plan.echauffement_m),
        _etape(1, "Montee", Intensity.ACTIVE, plan.montee_m),
        _etape(2, "Redescente", Intensity.RECOVERY, plan.montee_m),
    ]
    repetition = WorkoutStepMessage()
    repetition.message_index = 3
    repetition.duration_type = WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT
    repetition.duration_step = 1  # on reprend à l'étape « Montée »
    repetition.target_repeat_steps = plan.repetitions
    etapes.append(repetition)
    etapes.append(_etape(4, "Retour", Intensity.COOLDOWN, plan.retour_m))

    seance = WorkoutMessage()
    seance.workout_name = nom[:15]
    seance.sport = Sport.RUNNING
    seance.num_valid_steps = len(etapes)
    constructeur.add(seance)
    for etape in etapes:
        constructeur.add(etape)
    return constructeur.build().to_bytes()
