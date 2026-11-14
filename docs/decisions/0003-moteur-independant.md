# 3. Un moteur indépendant de l'interface et des régions

**Date :** 14 novembre 2026 — **État :** retenue

## Le besoin

Le projet commence par une ligne de commande en Île-de-France, puis doit devenir une
page web sur téléphone, peut-être étendue à d'autres régions.

## Les options

| Option | Pour | Contre |
|---|---|---|
| **Un moteur central, que la ligne de commande et la page web appellent toutes les deux ; les régions sont de simples fiches de configuration** | Un seul endroit où vit le calcul ; facile à tester ; ajouter une région ne touche pas au moteur | Demande un peu de discipline dès le départ |
| Tout écrire dans la ligne de commande, puis adapter pour le web | Plus rapide au début | Réécriture à l'étape 5, risque de deux versions du calcul |
| Tout écrire directement pour le web | Résultat visible plus tôt | Plus dur à tester et à mettre au point |

## Le choix

Trois couches :

1. **les données** — préparer et lire le réseau de chemins d'une région ;
2. **le moteur** — reçoit un réseau, un départ et des préférences, rend un itinéraire ;
   il ne sait ni d'où viennent les données ni qui l'appelle ;
3. **les interfaces** — ligne de commande d'abord, API et page web ensuite.

Une région est décrite par une fiche (nom, emprise géographique, sources de données).
L'Île-de-France est la première, dans `src/deniveleur/regions.py`.

## Ce que ça implique

- Les préférences (pente, escaliers, surface, portions en double) sont des paramètres
  du moteur, chacune activable ou non.
- La connexion à Strava, si elle arrive, sera une interface de plus, pas une
  modification du moteur.
