# 4. Altitude à 2 m et réseau enregistré en tableaux

**Date :** 14 novembre 2026 — **État :** retenue

## Le besoin

L'étape 2 doit récupérer l'altitude IGN et enregistrer le réseau de chemins. La
décision n° 2 avait laissé le format du fichier ouvert « une fois les volumes mesurés ».

## Altitude : comment la récupérer

| Option | Pour | Contre |
|---|---|---|
| **Service en ligne de l'IGN (Géoplateforme), par dalles de 2 km, pixel de 2 m** | On ne télécharge que la zone utile (144 Mo pour 12 km × 12 km) ; une simple adresse web par dalle ; 16 s de téléchargement | L'IGN recalcule les pixels de 1 m vers 2 m : très légère perte de finesse |
| Même service, pixel de 1 m (la finesse d'origine) | Le plus précis | 4 fois plus lourd, sans gain visible sur des chemins de 2 à 3 m de large |
| Archives départementales complètes du RGE ALTI | Données d'origine, sans recalcul | Plusieurs Go par département, format à convertir, site de téléchargement distinct |

**Choix :** le service en ligne, pixel de 2 m. La valeur se change dans
`parametres.toml` (`resolution_m`) si le terrain montre qu'il faut plus fin.

## Réseau : comment l'enregistrer

| Option | Pour | Contre |
|---|---|---|
| **Tableaux de nombres compressés (`reseau.npz`) + une petite fiche texte (`reseau.json`)** | 21 Mo pour la zone ; chargé en moins d'une seconde ; aucun outil supplémentaire | Format propre au projet |
| Base de données cartographique (SpatiaLite) | Interrogeable avec des outils standards | Plus lent à charger, installation plus lourde |
| Format d'échange de graphes (GraphML) | Lisible par d'autres logiciels | Très volumineux et lent pour 110 000 tronçons |

**Choix :** les tableaux compressés. Le moteur a besoin de tout le réseau en mémoire,
pas de requêtes.

## Ce que ça implique

- Volumes mesurés sur la zone Saint-Cloud / Meudon : 110 236 tronçons, 3 984 km de
  voies, réseau construit en 26 s.
- Pour l'Île-de-France entière (étape 8), il faudra traiter l'altitude par morceaux :
  aujourd'hui toute la zone est chargée d'un bloc en mémoire.
