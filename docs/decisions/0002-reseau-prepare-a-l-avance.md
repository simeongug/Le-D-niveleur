# 2. Un réseau de chemins préparé à l'avance

**Date :** 14 novembre 2026 — **État :** retenue

## Le besoin

Pour proposer une boucle, le moteur doit connaître tous les chemins autour du départ
et l'altitude le long de chacun.

## Les options

| Option | Pour | Contre |
|---|---|---|
| **Préparer une fois, par région, un fichier contenant le réseau de chemins avec ses altitudes** | Réponse rapide ; aucune dépendance à un service extérieur au moment de la demande ; hébergement à 0 € possible | Une étape de préparation à relancer pour rafraîchir les données |
| Interroger des services en ligne à chaque demande | Données toujours à jour, rien à stocker | Lent, quotas, panne si le service tombe ; l'objectif « moins d'une minute » devient fragile |
| Installer une base de données cartographique | Puissant, adapté à un pays entier | Lourd à installer et à héberger pour un projet à 0 € |

## Le choix

Préparer à l'avance. Une commande télécharge les chemins (OpenStreetMap) et l'altitude
(IGN RGE ALTI), les croise, et enregistre un fichier par région. Le moteur ne lit que
ce fichier.

## Ce que ça implique

- Les données téléchargées et les fichiers préparés ne sont jamais dans le repo
  (dossier `data/`, ignoré par git).
- Les chemins OpenStreetMap changent peu : un rafraîchissement de temps en temps suffit.
- Le format exact du fichier sera choisi à l'étape 2, une fois les volumes mesurés.
