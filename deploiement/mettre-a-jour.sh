#!/usr/bin/env bash
# Mise à jour du Déniveleur sur le serveur (lancé par un minuteur, en root).
#   mettre-a-jour.sh            récupère la dernière version publiée sur GitHub, si elle a changé
#   mettre-a-jour.sh --donnees  retélécharge aussi les chemins OpenStreetMap
set -euo pipefail

CODE=/opt/deniveleur
DONNEES=/var/lib/deniveleur
UTILISATEUR=deniveleur
BRANCHE="${BRANCHE:-main}"
DENIVELEUR=(sudo -u "$UTILISATEUR" "$CODE/.venv/bin/deniveleur")

cd "$DONNEES"
avant="$(git -C "$CODE" rev-parse HEAD)"
git -C "$CODE" fetch -q origin "$BRANCHE"
apres="$(git -C "$CODE" rev-parse "origin/$BRANCHE")"
refaire_reseau=0

if [[ "$avant" != "$apres" ]]; then
  echo "Nouvelle version : $avant -> $apres"
  git -C "$CODE" reset -q --hard "origin/$BRANCHE"
  "$CODE/.venv/bin/pip" install -q "$CODE"
  # Le réseau ne se reconstruit que si ce qui le fabrique a changé.
  if git -C "$CODE" diff --name-only "$avant" "$apres" | grep -qE \
      'src/deniveleur/(reseau|profil|geo)\.py|src/deniveleur/donnees/|src/deniveleur/config/parametres\.toml'; then
    refaire_reseau=1
  fi
fi

if [[ "${1:-}" == "--donnees" ]]; then
  refaire_reseau=1
fi

if [[ $refaire_reseau -eq 1 ]]; then
  # Ne télécharge que ce qui manque ou a changé (nouvelle zone, nouvel extrait OSM…).
  "${DENIVELEUR[@]}" donnees telecharger --donnees "$DONNEES"
  "${DENIVELEUR[@]}" donnees reseau --donnees "$DONNEES"
fi

if [[ "$avant" != "$apres" || $refaire_reseau -eq 1 ]]; then
  systemctl restart deniveleur.service
  echo "Site redémarré."
fi
