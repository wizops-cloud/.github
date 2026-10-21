# Sentry chez WizOps

Toutes les applications WizOps envoient leurs erreurs, leurs traces applicatives,
leurs profils et leurs crons au Sentry auto-hébergé de l'organisation. Cette page
est la convention à suivre pour tout nouveau projet ; les deux outils de ce dossier
l'appliquent sans saisie manuelle.

## Démarrer un projet

```bash
SENTRY_AUTH_TOKEN=… tools/sentry/bootstrap-project.sh <produit>-<composant> <plateforme> wizops-cloud/<dépôt>
```

Le script est idempotent : il crée le projet ou le réaligne, applique les réglages
ci-dessous, crée les règles d'alerte standard et affiche le DSN.

## Nommage

| Élément | Règle | Exemple |
|---|---|---|
| Projet | `<produit>-<composant>` | `wizscout-api`, `wizstatus-frontend` |
| Environnement | `production`, `staging`, `development` uniquement | la région va dans un tag `region` |
| Release | SHA git complet du commit livré | `release: process.env.APP_VERSION` |
| Release d'une extension | `<projet>@<version du manifeste>` | `wizscout-extension@1.4.0` |

## Réglages appliqués à chaque projet

- Auto-résolution après 14 jours sans événement.
- Masquage des données sensibles côté serveur, adresses IP comprises (RGPD).
- Projets navigateur : filtres des extensions et des robots actifs.

## SDK : réglages par défaut

- `sendDefaultPii: false` / `send_default_pii=False` : l'application définit
  elle-même l'identifiant technique de l'utilisateur, jamais son e-mail.
- `release` et `environment` toujours renseignés (variables d'environnement).
- Traces : 10 % en production (`tracesSampleRate: 0.1`), 100 % ailleurs.
- Profils : 10 % des transactions échantillonnées (`profilesSampleRate: 0.1`).
- Replays (navigateur) : 10 % des sessions, 100 % des sessions en erreur, texte masqué.
- Crons : chaque tâche planifiée est suivie (Celery : `monitor_beat_tasks=True` ;
  Node : `Sentry.withMonitor(slug, fn, { schedule, timezone: "UTC" })`). Les tâches
  qui tournent plus d'une fois par minute en sont exclues.
- Un log d'erreur qui ne fait que répéter une exception déjà remontée ne doit pas
  partir comme événement (doublon).

## Alertes standard

| Règle | Déclencheur | Destination |
|---|---|---|
| Slack - New & Escalating Issues | nouvelle issue ou régression, niveau ≥ warning, production | Slack |
| Slack - High Volume Errors (>10/hour) | plus de 10 événements par heure, niveau ≥ error | Slack |
| GitHub - Regression | une issue résolue réapparaît | ticket GitHub |

Pas de ticket GitHub par nouvelle erreur : Sentry reste la file de tri, GitHub ne
reçoit que les régressions. Les alertes sur métriques (latence p95, taux d'échec,
sessions sans crash) se créent par produit dans Sentry, avec la même destination Slack.

## Release en CI

L'action composite `wizops-cloud/.github/actions/sentry-release` s'ajoute à la fin du
job qui construit ou livre l'application (même job : elle voit les fichiers de build) :

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0 # set-commits a besoin de l'historique
# … build …
- uses: wizops-cloud/.github/actions/sentry-release@main
  if: github.ref == 'refs/heads/main'
  with:
    auth-token: ${{ secrets.SENTRY_AUTH_TOKEN }}
    projects: monproduit-api monproduit-web
    sourcemaps: apps/web/dist # optionnel ; supprime les .map après envoi
```

Elle injecte les debug IDs, envoie les source maps, associe les commits, finalise la
release et déclare le déploiement. Un échec Sentry n'échoue jamais la livraison.

Le jeton est un jeton d'organisation (scope `org:ci`), rangé en secret du dépôt
`SENTRY_AUTH_TOKEN`. Pour une image Docker, l'envoi peut aussi se faire pendant la
build avec un secret BuildKit (`--mount=type=secret,id=sentry_auth_token`).

## Résoudre une issue depuis un commit

Ajouter `Fixes <ID-SENTRY>` dans le message de commit (ex. `Fixes WIZSCOUT-API-12`) :
Sentry résout l'issue à la release qui contient le commit et la rouvre en régression
si elle réapparaît.
