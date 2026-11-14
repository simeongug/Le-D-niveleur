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

## 3. Moteur en ligne de commande

Depuis un point de départ et une distance, trouver la boucle au D+ maximal et l'écrire
en GPX.
**Résultat :** un GPX de 20-22 km à charger dans Strava.
**Critère de réussite :** au moins 550 m de D+, sans portion en double, en moins d'une
minute.

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
