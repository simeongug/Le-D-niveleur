# Comment le moteur cherche une boucle

Le problème : depuis un point de départ, trouver une boucle d'une distance donnée qui
monte le plus possible, sans emprunter deux fois le même chemin et sans faire demi-tour.
C'est un problème trop vaste pour essayer toutes les boucles possibles (il y en a des
milliards). Le moteur fait donc comme un coureur qui prépare sa sortie à la main :
il enchaîne les côtes d'un versant à l'autre en tournant autour du départ, il essaie
plein de variantes, et il garde les meilleures.

Le code est dans `src/deniveleur/moteur/`, les réglages dans la section `[moteur]` de
`src/deniveleur/config/parametres.toml`.

## 1. Préparer le terrain de jeu (`graphe.py`)

À partir du réseau de l'étape 2, on garde seulement ce qui peut servir :

- les tronçons à moins de 35 % de la distance demandée du départ (7 km pour 21 km) ;
- sans les **culs-de-sac**, retirés de proche en proche : y entrer oblige à faire
  demi-tour ;
- sans les pentes invraisemblables (plus de 45 %, hors escaliers) : ce sont presque
  toujours des erreurs de la carte, comme un mur ou un passage souterrain mal décrit ;
- sans les escaliers, si on le demande.

Chaque tronçon devient deux sens de parcours, parce que le D+ dépend du sens. Le départ
est déplacé au carrefour utilisable le plus proche (en général à quelques mètres).

## 2. Repérer les hauts et les bas (`chemins.py`)

On découpe la zone en carrés de 250 m. Dans chaque carré qui a au moins 8 m de relief,
on note le carrefour le plus haut et le plus bas : ce sont les **points d'ancrage**,
environ 1 300 autour de Saint-Cloud. Ce sont les étapes possibles d'une boucle :
« monter de la Seine au haut du parc », « redescendre vers Sèvres »…

Entre une ancre et ses 40 voisines les plus proches, on calcule le plus court chemin
et on note sa longueur, sa montée, sa descente et sa part de sentier. Ces calculs sont
faits au fur et à mesure et gardés en mémoire.

## 3. Construire une boucle en zigzag (`recherche.py`)

Pour chaque boucle, on tire au hasard un **cercle-guide** : un centre, un rayon et un
sens de rotation. Puis on avance d'ancre en ancre :

1. Parmi les ancres voisines, on donne une note à chacune :
   - **+** le dénivelé du trajet pour y aller (monter ou descendre, les deux comptent :
     c'est le zigzag qui fait le D+) ;
   - **−** la longueur du trajet (il faut que chaque mètre rapporte) ;
   - **−** l'écart au cercle-guide, pour avancer autour du départ au lieu de s'éloigner ;
   - **+** en fin de parcours, ce qui rapproche du départ ;
   - **+** les mètres de sentier, si une part minimale de chemin est demandée ;
   - un peu de hasard, pour que deux boucles ne soient jamais identiques.
2. On prend la meilleure ancre dont le trajet est **acceptable** : pas de tronçon déjà
   pris, pas de demi-tour à la jonction, et pas plus de quelques mètres à côté d'un
   endroit déjà traversé (sinon deux trottoirs d'une même rue compteraient comme deux
   chemins différents).
3. Si plus rien n'est acceptable, on **annule la dernière étape** et on essaie autre
   chose.
4. Quand la distance restante ne laisse plus que de quoi rentrer, on **ferme la
   boucle** : plus court chemin vers le départ, en comptant les tronçons déjà
   empruntés (et ceux qui les longent) comme beaucoup plus longs qu'ils ne sont, pour
   que le retour les contourne. Si le retour n'est pas propre, on recule d'une étape et
   on réessaie.

Une construction prend environ 40 millièmes de seconde.

## 4. Explorer puis approfondir

Pendant 25 secondes, on construit des centaines de boucles :

- **les 40 premiers % du temps**, avec des cercles-guides tirés complètement au hasard,
  pour explorer toutes les directions ;
- **ensuite**, avec des variantes des cercles-guides qui ont donné les 6 meilleures
  boucles (direction et rayon légèrement modifiés), pour creuser les pistes
  prometteuses.

Sur trois tirages, cet approfondissement fait gagner environ 50 m de D+ par rapport à
l'exploration seule.

## 5. Mesurer et trier (`boucle.py`)

Chaque boucle construite est mesurée sur son profil complet, point par point (tous les
5 m) :

- **D+ et D−**, avec le même seuil de 2 m que pour la comparaison avec Strava ;
- **tronçons empruntés deux fois** : interdits ;
- **demi-tours** (virage de plus de 160°) : interdits ;
- **passages en double** : endroits où l'on repasse à moins de 15-30 m d'une autre
  partie du parcours, hors croisements. Tolérés jusqu'à 0,5 % de la distance (105 m
  pour 21 km) ;
