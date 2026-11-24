# Mettre le site en ligne (Oracle Cloud, gratuit)

Le site tourne sur un serveur gratuit d'Oracle Cloud (offre « Always Free »). Une fois
installé, il se met à jour tout seul : chaque nouvelle version de la branche
`production` est installée dans les 15 minutes, et les chemins OpenStreetMap sont
rafraîchis une fois par mois.

## Comment une version arrive en ligne

1. Une PR est fusionnée dans `main` (seulement si ses vérifications sont vertes).
2. Les vérifications repassent sur `main`. Si elles sont vertes, l'action **Production**
   avance la branche `production` sur ce commit. On n'y pousse jamais à la main.
3. Dans les 15 minutes, le serveur installe `production`. Avant, il garde une copie du
   réseau. Après, il vérifie que le site répond (jusqu'à 4 minutes, le temps de charger
   le réseau).
4. Si le site ne répond pas, le serveur remet **l'ancien code et l'ancien réseau**, relance
   le site et note la version comme **refusée** : il ne la réessaie plus et attend que
   `production` avance sur une correction.
5. Toutes les 30 minutes, l'action **Surveillance du site** compare le site à
   `production` et écrit dans l'issue « Journal des changements » si le site ne répond
   pas, si une version a été refusée ou si le serveur est en retard (puis quand tout est
   rentré dans l'ordre).

Pour savoir ce qui tourne : `https://<adresse-du-site>/sante` donne l'état, la version
installée et l'éventuelle version refusée.

Pour réessayer une version refusée (par exemple après un souci passager sur le serveur) :

```bash
sudo rm /var/lib/deniveleur-maj/refusee && sudo systemctl start deniveleur-maj
```

## Ce qu'il faut faire une seule fois

### 1. Créer le compte

Sur **oracle.com/cloud/free** → « Start for free ». Région d'origine : **France Central
(Paris)**. La carte bancaire sert à vérifier l'identité ; rien n'est facturé tant qu'on ne
passe pas en compte payant (« Upgrade »).

### 2. Créer le serveur

Dans la console Oracle : menu ☰ → **Compute** → **Instances** → **Create instance**.

| Réglage | Valeur |
|---|---|
| Name | `deniveleur` |
| Image | **Canonical Ubuntu 24.04** (bouton « Change image ») |
| Shape | « Change shape » → **Ampere** → **VM.Standard.A1.Flex**, 2 OCPU et 12 GB de mémoire (le maximum marqué « Always Free-eligible ») |
| Networking | laisser les valeurs par défaut ; vérifier que « Assign a public IPv4 address » est coché |
| Add SSH keys | « Generate a key pair for me » → télécharger la clé privée et la garder (elle sert seulement en cas de dépannage) |
| Advanced options → Management → Initialization script | « Paste cloud-init script », puis coller **tout** le contenu de [`deploiement/cloud-init.yaml`](../deploiement/cloud-init.yaml) |

Puis **Create**. Si Oracle répond « Out of capacity », réessayer un peu plus tard ou
choisir un autre « Availability domain ».

### 3. Ouvrir les portes du réseau

Par défaut, Oracle bloque tout sauf la connexion d'administration. Sur la page du
serveur : lien du **Subnet** → **Security Lists** → « Default Security List » → **Add
Ingress Rules** :

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80,443` |

### 4. Attendre et ouvrir le site

Le serveur s'installe tout seul en 10 à 15 minutes (il télécharge les chemins et
l'altitude, puis construit le réseau). L'adresse du site est construite à partir de
l'adresse IP publique du serveur (indiquée sur sa page), en remplaçant les points par
des tirets :

```
IP publique 152.67.12.34  →  https://152-67-12-34.sslip.io
```

`sslip.io` est un service gratuit qui fait pointer ce nom vers le serveur ; c'est ce qui
permet d'avoir un vrai `https` (et donc le bouton « Ma position » sur téléphone) sans
acheter de nom de domaine.

## Préparer le vélo de route sans risque pour le site

La zone `chevreuse-velo` est plus grosse que celle de la course à pied. Avant de l'ouvrir sur le site, on mesure ce qu'elle coûte, sur le serveur existant (rien n'est créé, rien n'est payant) :

```
sudo bash /opt/deniveleur/deploiement/construire-velo.sh
```

Le script refuse de démarrer s'il manque de la place sur le disque, plafonne la mémoire de la construction (65 % de la mémoire du serveur par défaut, réglable avec `LIMITE_MEMOIRE`) pour qu'un dépassement arrête la construction et jamais le site, puis affiche la mémoire maximale de la construction, la mémoire que prendra le site avec ce réseau, et la taille sur le disque. Il ne touche ni au réseau de la course à pied ni au service. À lancer à un moment calme, sans l'avoir testé sur Oracle : si une ligne d'erreur apparaît, la transmettre telle quelle.

## En cas de problème

Se connecter au serveur (bouton « Cloud Shell » ou SSH avec la clé), puis :

```bash
sudo tail -50 /var/log/deniveleur-installation.log   # déroulé de l'installation
sudo systemctl status deniveleur                      # le site tourne-t-il ?
sudo journalctl -u deniveleur -n 50                   # ses derniers messages
sudo journalctl -u deniveleur-maj -n 20               # les dernières mises à jour
cat /var/lib/deniveleur/deploiement.json              # version installée, version refusée
```

Relancer l'installation (sans risque, elle reprend où elle en était) :

```bash
curl -fsSL https://raw.githubusercontent.com/simeongug/Le-D-niveleur/main/deploiement/installer.sh | sudo bash
```

## Ce qui tourne sur le serveur

| Élément | Rôle |
|---|---|
| `/opt/deniveleur` | le code, copie de GitHub |
| `/var/lib/deniveleur` | les données (chemins, altitude, réseau) |
| service `deniveleur` | le site, relancé automatiquement s'il s'arrête |
| Caddy | reçoit les visites en `https` et obtient le certificat tout seul |
| minuteur `deniveleur-maj` | toutes les 15 min : installe la dernière version de `production`, vérifie le site, revient en arrière si besoin |
| `/var/lib/deniveleur-maj` | copie du réseau avant mise à jour, version refusée |
| minuteur `deniveleur-donnees` | une fois par mois : retélécharge les chemins OpenStreetMap |

Un seul calcul tourne à la fois (environ 30 s) ; les demandes suivantes attendent leur
tour, et la page affiche leur place dans la file.
