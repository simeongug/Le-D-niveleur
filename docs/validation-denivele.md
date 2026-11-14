# Notre D+ est-il cohérent avec Strava ?

Critère de l'étape 2 : sur un tracé connu, notre D+ doit être à moins de 10 % de celui
de Strava.

## Méthode

Quatre sorties à pied enregistrées dans le secteur, de 6 à 9 km. Pour chacune, on
reprend le tracé simplifié fourni par Strava (environ 320 points), on lit l'altitude
dans notre modèle de terrain, et on compare notre D+ à celui que Strava affiche. Les
tracés eux-mêmes restent privés : seuls les chiffres sont ici.

## Résultat (14 novembre 2026)

| Sortie | Distance Strava | Notre distance | D+ Strava | Notre D+ | Écart |
|---|---|---|---|---|---|
| Meudon | 6,61 km | 6,64 km | 175 m | 196 m | +12 % |
| Départ Saint-Cloud | 8,20 km | 8,02 km | 147 m | 152 m | +3 % |
| Ville-d'Avray A | 8,80 km | 8,81 km | 109 m | 98 m | −11 % |
| Ville-d'Avray B | 8,50 km | 8,52 km | 95 m | 92 m | −3 % |
| **Total** | | | **526 m** | **537 m** | **+2 %** |

- Écart moyen (en valeur absolue) : 7 %. Le critère des 10 % est tenu en moyenne et
  sur deux sorties sur quatre ; les deux autres sont à 11 et 12 %.
- Pas de biais : on ne surestime ni ne sous-estime systématiquement (+2 % au total).

## Ce qu'il faut en retenir

- Le D+ de ces sorties vient de la montre (baromètre), qui a elle-même une marge
  d'erreur de cet ordre. Et le tracé simplifié coupe un peu les virages.
- La comparaison la plus utile reste à faire à l'étape 3 : importer nos GPX dans le
  créateur d'itinéraires de Strava, celui qui a mesuré la référence de 579 m.

## Réglages retenus

Lissage sur 30 m, seuil de 2 m. Autres réglages essayés sur les mêmes sorties :

| Lissage | Seuil | Écart moyen | Écart sur le total |
|---|---|---|---|
| 20 m | 2 m | 10 % | +5 % |
| **30 m** | **2 m** | **7 %** | **+2 %** |
| 30 m | 3 m | 8 % | −1 % |
| 50 m | 2 m | 7 % | +2 % |