- **longueur** : dans la tolérance (±5 % par défaut). Le moteur vise plutôt le haut
  de la fourchette, puisque plus de distance donne plus de D+.

Les boucles valides sont classées par D+. Quand on demande plusieurs propositions, on
écarte celles qui partagent plus de 60 % de leur parcours avec une proposition déjà
retenue, pour avoir de vrais choix différents.

## 6. Présenter le résultat (`itineraire.py`, `gpx.py`)

- **Montées principales** : toute portion qui gagne au moins 15 m sans redescendre de
  plus de 6 m. On donne leur nom de rue ou de chemin quand OpenStreetMap le connaît
  pour au moins 30 % de leur longueur.
- **GPX** : la trace avec l'altitude, plus un repère en bas et en haut de chaque
  montée principale.
- **Alertes** : passages en double, escaliers, horaires des parcs (pas encore
  vérifiés, voir étape 7).

## 7. Contraintes (`recherche.py`)

- **Type de voie** : « max de chemin » donne un petit bonus (0,03 m de D+ par mètre) à
  chaque mètre de sentier ou de piste, « max de route » le même bonus à chaque mètre
  de voie revêtue (escaliers exclus). Ce n'est pas une obligation : sur 21 km depuis la
  rue Dailly, la part de sentier passe d'environ 48 % à 61 % (max de chemin) ou 18 %
  (max de route), pour un D+ presque inchangé.
- **Escaliers** : « éviter » les retire du réseau avant la recherche.
- **Allers-retours acceptés** : les culs-de-sac sont gardés, et un tronçon peut être
  repris une fois dans chaque sens (au plus 20 % de la distance). Chaque mètre repris
  coûte 0,1 m de D+ dans la note, chaque demi-tour 15 m. La moitié du temps sert à
  chercher aussi des boucles strictes : on ne propose un aller-retour que s'il rapporte
  vraiment plus. En pratique, dans le secteur de Saint-Cloud, le gain est faible : les
  boucles strictes sont déjà très riches en D+.

## 8. Côtes pour intervalles (`cotes.py`)

But : trouver près du départ des montées qui durent environ le temps d'une répétition
(par exemple 4 minutes).

1. **Temps d'une montée** : même règle que pour les boucles (100 m de D+ ≈ 1 km de
   plat), avec une allure d'intervalle (4:30 /km par défaut). Une côte de 380 m à
   13 % (+50 m) compte comme 0,88 km de plat, soit environ 3 min 55 à 4:30 /km.
2. **Bas de côte possibles** : le carrefour le plus bas de chaque case de 150 m, et
   chaque carrefour plus bas que tous ses voisins, à moins de 3 km du départ par les
   chemins.
3. **Exploration** : depuis chaque bas, on avance en suivant d'abord ce qui monte le
   plus (3 continuations au plus à chaque carrefour), sans virage de plus de 120° et
   sans redescendre de plus de 4 m sous le point le plus haut atteint. On garde les
   montées dont le temps est à ±15 % de la durée demandée et la pente moyenne d'au
   moins 4 %.
4. **Tri** : note = dénivelé − 3 × descente intermédiaire − 0,5 m par mètre d'escalier
   − 5 m par km d'approche − 0,5 m par % d'écart à la durée. On propose les 5
   meilleures qui ne se recouvrent pas (moins de 30 % de longueur en commun).

Depuis la rue Dailly, pour 4 minutes : 5 côtes en 7 secondes, dont trois sentiers du
parc de Saint-Cloud (380 à 450 m, 11 à 13 % de moyenne).

## Limites connues

- Le moteur ne garantit pas la meilleure boucle possible : il en trouve une très bonne
  en un temps limité. Relancer avec `--graine 2`, `3`… donne d'autres boucles,
  parfois meilleures.
- Sans contrainte, il préfère la ville : les rues raides et les escaliers de Sèvres et
  de Saint-Cloud rapportent plus de D+ par kilomètre que la forêt. D'où les options
  `--chemin-min` et `--sans-escaliers`.
- Une part de chemin trop élevée peut être impossible à atteindre (70 % depuis la rue
  Dailly, par exemple) : le moteur propose alors ce qui s'en approche le plus et le
  signale.
- Une montée qui se termine par un long replat est comptée jusqu'au point le plus haut
  du replat : sa longueur est alors un peu surestimée et sa pente moyenne
  sous-estimée.
- Les horaires d'ouverture des parcs et les zones fermées ne sont pas pris en compte
  (étape 7).
