#!/usr/bin/env bash
# Lancé par l'action « Surveillance du site » (pas sur le serveur).
# Compare le site en ligne à la branche production et prévient dans l'issue
# « Journal des changements » : une fois par problème, puis une fois quand c'est réglé.
# Variables : REPO (propriétaire/nom), SITE (adresse du site), GH_TOKEN.
#   SIMULATION=1 affiche le message au lieu de l'écrire dans l'issue.
set -euo pipefail

RETARD_MAX_S="${RETARD_MAX_S:-2700}"   # 45 min : 15 min de minuteur + reconstruction du réseau
TITRE="Journal des changements"

prod_sha="$(gh api "repos/$REPO/branches/production" --jq .commit.sha 2>/dev/null || true)"
if [[ -z "$prod_sha" ]]; then
  echo "Pas encore de branche production : rien à surveiller."
  exit 0
fi
prod_date="$(gh api "repos/$REPO/commits/$prod_sha" --jq .commit.committer.date)"
age_s=$(($(date +%s) - $(date -d "$prod_date" +%s)))

sante="$(curl -fsS --max-time 30 --retry 2 --retry-delay 20 "$SITE/sante" 2>/dev/null || true)"
installe="$(jq -r '.deploiement.commit // empty' <<<"${sante:-null}" 2>/dev/null || true)"
refusee="$(jq -r '.deploiement.refusee // empty' <<<"${sante:-null}" 2>/dev/null || true)"
etat="$(jq -r '.etat // empty' <<<"${sante:-null}" 2>/dev/null || true)"

if [[ -z "$sante" ]]; then
  cle="site-muet"
  message="🔴 Le site ne répond pas ($SITE). Vérifier le serveur (docs/deploiement.md, « En cas de problème »)."
elif [[ "$etat" != "ok" ]]; then
  cle="site-$etat"
  message="🟠 Le site répond, mais son état est « $etat » au lieu de « ok »."
elif [[ -n "$refusee" && "$refusee" == "$prod_sha" ]]; then
  cle="refusee-${refusee:0:7}"
  message="🔴 Le serveur a refusé la version ${refusee:0:7} : le site ne répondait plus après l'installation. Il est revenu à ${installe:0:7}. À corriger sur main par une nouvelle PR ; le serveur installera la suivante tout seul."
elif [[ -n "$installe" && "$installe" != "$prod_sha" && $age_s -gt $RETARD_MAX_S ]]; then
  cle="retard-${prod_sha:0:7}"
  message="🟠 production est sur ${prod_sha:0:7} depuis plus de $((RETARD_MAX_S / 60)) min, mais le serveur est encore sur ${installe:0:7}. La mise à jour automatique est peut-être bloquée."
else
  cle="ok"
  message="🟢 Tout est rentré dans l'ordre : version ${installe:0:7} en ligne."
fi
echo "État : $cle — installé ${installe:0:7}, production ${prod_sha:0:7} (il y a $((age_s / 60)) min)."

num="$(gh issue list --repo "$REPO" --state all --limit 200 --json number,title \
  --jq "map(select(.title == \"$TITRE\")) | .[0].number // empty")"
if [[ -z "$num" ]]; then
  echo "Issue « $TITRE » introuvable."
  exit 0
fi

# Dernier message de surveillance déjà écrit (repéré par un marqueur invisible).
derniere="$(gh api --paginate "repos/$REPO/issues/$num/comments?per_page=100" \
  | jq -rs 'add // [] | map(.body | capture("<!-- surveillance:(?<cle>[^ ]+) -->").cle // empty) | last // ""')"

if [[ "$cle" == "$derniere" ]] || [[ "$cle" == "ok" && -z "$derniere" ]]; then
  echo "Rien de nouveau à signaler."
  exit 0
fi

corps="$message"$'\n\n'"<!-- surveillance:$cle -->"
if [[ "${SIMULATION:-0}" == "1" ]]; then
  echo "Message (simulation) : $corps"
else
  gh issue comment "$num" --repo "$REPO" --body "$corps"
fi
