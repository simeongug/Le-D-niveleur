# Le Déniveleur

Générateur de boucles trail qui cherche le **maximum de dénivelé positif (D+)**, ou un
D+ choisi, pour une distance donnée — et sort un fichier GPX prêt à charger dans une
montre ou dans Strava.

## L'objectif

Depuis un point de départ (par défaut la rue Dailly à Saint-Cloud), proposer en moins
d'une minute une boucle de 20 à 22 km avec **au moins 550 m de D+**, sans repasser deux
fois au même endroit.

La référence à battre est un tracé fait à la main : 25,1 km pour 579 m de D+.

## Où en est le projet

| Étape | Contenu | État |
|---|---|---|
| 1 | Cadrage : repo, vérifications automatiques, décisions d'architecture | ✅ |
| 2 | Données : chemins OpenStreetMap + altitude IGN pour l'Île-de-France | à venir |
| 3 | Moteur en ligne de commande : boucle à D+ maximal, export GPX | à venir |
| 4 | D+ cible et estimation du temps de parcours | à venir |
| 5 | API + interface web utilisable sur téléphone | à venir |
| 6 | Intervalles en côte | à venir |
| 7 | Préférences avancées (pente, escaliers, surface, portions en double) | à venir |
| 8 | Options : connexion Strava, autres régions, hébergement public | à venir |

Le détail est dans [docs/feuille-de-route.md](docs/feuille-de-route.md).

## Essayer

Il faut Python 3.11 ou plus récent.

```bash
git clone https://github.com/simeongug/Le-D-niveleur.git
cd Le-D-niveleur
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

deniveleur --version     # affiche la version
deniveleur regions       # liste les régions couvertes
```

À ce stade la commande ne génère pas encore d'itinéraire : elle prouve seulement que
l'installation fonctionne.

## Vérifications automatiques

À chaque modification envoyée sur GitHub, deux contrôles tournent tout seuls :

- **ruff** vérifie le style du code ;
- **pytest** lance les tests.

Pour les lancer à la main :

```bash
ruff check . && ruff format --check .
pytest
```

## Organisation du repo

```
src/deniveleur/     le code de l'application
tests/              les tests automatiques
docs/decisions/     les choix d'architecture et leurs raisons
docs/               la feuille de route
.github/workflows/  les vérifications automatiques
```

## Décisions d'architecture

1. [Python comme langage](docs/decisions/0001-langage-python.md)
2. [Un réseau de chemins préparé à l'avance](docs/decisions/0002-reseau-prepare-a-l-avance.md)
3. [Un moteur indépendant de l'interface et des régions](docs/decisions/0003-moteur-independant.md)

## Données

- Chemins : © les contributeurs d'[OpenStreetMap](https://www.openstreetmap.org/copyright), licence ODbL.
- Altitude : IGN, RGE ALTI®, Licence Ouverte Etalab 2.0.

Le projet n'utilise pas la carte de chaleur de Strava.
