# Journal d'Antoine

Une entrée par PR, la plus récente en haut, 5 lignes au plus : date, PR, ce qui change,
impact serveur, ce qui reste à faire.

## 22/11/2026 — Journal : entrées de #8, #13 et #18
- Ajoute ci-dessous les entrées des trois PR fusionnées avant la création des journaux (#20).
- Impact serveur : aucun. Reste : supprimer les branches `antoine/source-osm`, `carte-zone`, `test-pente`.

## 20/11/2026 — #18 Test : D+ d'un tracé dans la pente indépendant des arrondis
- `test_mesurer_un_trace_dans_la_pente` mesure avec un seuil de 1,8 m au lieu de 2 m : sur la
  pente d'essai, chaque marche tombait pile sur le seuil (18 m au lieu de 20 sur Windows).
- Test seul, moteur et réglages inchangés. Impact serveur : aucun.

## 20/11/2026 — #13 Carte : zone couverte dessinée et bande « bord de zone »
- Carte : extérieur de la zone grisé, départ hors zone refusé tout de suite, bande jaune
  « bord de zone » selon la distance choisie. `/api/infos` renvoie le contour de la zone.
- Le seuil 0.3 devient `[site] bord_alerte_part` dans `parametres.toml`.
- Impact serveur : `parametres.toml` change, le serveur reconstruit le réseau à la fusion.

## 20/11/2026 — #8 Données : source OSM de secours si Geofabrik ne répond pas
- `[osm] sources` : Geofabrik d'abord, OpenStreetMap France en secours (même extrait, empreinte
  vérifiée). Le manifeste note la source utilisée.
- Impact serveur : `parametres.toml` et `donnees/` changent, le serveur reconstruit le réseau à la fusion.
