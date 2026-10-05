#!/bin/bash
# Prepara il server Cloudron: copia lo script di aggiornamento in /opt/cerhub,
# installa il timer systemd giornaliero e (con --install) installa l'app.
# Da eseguire come root dalla cartella cloudron/server di un clone del fork.
set -eu

BASE="${CERHUB_BASE:-/opt/cerhub}"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$BASE"
install -m 750 "$HERE/cerhub-update.sh" "$BASE/cerhub-update.sh"

cat > /etc/systemd/system/cerhub-update.service <<EOF
[Unit]
Description=Aggiornamento automatico dell'app Cloudron CerHub (app.cerhub.it)
After=docker.service network-online.target

[Service]
Type=oneshot
Environment=HOME=/root
ExecStart=$BASE/cerhub-update.sh
TimeoutStartSec=3600
EOF

cat > /etc/systemd/system/cerhub-update.timer <<EOF
[Unit]
Description=Controllo giornaliero aggiornamenti CerHub

[Timer]
OnCalendar=*-*-* 03:50
RandomizedDelaySec=15min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now cerhub-update.timer

if [ "${1:-}" = "--install" ]; then
    "$BASE/cerhub-update.sh" --install
fi
