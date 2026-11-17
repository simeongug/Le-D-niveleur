# Rapport de benchmark du moteur

Généré le 2026-11-17 par `python benchmarks/lancer.py`, réseau construit à partir de `ile-de-france-261113.osm.pbf`.

| Cas | Distance | D+ | D+ par km | Chemin | Escaliers | En double | Durée | Plancher | État |
|---|---|---|---|---|---|---|---|---|---|
| Saint-Cloud, rue Dailly — 21 km | 21.5 km | 759 m | 35 m | 38 % | 891 m | 0 m | 27 s | 600 m | ✅ |
| Saint-Cloud, rue Dailly — 25 km | 25.9 km | 918 m | 35 m | 52 % | 913 m | 85 m | 27 s | 700 m | ✅ |
| Saint-Cloud, rue Dailly — 21 km, 50 % de chemin, sans escaliers | 21.8 km | 691 m | 32 m | 59 % | 0 m | 0 m | 27 s | 550 m | ✅ |
| Saint-Cloud, rue Dailly — 10 km | 10.3 km | 352 m | 34 m | 14 % | 616 m | 0 m | 25 s | 280 m | ✅ |
| Meudon, gare de Val Fleury — 15 km | 14.9 km | 584 m | 39 m | 14 % | 892 m | 0 m | 26 s | 400 m | ✅ |
| Chaville, gare Rive Droite — 15 km | 15.2 km | 641 m | 42 m | 43 % | 465 m | 0 m | 26 s | 400 m | ✅ |

Toutes les boucles respectent : retour au départ, longueur dans la tolérance (±5 %), aucun tronçon emprunté deux fois, aucun demi-tour.
« En double » : longueur qui passe à moins de 15-30 m d'une autre partie du parcours (hors croisements).

Notes :
- Saint-Cloud, rue Dailly — 21 km : Objectif du projet : au moins 550 m de D+ sur 20-22 km.
- Saint-Cloud, rue Dailly — 25 km : Référence tracée à la main dans Strava : 579 m de D+ sur 25,1 km.
