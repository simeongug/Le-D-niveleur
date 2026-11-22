# Journal de Siméon

Une entrée par PR, la plus récente en haut, 5 lignes au plus : date, PR, ce qui change,
impact serveur, ce qui reste à faire.

## 22/11/2026 — Règles communes et branche production
- Ajoute `CLAUDE.md` (règles des deux Claude), les journaux, le modèle de PR.
- Nouvelle action « Production » : avance `production` sur `main` dès que sa CI est verte.
- L'issue « Journal des changements » ne reçoit plus que les PR (plus les pushes).
- Impact serveur : aucun (le serveur suit encore `main` ; il passera à `production` dans la PR serveur).
