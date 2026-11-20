# Les données

## D'où elles viennent

| Donnée | Source | Licence |
|---|---|---|
| Chemins | Extrait Île-de-France d'OpenStreetMap, publié chaque jour par Geofabrik (secours : OpenStreetMap France) | ODbL — © les contributeurs d'OpenStreetMap |
| Altitude | IGN, RGE ALTI®, via la Géoplateforme (`data.geopf.fr`) | Licence Ouverte Etalab 2.0 |
| Fond de la carte de contrôle | IGN, Plan IGN | Licence Ouverte Etalab 2.0 |

Rien n'est stocké dans le repo : tout se retélécharge dans le dossier `data/`.

## La zone couverte

La zone par défaut, `ouest-parisien`, couvre 26 km × 22 km : de Marnes-la-Coquette et
Meudon à l'ouest et au sud jusqu'à Montmartre et la Villette au nord-est, Mont Valérien
compris. Elle compte environ 600 000 tronçons ; construire le réseau prend 1 min 30 et
2,2 Go de mémoire, et le site en occupe ensuite environ 650 Mo. L'ancienne zone
`saint-cloud-meudon` (12 km × 12 km) reste disponible avec `--zone saint-cloud-meudon`.

## Les commandes

```bash
deniveleur donnees telecharger   # récupère les chemins et l'altitude
deniveleur donnees reseau        # construit le réseau de chemins
deniveleur donnees carte         # dessine la carte de contrôle (sorties/carte-pentes.png)
deniveleur donnees tout          # les trois à la suite

# Zoom de 2 km autour d'un point (latitude,longitude)
deniveleur donnees carte --centre 48.8428,2.2215 --rayon 2

# D+ d'un fichier GPX d'après notre modèle d'altitude
deniveleur denivele ma-sortie.gpx
```

## Reproductibilité

`data/manifeste.json` note pour chaque fichier téléchargé son adresse, sa date, sa
taille et son empreinte. L'extrait OpenStreetMap est vérifié contre l'empreinte publiée
par sa source avant d'être utilisé. `reseau.json` rappelle de quel extrait et avec
quels réglages le réseau a été construit.

## Ce qu'on garde d'OpenStreetMap

- **Gardé :** sentiers, chemins, pistes, escaliers, rues piétonnes, pistes cyclables,
  rues résidentielles et routes jusqu'aux nationales (qui ont des trottoirs).
- **Écarté :** autoroutes et voies rapides, voies privées ou interdites aux piétons
  (`access=private/no`, `foot=no`), allées privées de maisons.
- **Chemin ou bitume :** d'après le revêtement indiqué ; s'il manque, un sentier ou une
  piste compte comme chemin, le reste comme bitume.

La liste exacte est dans `src/deniveleur/config/parametres.toml`.

## Comment l'altitude est calculée

1. Chaque tronçon reçoit un point tous les 5 m.
2. L'altitude de chaque point est lue dans le modèle de terrain IGN (pixel de 2 m).
3. Le profil est lissé sur 30 m, sans toucher à l'altitude des carrefours.
4. Sur un **pont** ou dans un **tunnel**, le modèle de terrain voit l'eau ou la
   colline : l'altitude y est tracée en ligne droite entre les deux extrémités.
5. Le D+ d'un tracé complet ignore les variations de moins de 2 m (seuil
   « d'hystérésis »), comme le font les montres.

Chaque tronçon stocke son D+ dans les deux sens, sans seuil, pour que les D+ des
tronçons s'additionnent correctement. Le D+ annoncé pour une boucle sera recalculé sur
la boucle entière, avec le seuil.

## Limites connues

- 1,7 km de voies (hors escaliers) affichent une pente de plus de 40 % : murs de
  soutènement, passages souterrains non signalés dans OpenStreetMap. À traiter à
  l'étape 3 pour que le moteur ne s'y précipite pas.
- Les horaires des parcs et les zones fermées ne sont pas encore pris en compte
  (étape 7).
- La connexion sécurisée vers Geofabrik est coupée sur certains réseaux : le
  téléchargement bascule alors en connexion simple, et l'empreinte du fichier garantit
  qu'il n'a pas été altéré.
- Si Geofabrik ne répond pas du tout (le 20/11/2026, son adresse « latest » renvoyait
  une redirection sans fin), l'extrait est pris chez OpenStreetMap France, source de
  secours déclarée dans `parametres.toml` (`[osm] sources`). Le manifeste note la
  source réellement utilisée.
