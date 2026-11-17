#!/usr/bin/env bash
# Installe Le Déniveleur sur un serveur Ubuntu 24.04 neuf (prévu pour Oracle Cloud,
# processeur Arm). À lancer en root. Peut être relancé sans risque.
#
#   curl -fsSL https://raw.githubusercontent.com/simeongug/Le-D-niveleur/main/deploiement/installer.sh | sudo bash
#
# Ce que fait le script :
#   1. installe Python, git et Caddy (serveur web qui gère le https tout seul) ;
#   2. ouvre les ports 80 et 443 du pare-feu du serveur ;
#   3. récupère le code, prépare les données (environ 5 minutes) ;
#   4. lance le site et le relance automatiquement en cas de redémarrage ;
#   5. installe la mise à jour automatique (toutes les 15 min depuis GitHub) et le
#      rafraîchissement mensuel des chemins OpenStreetMap.
set -euo pipefail

DEPOT="${DEPOT:-https://github.com/simeongug/Le-D-niveleur.git}"
BRANCHE="${BRANCHE:-main}"
CODE=/opt/deniveleur
DONNEES=/var/lib/deniveleur
UTILISATEUR=deniveleur
JOURNAL=/var/log/deniveleur-installation.log

exec > >(tee -a "$JOURNAL") 2>&1
echo "=== Installation du Déniveleur — $(date -Is) ==="

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé en root (sudo)." >&2
  exit 1
fi

echo "--- 1. Logiciels"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv git curl caddy iptables-persistent

echo "--- 2. Pare-feu du serveur : ports 80 (http) et 443 (https)"
for port in 80 443; do
  if ! iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    # Avant la règle « tout rejeter » des images Oracle.
    iptables -I INPUT 1 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
netfilter-persistent save

echo "--- 3. Code et données"
id "$UTILISATEUR" >/dev/null 2>&1 || useradd --system --home "$DONNEES" --shell /usr/sbin/nologin "$UTILISATEUR"
mkdir -p "$DONNEES"
if [[ -d "$CODE/.git" ]]; then
  git -C "$CODE" fetch -q origin "$BRANCHE"
  git -C "$CODE" reset -q --hard "origin/$BRANCHE"
else
  git clone -q --depth 50 --branch "$BRANCHE" "$DEPOT" "$CODE"
fi
python3 -m venv "$CODE/.venv"
"$CODE/.venv/bin/pip" install -q --upgrade pip
"$CODE/.venv/bin/pip" install -q "$CODE"
chown -R "$UTILISATEUR:$UTILISATEUR" "$DONNEES"
cd "$DONNEES"
sudo -u "$UTILISATEUR" "$CODE/.venv/bin/deniveleur" donnees telecharger --donnees "$DONNEES"
sudo -u "$UTILISATEUR" "$CODE/.venv/bin/deniveleur" donnees reseau --donnees "$DONNEES"

echo "--- 4. Service du site"
cat > /etc/systemd/system/deniveleur.service <<SERVICE
[Unit]
Description=Le Déniveleur (site web)
After=network-online.target
Wants=network-online.target

[Service]
User=$UTILISATEUR
WorkingDirectory=$DONNEES
ExecStart=$CODE/.venv/bin/deniveleur site --hote 127.0.0.1 --port 8000 --donnees $DONNEES
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Adresse publique : le site est servi en https sur <ip-en-tirets>.sslip.io, un nom
# gratuit qui pointe vers l'adresse du serveur (Caddy obtient le certificat tout seul).
IP_PUBLIQUE="$(curl -fsS --max-time 10 https://api.ipify.org || true)"
if [[ -n "$IP_PUBLIQUE" ]]; then
  NOM="${IP_PUBLIQUE//./-}.sslip.io"
  cat > /etc/caddy/Caddyfile <<CADDY
$NOM {
	encode gzip
	reverse_proxy 127.0.0.1:8000
}

http://$IP_PUBLIQUE {
	redir https://$NOM{uri}
}
CADDY
else
  NOM=""
  printf ':80 {\n\tencode gzip\n\treverse_proxy 127.0.0.1:8000\n}\n' > /etc/caddy/Caddyfile
fi

echo "--- 5. Mises à jour automatiques"
cat > /etc/systemd/system/deniveleur-maj.service <<SERVICE
[Unit]
Description=Le Déniveleur : mise à jour depuis GitHub

[Service]
Type=oneshot
ExecStart=/bin/bash $CODE/deploiement/mettre-a-jour.sh
SERVICE
cat > /etc/systemd/system/deniveleur-maj.timer <<TIMER
[Unit]
Description=Le Déniveleur : vérifie les mises à jour toutes les 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
TIMER
cat > /etc/systemd/system/deniveleur-donnees.service <<SERVICE
[Unit]
Description=Le Déniveleur : rafraîchit les chemins OpenStreetMap

[Service]
Type=oneshot
ExecStart=/bin/bash $CODE/deploiement/mettre-a-jour.sh --donnees
SERVICE
cat > /etc/systemd/system/deniveleur-donnees.timer <<TIMER
[Unit]
Description=Le Déniveleur : rafraîchissement mensuel des chemins

[Timer]
OnCalendar=monthly
RandomizedDelaySec=6h
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable --now deniveleur.service deniveleur-maj.timer deniveleur-donnees.timer
systemctl restart caddy

echo "--- Vérification"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/sante | grep -q ok; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/sante && echo
echo "=== Terminé. Le site : ${NOM:+https://$NOM} (ou http://${IP_PUBLIQUE:-adresse-du-serveur})"
