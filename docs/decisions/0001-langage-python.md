# 1. Python comme langage

**Date :** 14 novembre 2026 — **État :** retenue

## Le besoin

Lire des données cartographiques, calculer des altitudes, chercher des boucles dans un
réseau de chemins, puis exposer le tout dans une page web.

## Les options

| Option | Pour | Contre |
|---|---|---|
| **Python** | Les meilleurs outils de cartographie et de calcul existent déjà ; code lisible ; gratuit à héberger | Plus lent qu'un langage compilé sur les calculs lourds |
| JavaScript / TypeScript | Un seul langage pour le moteur et la page web | Peu d'outils pour l'altitude et les réseaux de chemins |
| Rust | Très rapide | Développement plus long, peu d'outils cartographiques prêts à l'emploi |

## Le choix

Python (3.11 ou plus récent).

La lenteur relative n'est pas un obstacle : le secteur visé représente quelques
dizaines de milliers de tronçons, et l'objectif est une réponse en moins d'une minute,
pas en une milliseconde. Si une partie du calcul devient trop lente, elle pourra être
accélérée seule, sans réécrire le reste.

## Ce que ça implique

- Le style est vérifié par ruff, les tests lancés par pytest.
- Les bibliothèques sont ajoutées une par une, quand une étape en a besoin.
