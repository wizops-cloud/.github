#!/usr/bin/env bash
# Crée ou remet aux normes un projet Sentry WizOps (voir README.md) :
# réglages, filtres, règles d'alerte standard, puis affiche le DSN.
# Idempotent : relancer le script réaligne un projet existant sans doublon.
#
# Usage : bootstrap-project.sh <projet> <plateforme> [dépôt GitHub owner/nom]
#   ex.   bootstrap-project.sh wizscout-api node wizops-cloud/wizscout
#
# Environnement :
#   SENTRY_AUTH_TOKEN  jeton avec project:admin, alerts:write, org:read (obligatoire)
#   SENTRY_URL         défaut https://sentry.wizops.cloud
#   SENTRY_ORG         défaut wizops
#   SENTRY_TEAM        équipe propriétaire, défaut : la première de l'organisation
#   SLACK_CHANNEL      canal des alertes, défaut #sentry
#   GITHUB_ASSIGNEE    assigné des tickets de régression (optionnel)
set -euo pipefail

project=${1:?projet (ex. wizscout-api)}
platform=${2:?plateforme Sentry (ex. node, python-django, javascript-vue, go)}
repo=${3:-}
: "${SENTRY_AUTH_TOKEN:?SENTRY_AUTH_TOKEN manquant}"
url=${SENTRY_URL:-https://sentry.wizops.cloud}
org=${SENTRY_ORG:-wizops}
channel=${SLACK_CHANNEL:-#sentry}

api() {
  local method=$1 path=$2
  shift 2
  curl -sS --fail-with-body -X "$method" -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
    -H "Content-Type: application/json" "$url/api/0$path" "$@"
}

# 1. Projet
if api GET "/projects/$org/$project/" >/dev/null 2>&1; then
  echo "Projet $project existant : réalignement."
else
  team=${SENTRY_TEAM:-$(api GET "/organizations/$org/teams/" | jq -r '.[0].slug')}
  api POST "/teams/$org/$team/projects/" -d "$(jq -n --arg s "$project" --arg p "$platform" '{name: $s, slug: $s, platform: $p}')" >/dev/null
  echo "Projet $project créé (équipe $team)."
fi

# 2. Réglages : auto-résolution à 14 jours, données personnelles masquées côté serveur.
api PUT "/projects/$org/$project/" -d '{
  "resolveAge": 336,
  "dataScrubber": true,
  "dataScrubberDefaults": true,
  "scrubIPAddresses": true
}' >/dev/null

# 3. Filtres entrants : bruit des extensions, robots et vieux navigateurs (projets navigateur).
case $platform in
  javascript*)
    for filter in browser-extensions web-crawlers; do
      api PUT "/projects/$org/$project/filters/$filter/" -d '{"active": true}' >/dev/null
    done
    ;;
esac

# 4. Règles d'alerte standard (créées une fois, retrouvées par leur nom).
existing=$(api GET "/projects/$org/$project/rules/" | jq -r '.[].name')
slack_id=$(api GET "/organizations/$org/integrations/?provider_key=slack" | jq -r '.[0].id // empty')
github_id=$(api GET "/organizations/$org/integrations/?provider_key=github" | jq -r '.[0].id // empty')

production_filters='[
  {"id": "sentry.rules.filters.tagged_event.TaggedEventFilter", "key": "environment", "match": "sw", "value": "production"},
  {"id": "sentry.rules.filters.level.LevelFilter", "match": "gte", "level": "LEVEL"}
]'

add_rule() {
  local name=$1 body=$2
  if grep -qxF "$name" <<<"$existing"; then
    echo "Règle « $name » déjà présente."
  else
    api POST "/projects/$org/$project/rules/" -d "$body" >/dev/null
    echo "Règle « $name » créée."
  fi
}

if [ -n "$slack_id" ]; then
  slack_action=$(jq -n --argjson w "$slack_id" --arg c "$channel" \
    '[{id: "sentry.integrations.slack.notify_action.SlackNotifyServiceAction", workspace: ($w | tostring), channel: $c, tags: "environment,level,release"}]')
  add_rule "Slack - New & Escalating Issues" "$(jq -n --argjson a "$slack_action" --argjson f "${production_filters/LEVEL/30}" '{
    name: "Slack - New & Escalating Issues", actionMatch: "any", filterMatch: "all", frequency: 30,
    conditions: [
      {id: "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition"},
      {id: "sentry.rules.conditions.regression_event.RegressionEventCondition"}
    ],
    filters: $f, actions: $a}')"
  add_rule "Slack - High Volume Errors (>10/hour)" "$(jq -n --argjson a "$slack_action" --argjson f "${production_filters/LEVEL/40}" '{
    name: "Slack - High Volume Errors (>10/hour)", actionMatch: "any", filterMatch: "all", frequency: 60,
    conditions: [{id: "sentry.rules.conditions.event_frequency.EventFrequencyCondition", comparisonType: "count", interval: "1h", value: 10}],
    filters: $f, actions: $a}')"
else
  echo "::warning:: intégration Slack absente : règles Slack non créées." >&2
fi

if [ -n "$repo" ] && [ -n "$github_id" ]; then
  github_action=$(jq -n --argjson i "$github_id" --arg r "$repo" --arg u "${GITHUB_ASSIGNEE:-}" \
    '[{id: "sentry.integrations.github.notify_action.GitHubCreateTicketAction", integration: $i, repo: $r, labels: ["bug"],
       # Sentry exige les champs du formulaire de ticket (« issue link settings »).
       dynamic_form_fields: [
         {name: "repo", type: "select", choices: [[$r, ($r | split("/") | last)]], required: true},
         {name: "labels", type: "select", choices: [["bug", "bug"]], multiple: true, required: false}
       ]} + (if $u == "" then {} else {assignee: $u} end)]')
  add_rule "GitHub - Regression" "$(jq -n --argjson a "$github_action" --argjson f "${production_filters/LEVEL/40}" '{
    name: "GitHub - Regression", actionMatch: "any", filterMatch: "all", frequency: 30,
    conditions: [{id: "sentry.rules.conditions.regression_event.RegressionEventCondition"}],
    filters: $f, actions: $a}')"
fi

# 5. DSN à configurer dans l'application (variable SENTRY_DSN, jamais dans le code).
echo "DSN : $(api GET "/projects/$org/$project/keys/" | jq -r '.[0].dsn.public')"
