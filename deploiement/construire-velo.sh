#!/usr/bin/env bash
# Prépare les données du vélo de route (zone chevreuse-velo) SANS RISQUE pour le site.
# À lancer à la main sur le serveur, en root :
#
#   sudo bash /opt/deniveleur/deploiement/construire-velo.sh
#
# Garde-fous (tout reste gratuit : rien n'est créé chez Oracle, on utilise seulement le
# serveur existant) :
#   - refuse de démarrer s'il manque de la place sur le disque ;
#   - plafonne la mémoire de la construction (par défaut 65 % de la mémoire du serveur) : si la zone est
#     trop grosse, c'est la construction qui s'arrête, jamais le site ;
#   - mesure la mémoire maximale utilisée, puis celle que prendra le site avec ce réseau ;
#   - ne touche ni au réseau de la course à pied ni au service du site.
# Variables : LIMITE_MEMOIRE (65 % de la mémoire), DISQUE_MIN_GO (6), ZONE (chevreuse-velo).
set -euo pipefail

CODE=/opt/deniveleur
DONNEES=/var/lib/deniveleur
UTILISATEUR=deniveleur
ZONE="${ZONE:-chevreuse-velo}"
DISQUE_MIN_GO="${DISQUE_MIN_GO:-6}"
DENIVELEUR="$CODE/.venv/bin/deniveleur"

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé en root (sudo)." >&2
  exit 1
fi

echo "--- Contrôles avant de commencer"
# Par défaut, la construction ne peut pas dépasser 65 % de la mémoire du serveur.
LIMITE_MEMOIRE="${LIMITE_MEMOIRE:-$(awk '/MemTotal/ {print int($2 * 0.65 / 1024)}' /proc/meminfo)M}"
libre_go="$(df -BG --output=avail "$DONNEES" | tail -1 | tr -dc '0-9')"
dispo_mo="$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)"
total_mo="$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)"
echo "Disque libre : ${libre_go} Go (minimum demandé : ${DISQUE_MIN_GO} Go)"
echo "Mémoire : ${dispo_mo} Mo disponibles sur ${total_mo} Mo ; plafond de la construction : ${LIMITE_MEMOIRE}"
if (( libre_go < DISQUE_MIN_GO )); then
  echo "Pas assez de place sur le disque : on s'arrête, rien n'a été téléchargé." >&2
  exit 1
fi

echo "--- 1. Téléchargement (OpenStreetMap + altitude IGN, gratuits)"
systemd-run --quiet --wait --collect --pipe -p User="$UTILISATEUR" -p WorkingDirectory="$DONNEES" \
  -p MemoryMax="$LIMITE_MEMOIRE" -p MemorySwapMax=0 \
  "$DENIVELEUR" donnees telecharger --zone "$ZONE" --donnees "$DONNEES"

echo "--- 2. Construction du réseau, mémoire plafonnée à ${LIMITE_MEMOIRE}"
if ! systemd-run --quiet --wait --collect --pipe -p User="$UTILISATEUR" -p WorkingDirectory="$DONNEES" \
  -p MemoryMax="$LIMITE_MEMOIRE" -p MemorySwapMax=0 \
  "$CODE/.venv/bin/python" - "$ZONE" "$DONNEES" <<'PYTHON'
import resource
import sys
from pathlib import Path

from deniveleur import cli

cli.construire_reseau(sys.argv[1], Path(sys.argv[2]))
pic_mo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(f"Mémoire maximale de la construction : {pic_mo:.0f} Mo")
PYTHON
then
  echo "La construction a échoué : lire l'erreur au-dessus (« Killed » ou « MemoryError » = plafond mémoire atteint)." >&2
  echo "Le site n'est pas touché. Si c'est la mémoire, réduire la zone dans parametres.toml." >&2
  exit 1
fi

echo "--- 3. Mémoire que prendra le site avec ce réseau"
sudo -u "$UTILISATEUR" "$CODE/.venv/bin/python" - "$ZONE" "$DONNEES" <<'PYTHON'
import resource
import sys
from pathlib import Path

from deniveleur.reseau import Reseau

reseau = Reseau.charger(Path(sys.argv[2]) / sys.argv[1])
pic_mo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(f"{reseau.nombre_troncons} tronçons ; chargement du réseau : {pic_mo:.0f} Mo")
PYTHON
du -sh "$DONNEES/$ZONE" | awk '{print "Taille du réseau sur le disque : " $1}'
echo "Mémoire disponible maintenant : $(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo) Mo"
echo "--- Terminé. Envoyer ces lignes à Claude avant d'ouvrir le vélo sur le site."
