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

## 4. D+ cible et modèle de temps ✅ (en partie)

Viser un D+ précis plutôt que le maximum, et estimer le temps de parcours.
**Résultat :** sur 20 km depuis la rue Dailly, 200, 300, 400 et 500 m visés donnent
200, 301, 400 et 501 m (critère : moins de 10 % d'écart). Le temps est estimé avec la
règle « 100 m de D+ ≈ 1 km de plat » et une allure à plat réglable.
**Reste à faire :** le mode « temps cible » (donner une durée plutôt qu'une distance),
et l'allure calibrée sur les sorties Strava (étape 8).

## 5. Site web utilisable sur téléphone ✅

Une page web : carte, réglages, propositions, profil, téléchargement du GPX. Installation
automatique sur un serveur gratuit Oracle Cloud, mise à jour automatique depuis GitHub.
**Résultat :** `deniveleur site` en local ; mise en ligne décrite dans
[deploiement.md](deploiement.md).
**Reste à vérifier par Siméon :** l'usage depuis son téléphone une fois en ligne.

## 6. Intervalles en côte ✅ (en partie)

Une séance : échauffement jusqu'au pied d'une côte, N montées avec redescente par le même
chemin, retour au départ par un autre chemin si possible. L'appli choisit la côte (la plus
riche en D+ qui tient dans la distance demandée) ; on fixe seulement le nombre de
répétitions. Site : « Séance d'intervalles » ; ligne de commande : `--repetitions 6`.
**Résultat :** sur le terrain d'essai, 3 montées de 800 m donnent 5,2 km et 120 m de D+, en
moins d'une seconde ; trop de répétitions pour la distance donnent « aucune proposition ».
**Reste à faire :** choisir la côte soi-même en touchant la carte ; compléter un parcours
trop court avec un détour ; export FIT (parcours + entraînement) pour la montre ; essai sur
les vraies données.

## 7. Préférences avancées ✅ (en partie)

Un interrupteur oui/non pour chacune, dans le site (`Contraintes`) et en ligne de commande :
escaliers (`--sans-escaliers`), part de sentier (`--chemin-min`), pente maximale
(`--pente-max 25`), pas de bitume (`--sans-bitume`), repasser par le même chemin
(`--doublons`). Les demi-tours restent toujours interdits.
**Résultat :** tests sur le terrain d'essai ; si les préférences ne laissent aucune
boucle, le message le dit clairement.
**Reste à vérifier par Siméon :** essayer chaque interrupteur sur les vraies données depuis
la rue Dailly (je n'ai pas pu télécharger OpenStreetMap / IGN depuis mon environnement) ;
je compléterai alors `benchmarks/rapport.md` avec les chiffres réels.

## 8. Options

Connexion Strava, autres régions, hébergement public (budget : 0 €).

## 9. Vélo de route (en cours)

Même fonctionnement à vélo de route, pour des sorties de 50 à 80 km autour de Saint-Cloud
(voir [la décision 6](decisions/0006-profil-velo-route.md)).
**Fait :** profil `velo-route` (voies, revêtement, pentes, temps estimé), zone
`chevreuse-velo`.
**Reste à faire :** télécharger et construire les données de la zone sur le serveur
(`deniveleur donnees tout --zone chevreuse-velo`), un premier essai réel et le réglage du
moteur, puis un choix course / vélo dans le site.

