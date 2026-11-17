# 5. Héberger le site sur le serveur gratuit d'Oracle Cloud

**Date :** 17 novembre 2026 — **État :** retenue (choix de Siméon)

## Le besoin

Mettre le Déniveleur en ligne pour l'utiliser depuis un téléphone et le partager avec
des amis, avec un budget de 0 €. Chaque demande occupe le processeur environ 30 s et le
réseau de chemins tient quelques centaines de Mo en mémoire.

## Options étudiées

| Option | Pour | Contre |
|---|---|---|
| **Serveur gratuit Oracle Cloud (Arm, 2 cœurs, 12 Go)** | 0 €, toujours allumé, largement assez puissant, vraie adresse web | Compte avec carte bancaire ; offre réduite récemment ; « plus de capacité » possible à la création |
| Sur l'ordinateur de Siméon | 0 €, aucun compte | Site disponible seulement ordinateur allumé, et seulement sur le même wifi |
| Petit serveur payant (type Hetzner) | Le plus simple et fiable | Environ 4-5 € par mois, hors budget |
| Render (offre gratuite) | Installation simple | 0,1 cœur et 512 Mo : beaucoup trop faible, mise en veille après 15 min |
| Hugging Face Spaces | Pensé pour les démos | L'offre gratuite ne permet plus d'y faire tourner un serveur Python |

## Décision

Oracle Cloud, avec :
- une installation entièrement automatique au premier démarrage (`deploiement/`) ;
- le `https` par Caddy et un nom gratuit en `sslip.io`, sans nom de domaine à acheter ;
- la mise à jour automatique depuis la branche `main`, pour qu'aucune manipulation ne
  soit nécessaire après chaque évolution.

## Ce que ça implique

- Le passage à un autre hébergeur reste simple : le même script s'installe sur
  n'importe quel serveur Ubuntu 24.04.
- Si Oracle supprimait son offre gratuite, la solution de repli est un petit serveur
  payant.
- Un seul calcul à la fois : suffisant pour quelques coureurs, à revoir si le site
  s'ouvre plus largement.
