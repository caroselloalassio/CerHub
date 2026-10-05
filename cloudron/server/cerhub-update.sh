#!/bin/bash
# Build e aggiornamento dell'app Cloudron CerHub a partire dal fork GitHub.
#
# Gira sul server Cloudron (root), di norma da un timer systemd giornaliero.
#   cerhub-update.sh             aggiorna se c'è un nuovo commit sul ramo, oppure
#                                (una volta a settimana) se sono cambiate immagine
#                                base o dipendenze Python
#   cerhub-update.sh --force     ricompila e aggiorna comunque
#   cerhub-update.sh --install   prima installazione dell'app
#
# Questo file viene copiato in /opt/cerhub al momento dell'installazione e NON
# si aggiorna da solo dal repository: così un push sul fork non può cambiare
# ciò che gira come root sul server.
set -uo pipefail

APP="${CERHUB_APP:-app.cerhub.it}"
REPO="${CERHUB_REPO:-https://github.com/caroselloalassio/CerHub.git}"
BRANCH="${CERHUB_BRANCH:-main}"
BASE="${CERHUB_BASE:-/opt/cerhub}"
REG="${CERHUB_REGISTRY:-127.0.0.1:5000/it.cerhub.app}"
NTFY_URL="${CERHUB_NTFY_URL:-https://ntfy.carosello.net/claude}"
REBUILD_DAYS="${CERHUB_REBUILD_DAYS:-7}"
HEALTH_URL="https://$APP/monitoring/health/"

SRC="$BASE/src"
STATE="$BASE/state"
BUILD="$BASE/build"
PREV="$BASE/prev"
LOG="$BASE/update.log"
MODE="${1:-}"

export HOME=/root
for d in /usr/local/node-*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
export PATH

mkdir -p "$BASE" "$STATE"
exec 9>"$BASE/.lock"
flock -n 9 || { echo "aggiornamento già in corso"; exit 0; }
exec > >(tee -a "$LOG") 2>&1
echo "==== $(date -Is) ${MODE:-auto} ===="

notify() { # $1=titolo $2=testo $3=priorità
    local tok=""
    [ -f /root/.ntfy-token ] && tok=$(cat /root/.ntfy-token)
    curl -s -m 15 -H "Title: $1" -H "Priority: ${3:-default}" -H "Tags: cerhub" \
        ${tok:+-H "Authorization: Bearer $tok"} -d "$2" "$NTFY_URL" >/dev/null || true
}
fail() { echo "ERRORE: $1"; notify "CerHub: aggiornamento fallito" "$1" high; exit 1; }
state() { cat "$STATE/$1" 2>/dev/null || echo "${2:-}"; }
healthy() { curl -s -m 10 "$HEALTH_URL" | grep -q '"status": *"healthy"'; }
wait_healthy() { for _ in $(seq 1 36); do healthy && return 0; sleep 10; done; return 1; }
bump() { python3 -c "v='$1'.split('.'); v[2]=str(int(v[2])+1); print('.'.join(v))"; }
set_manifest() { # $1=cartella $2=versione $3=commit
    python3 - "$1/CloudronManifest.json" "$2" "$3" <<'PY'
import json, sys
path, version, commit = sys.argv[1:4]
m = json.load(open(path))
m["version"] = version
m["upstreamVersion"] = commit
json.dump(m, open(path, "w"), indent=2, ensure_ascii=False)
PY
}

# --- Sorgenti -----------------------------------------------------------------
if [ ! -d "$SRC/.git" ]; then
    git clone --branch "$BRANCH" "$REPO" "$SRC" || fail "git clone non riuscito"
fi
git -C "$SRC" fetch --quiet origin "$BRANCH" || { echo "GitHub non raggiungibile, riprovo al prossimo giro"; exit 0; }
NEW=$(git -C "$SRC" rev-parse "origin/$BRANCH")
CUR=$(state commit)
CURVER=$(state version)
LAST=$(state last_build 0)
NOW=$(date +%s)

REASON=""
if [ "$MODE" = "--install" ]; then REASON=install
elif [ "$MODE" = "--force" ]; then REASON=force
elif [ "$NEW" != "$CUR" ]; then REASON=commit
elif [ $(( (NOW - LAST) / 86400 )) -ge "$REBUILD_DAYS" ]; then REASON=periodic
fi
[ -z "$REASON" ] && { echo "nessun aggiornamento (commit ${CUR:0:7})"; exit 0; }
if [ "$REASON" = commit ] && [ "$NEW" = "$(state skip_commit)" ]; then
    echo "commit ${NEW:0:7} già fallito in passato: salto (usa --force)"; exit 0
fi
if [ "$REASON" != install ] && [ -z "$CURVER" ]; then fail "app non ancora installata: usa --install"; fi

