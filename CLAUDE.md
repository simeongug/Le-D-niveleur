# Le Déniveleur — consignes pour Claude

Deux personnes travaillent sur ce repo, chacune avec son propre Claude : **Siméon**
(propriétaire du repo) et **Antoine**. Ce fichier est la **seule source des règles** pour
les deux. Aucune copie locale : pour changer une règle, on ouvre une PR sur ce fichier,
que l'autre lit avant la fusion.

On écrit en français : code, commentaires, messages de commit, PR, documentation.
Expliquer simplement, sans jargon inutile : ni Siméon ni Antoine ne relisent le code
ligne à ligne.

## Les règles

1. **Avant de coder** : `git pull`, lire `docs/journal/` et `git branch -r`, regarder
   les PR ouvertes, puis **annoncer sa tâche** (issue ou PR brouillon) pour ne pas
   travailler à deux sur la même chose.
2. **Jamais de push sur `main` ni sur `production`** : toujours une branche
   `prenom/sujet` (ex. `simeon/export-fit`), partie du dernier `main`, et une PR.
3. **Chaque PR remplit le modèle** (`.github/pull_request_template.md`) et **ajoute son
   entrée** dans `docs/journal/<prenom>.md`, dans la même PR.
4. **Signaler en tête de PR tout ce qui touche le serveur** (rubrique « Impact
   serveur ») :
   - `src/deniveleur/config/parametres.toml`, `reseau.py`, `profil.py`, `geo.py`,
     `src/deniveleur/donnees/` : le serveur **reconstruit le réseau** (plusieurs minutes,
     beaucoup de mémoire) ;
   - `deploiement/` : change la façon dont le serveur se met à jour ;
   - une nouvelle dépendance dans `pyproject.toml` : elle doit s'installer sur le
     serveur (Ubuntu 24.04, processeur Arm).
5. **Fusionner seulement avec la CI verte**, et **ne jamais dire qu'une chose marche sans
   l'avoir lancée**. Pas de relecture obligatoire : quand la CI est verte, l'auteur
   fusionne lui-même.
6. **Mettre à jour ce fichier dans la même PR** quand l'état du projet change
   (nouvelle commande, nouvelle zone, changement de déploiement…).

GitHub fait respecter l'essentiel : `main` est protégée, on ne peut y fusionner qu'une
PR dont les vérifications sont vertes, et personne ne peut contourner la règle.

## Du code à la production

```
branche prenom/sujet → PR → CI verte → fusion dans main
   → CI verte sur main → l'action « Production » avance la branche production
   → le serveur l'installe dans les 15 min, vérifie que le site répond
   → sinon il revient à la version d'avant (code et réseau) et refuse cette version
   → l'action « Surveillance du site » le signale dans l'issue « Journal des changements »
```

En cas d'alerte : on corrige **sur `main`** par une nouvelle PR. Le serveur ignore la
version refusée et installe la suivante dès que `production` avance.

- Site : https://89-168-50-77.sslip.io/ — `/sante` donne l'état et la version installée.
- Serveur : Oracle Cloud, offre gratuite (2 processeurs Arm, 12 Go). Budget : **0 €**.
  Détails et dépannage : [docs/deploiement.md](docs/deploiement.md).

## Le projet en bref

Générateur de boucles trail (et bientôt vélo de route) à D+ maximal ou visé, avec export
GPX et FIT. Python 3.11+, données OpenStreetMap + altitude IGN, réseau préparé à l'avance
puis moteur de recherche de boucles, site FastAPI pensé pour le téléphone.

| Où | Quoi |
|---|---|
| `src/deniveleur/config/parametres.toml` | tous les réglages (zones, moteur, site) |
| `src/deniveleur/donnees/` | téléchargement OSM et altitude |
| `src/deniveleur/reseau.py` | construction du réseau |
| `src/deniveleur/moteur/` | recherche des boucles et des côtes |
| `src/deniveleur/site/` | API et page web |
| `deploiement/` | installation et mise à jour du serveur |
| `docs/feuille-de-route.md` | étapes du projet et leur état |
| `docs/decisions/` | décisions d'architecture |
| `docs/journal/` | journal de chacun (5 lignes par PR) |

Zones : `ouest-parisien` (celle du site), `saint-cloud-meudon`, `chevreuse-velo`
(vélo de route, en préparation).

## Commandes

```bash
pip install -e ".[dev]"          # installer
ruff check . && ruff format --check .   # style (comme la CI)
pytest                           # tests (comme la CI)
deniveleur donnees tout          # télécharger et construire le réseau de la zone
deniveleur site                  # site sur http://localhost:8000
```

## Le journal

Chaque PR ajoute **en haut** de `docs/journal/<prenom>.md` une entrée de 5 lignes au
plus : date, numéro et titre de la PR, ce qui change, l'impact serveur, ce qui reste à
faire. Ce sont nos Claude qui l'écrivent.
