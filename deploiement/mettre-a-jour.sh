#!/usr/bin/env bash
# Mise à jour du Déniveleur sur le serveur (lancé par un minuteur toutes les 15 min, en root).
#   mettre-a-jour.sh            installe la dernière version de la branche production, si elle a changé
#   mettre-a-jour.sh --donnees  retélécharge aussi les chemins OpenStreetMap et reconstruit le réseau
#
# Filet de sécurité : avant de toucher à quoi que ce soit, on garde une copie du réseau. Après
# l'installation, on vérifie que le site répond. Sinon, on remet l'ancien code ET l'ancien
# réseau, on relance le site, et on note la version « refusée » : elle ne sera plus réessayée
# (on attend que production avance sur une correction). Le résultat est écrit dans
# deploiement.json, que le site affiche sur /sante et que l'action « Surveillance du site »
# signale dans l'issue « Journal des changements ».
set -euo pipefail

CODE="${CODE:-/opt/deniveleur}"
DONNEES="${DONNEES:-/var/lib/deniveleur}"
ETAT="${ETAT:-/var/lib/deniveleur-maj}"            # mémoire de la mise à jour (sauvegarde, version refusée)
VERROU="${VERROU:-/run/deniveleur-maj.lock}"
UTILISATEUR=deniveleur
BRANCHE="${BRANCHE:-production}"
ZONE="${ZONE:-ouest-parisien}"                       # zone servie par le site
SANTE="${SANTE:-http://127.0.0.1:8000/sante}"
ATTENTE_SANTE_S="${ATTENTE_SANTE_S:-240}"            # le site met un moment à charger le réseau
# Fichiers qui, s'ils changent, obligent à reconstruire le réseau.
FICHIERS_RESEAU='src/deniveleur/(reseau|profil|geo)\.py|src/deniveleur/donnees/|src/deniveleur/config/parametres\.toml'
FICHIERS_SAUVES=(reseau.npz reseau.json voies.json.gz)

journal() { echo "$*" >&2; }

deniveleur() { sudo -u "$UTILISATEUR" "$CODE/.venv/bin/deniveleur" "$@"; }

# La branche production est créée par GitHub après la première fusion ; d'ici là, on suit main.
choisir_branche() {
  if [[ "$BRANCHE" != main ]] && ! git -C "$CODE" ls-remote -q --exit-code --heads origin "$BRANCHE" >/dev/null; then
    journal "La branche $BRANCHE n'existe pas encore : on suit main."
    echo main
  else
    echo "$BRANCHE"
  fi
}

ecrire_etat() {  # resultat commit refusee message
  local fichier="$DONNEES/deploiement.json"
  printf '{"resultat": "%s", "commit": "%s", "branche": "%s", "refusee": "%s", "date": "%s", "message": "%s"}\n' \
    "$1" "$2" "$BRANCHE_SUIVIE" "$3" "$(date -Is)" "$4" > "$fichier.tmp"
  chmod 644 "$fichier.tmp"
  mv "$fichier.tmp" "$fichier"
}

site_repond() {
  local fin=$((SECONDS + ATTENTE_SANTE_S))
  while ((SECONDS < fin)); do
    if curl -fsS --max-time 5 "$SANTE" 2>/dev/null | grep -Eq '"etat": ?"ok"'; then
      return 0
    fi
    sleep 5
  done
  return 1
}

redemarrer_et_verifier() {
  systemctl restart deniveleur.service || return 1
  site_repond
}

sauver_reseau() {
  rm -rf "$ETAT/sauvegarde"
  mkdir -p "$ETAT/sauvegarde"
  local f
  for f in "${FICHIERS_SAUVES[@]}"; do
    if [[ -f "$DONNEES/$ZONE/$f" ]]; then cp -p "$DONNEES/$ZONE/$f" "$ETAT/sauvegarde/$f"; fi
  done
}

restaurer_reseau() {
  local f
  for f in "${FICHIERS_SAUVES[@]}"; do
    if [[ -f "$ETAT/sauvegarde/$f" ]]; then cp -p "$ETAT/sauvegarde/$f" "$DONNEES/$ZONE/$f"; fi
  done
}

installer_code() {  # commit
  git -C "$CODE" reset -q --hard "$1" || return 1
  "$CODE/.venv/bin/pip" install -q "$CODE" || return 1
}

