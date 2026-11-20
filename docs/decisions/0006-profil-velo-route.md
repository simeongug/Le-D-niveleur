# 6. Un profil « vélo de route » à côté de la course à pied

**Date :** 20 novembre 2026 — **État :** première partie faite (réglages et filtres), le
reste à valider sur les vraies données

## Le besoin

Faire la même chose à vélo de route : des boucles de 50 à 80 km à D+ maximal ou ciblé,
des répétitions de côte, des fichiers GPX et FIT pour le compteur ou la montre.

## Ce qui change par rapport à la course

| Sujet | Course | Vélo de route |
|---|---|---|
| Voies autorisées | sentiers, escaliers, voies piétonnes | routes, pistes cyclables ; ni sentiers, ni escaliers, ni grands axes |
| Revêtement | tout | dur uniquement (pas de pavés ni de gravier) |
| Droit de passage | étiquette `foot` | étiquette `bicycle` |
| Taille de la zone | 12 km × 12 km | 56 km × 52 km (Rambouillet à Paris, Chevreuse à Saint-Germain) |
| Altitude | pixels de 2 m | pixels de 10 m (l'écart suffit pour des routes) |
| Pente maximale « plausible » | 45 % | 25 % |
| Temps estimé | allure à plat 6:00/km, 100 m de D+ ≈ 1 km | 30 km/h à plat, 50 m de D+ ≈ 1 km |

## Décision

Un **profil** est un jeu de réglages qui ne redit que ce qui change
(`[profils.velo-route.*]` dans `parametres.toml`). Une **zone** désigne son profil. Le
moteur ne change pas : il reçoit le réseau et les réglages de la zone choisie. Le réseau
de la course reste intact et séparé de celui du vélo.

## Ce qui n'est pas fait

- Aucun test sur les vraies données : les valeurs du profil (tailles de cases, longueur
  des liaisons, temps de recherche) sont des estimations à régler après un premier essai.
- Le site ne propose pas encore de choisir entre course et vélo : il sert une seule zone
  à la fois (`deniveleur site --zone chevreuse-velo --port 8001`).
- Rien n'évite encore les routes passantes : seuls les grands axes sont écartés.
- Gravel et VTT : un autre profil, à écrire après celui-ci.

## Risques connus

La zone fait environ 2 900 km² : le réseau peut dépasser plusieurs centaines de milliers
de tronçons. La préparation de chaque calcul (graphe autour du départ) risque d'être
longue sur le serveur gratuit ; si c'est le cas, on réduira le rayon de recherche ou on
gardera le graphe en mémoire d'un calcul à l'autre.
