# Feuille de route

Chaque étape se termine par quelque chose de concret à lancer et à voir.

## 1. Cadrage ✅

Repo, README, vérifications automatiques, trois décisions d'architecture.
**Résultat :** une coche verte sur GitHub et la commande `deniveleur --version`.

## 2. Données ✅

Télécharger les chemins OpenStreetMap et l'altitude IGN (RGE ALTI), puis les assembler
en un réseau de chemins où chaque tronçon connaît sa longueur, sa montée et sa descente.
Fait pour le secteur Saint-Cloud / Sèvres / Meudon / Chaville / Ville-d'Avray ; le
reste de l'Île-de-France viendra à l'étape 8.
**Résultat :** la commande `deniveleur donnees tout`, une carte des chemins colorés par
la pente, et un D+ comparé à Strava sur quatre sorties (+2 % au total, voir
[validation-denivele.md](validation-denivele.md)).

## 3. Moteur en ligne de commande ✅

Depuis un point de départ et une distance, trouver la boucle au D+ maximal et l'écrire
en GPX.
**Résultat :** la commande `deniveleur boucle`, qui donne un ou plusieurs GPX avec leur
carte et leur profil. Depuis la rue Dailly : 759 m de D+ sur 21,5 km, ou environ 690 m
avec au moins 50 % de sentier et sans escaliers, en moins de 30 secondes. Six cas de
référence dans [benchmarks/rapport.md](../benchmarks/rapport.md).
**Reste à vérifier par Siméon :** importer un GPX dans Strava et comparer le D+ affiché.

## 4. D+ cible et modèle de temps

Viser un D+ précis plutôt que le maximum ; estimer la durée de la sortie.

## 5. API et interface web

Une page utilisable sur téléphone : choisir le départ, la distance, le D+, voir la
carte et le profil, télécharger le GPX.

## 6. Intervalles en côte

Insérer dans la boucle des répétitions sur une côte choisie.

## 7. Préférences avancées

Un interrupteur oui/non pour chacune : pente maximale, escaliers, type de surface,
portions en double.

## 8. Options

Connexion Strava, autres régions, hébergement public (budget : 0 €).