# Chaque étape s'arrête à la première erreur (les fonctions appelées dans un « if » ne
# s'arrêtent pas toutes seules, d'où les « || return 1 »).
mettre_en_place() {  # cible refaire_reseau telecharger
  if [[ "$1" != "$(git -C "$CODE" rev-parse HEAD)" ]]; then
    installer_code "$1" || return 1
  fi
  if [[ $2 -eq 1 ]]; then
    # Ne télécharge que ce qui manque ou a changé, sauf avec --donnees.
    deniveleur donnees telecharger --donnees "$DONNEES" || return 1
    deniveleur donnees reseau --donnees "$DONNEES" || return 1
  fi
  redemarrer_et_verifier
}

principal() {
  exec 9>"$VERROU"
  if ! flock -n 9; then
    journal "Une mise à jour est déjà en cours."
    return 0
  fi
  mkdir -p "$ETAT"
  cd "$DONNEES"

  BRANCHE_SUIVIE="$(choisir_branche)"
  # Chemin complet : le serveur a été cloné en ne suivant que main.
  git -C "$CODE" fetch -q origin "+refs/heads/$BRANCHE_SUIVIE:refs/remotes/origin/$BRANCHE_SUIVIE"
  local avant cible refusee
  avant="$(git -C "$CODE" rev-parse HEAD)"
  cible="$(git -C "$CODE" rev-parse "origin/$BRANCHE_SUIVIE")"
  refusee="$(cat "$ETAT/refusee" 2>/dev/null || true)"

  if [[ "$cible" == "$refusee" && "$cible" != "$avant" ]]; then
    journal "La version $cible a déjà été refusée : on reste sur $avant en attendant la suivante."
    cible="$avant"
  fi

  local refaire_reseau=0
  if [[ "$avant" != "$cible" ]] && git -C "$CODE" diff --name-only "$avant" "$cible" | grep -qE "$FICHIERS_RESEAU"; then
    refaire_reseau=1
  fi
  # Le site sert cette zone : si son réseau manque, il plante en boucle (20 novembre 2026).
  if [[ ! -f "$DONNEES/$ZONE/reseau.npz" ]]; then
    journal "Réseau de la zone $ZONE absent : construction."
    refaire_reseau=1
  fi
  if [[ "${1:-}" == "--donnees" ]]; then
    refaire_reseau=1
  fi

  if [[ "$avant" == "$cible" && $refaire_reseau -eq 0 ]]; then
    if [[ ! -f "$DONNEES/deploiement.json" ]]; then ecrire_etat ok "$avant" "$refusee" "Rien de nouveau."; fi
    return 0
  fi

  journal "Mise à jour : $avant -> $cible (réseau à reconstruire : $refaire_reseau)."
  if [[ $refaire_reseau -eq 1 ]]; then sauver_reseau; fi

  if mettre_en_place "$cible" "$refaire_reseau"; then
    if [[ "$cible" != "$avant" ]]; then rm -f "$ETAT/refusee"; refusee=""; fi
    ecrire_etat ok "$cible" "$refusee" "Version installée et site vérifié."
    journal "Site redémarré et vérifié : version $cible en ligne."
    return 0
  fi

  # Échec : on revient à la version d'avant, code et réseau.
  journal "ÉCHEC de la mise à jour vers $cible : retour à $avant."
  if [[ "$cible" != "$avant" ]]; then
    echo "$cible" > "$ETAT/refusee"
    refusee="$cible"
  fi
  local retour_ok=1
  installer_code "$avant" || retour_ok=0
  if [[ $refaire_reseau -eq 1 ]]; then restaurer_reseau; fi
  redemarrer_et_verifier || retour_ok=0
  if [[ $retour_ok -eq 1 ]]; then
    ecrire_etat retour-arriere "$avant" "$refusee" "Version $cible refusée : le site ne répondait plus. Retour à la version précédente."
    journal "Retour en arrière réussi : version $avant en ligne."
  else
    ecrire_etat echec "$avant" "$refusee" "Version $cible refusée, et la version précédente ne répond pas non plus."
    journal "ATTENTION : même la version précédente ne répond pas."
  fi
  return 1
}

# Tout sur une ligne : bash lit ce fichier au fur et à mesure, et la mise à jour le remplace.
principal "$@"; exit $?