if [ "$REASON" = install ]; then NEWVER=1.0.0; else NEWVER=$(bump "$CURVER"); fi
echo "motivo=$REASON commit=${CUR:0:7}->${NEW:0:7} versione=${CURVER:-nessuna}->$NEWVER"

# --- Build --------------------------------------------------------------------
rm -rf "$BUILD"; mkdir -p "$BUILD"
git -C "$SRC" archive "$NEW" | tar -x -C "$BUILD" || fail "estrazione sorgenti non riuscita"
set_manifest "$BUILD" "$NEWVER" "${NEW:0:7}"

NOCACHE=""
[ "$REASON" = periodic ] || [ "$REASON" = force ] && NOCACHE="--no-cache"
docker build --pull $NOCACHE -t "$REG:$NEWVER" "$BUILD" || fail "docker build non riuscito (commit ${NEW:0:7}); l'app resta sulla versione $CURVER"

# Impronta di ciò che contiene l'immagine: se nel giro settimanale non è
# cambiato nulla (stesso codice, stessi pacchetti) non serve aggiornare.
FP=$(docker run --rm --entrypoint /bin/bash "$REG:$NEWVER" -c \
    'pip freeze 2>/dev/null; dpkg-query -W 2>/dev/null' | sha256sum | cut -d" " -f1)
FP="$NEW-$FP"
if [ "$REASON" = periodic ] && [ "$FP" = "$(state fingerprint)" ]; then
    echo "nessuna novità in immagine base e dipendenze"
    docker rmi "$REG:$NEWVER" >/dev/null 2>&1
    echo "$NOW" > "$STATE/last_build"
    rm -rf "$BUILD"
    exit 0
fi
docker push "$REG:$NEWVER" || fail "push dell'immagine $NEWVER non riuscito"

# --- Installazione / aggiornamento -------------------------------------------
cd "$BUILD"
if [ "$REASON" = install ] && ! cloudron status --app "$APP" >/dev/null 2>&1; then
    cloudron install --image "$REG:$NEWVER" --location "$APP" || fail "cloudron install non riuscito"
else
    # anche per --install, se l'app esiste già (installazione precedente non completata)
    cloudron update --image "$REG:$NEWVER" --app "$APP" || echo "cloudron update ha segnalato un errore, verifico lo stato dell'app"
fi

if wait_healthy; then
    echo "$NEW" > "$STATE/commit"; echo "$NEWVER" > "$STATE/version"
    echo "$NOW" > "$STATE/last_build"; echo "$FP" > "$STATE/fingerprint"
    rm -f "$STATE/skip_commit"
    rm -rf "$PREV"; mv "$BUILD" "$PREV"
    # tiene in locale solo le ultime tre immagini
    docker images "$REG" --format '{{.Tag}}' | sort -t. -k1,1n -k2,2n -k3,3n | head -n -3 | \
        while read -r t; do docker rmi "$REG:$t" >/dev/null 2>&1; done
    case "$REASON" in
        install) MSG="Installata la versione $NEWVER (commit ${NEW:0:7}) su $APP." ;;
        commit)  MSG="Aggiornata a $NEWVER: nuovo codice dal fork (${CUR:0:7} → ${NEW:0:7})." ;;
        *)       MSG="Aggiornata a $NEWVER: immagine base e dipendenze rinnovate (codice ${NEW:0:7})." ;;
    esac
    notify "CerHub aggiornato" "$MSG"
    echo "OK $NEWVER"
    exit 0
fi

# --- Ripristino ---------------------------------------------------------------
if [ "$REASON" = install ] || [ ! -d "$PREV" ]; then
    fail "l'app non risponde dopo l'installazione della versione $NEWVER"
fi
echo "l'app non risponde: ripristino il codice della versione $CURVER"
RBVER=$(bump "$NEWVER")
set_manifest "$PREV" "$RBVER" "${CUR:0:7}"
docker tag "$REG:$CURVER" "$REG:$RBVER" && docker push "$REG:$RBVER"
( cd "$PREV" && cloudron update --image "$REG:$RBVER" --app "$APP" )
echo "$RBVER" > "$STATE/version"
echo "$NEW" > "$STATE/skip_commit"
echo "$NOW" > "$STATE/last_build"
if wait_healthy; then
    notify "CerHub: aggiornamento annullato" "La versione $NEWVER (commit ${NEW:0:7}) non è partita: ripristinato il codice precedente (${CUR:0:7}, versione $RBVER). Non riproverò questo commit." high
else
    notify "CerHub NON RAGGIUNGIBILE" "Aggiornamento a $NEWVER fallito e anche il ripristino non risponde. Serve un intervento: cloudron logs --app $APP" urgent
fi
exit 1
