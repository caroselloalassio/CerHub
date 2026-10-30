#!/bin/bash
# Avvio del broker MQTT CerHub su Cloudron.
set -eu

DATA=/app/data
RUN=/run/mosquitto

mkdir -p "$DATA/persistence" "$RUN/certs" "$RUN/extra"

# Certificato dell'indirizzo dell'app (addon tls di Cloudron). Cloudron riavvia
# l'app quando lo rinnova, quindi basta copiarlo all'avvio.
cp /etc/certs/tls_cert.pem /etc/certs/tls_key.pem "$RUN/certs/"
chmod 600 "$RUN/certs/tls_key.pem"

# Utenti e permessi: creati vuoti al primo avvio, poi gestiti con mqtt-utente
[ -f "$DATA/passwd" ] || : > "$DATA/passwd"
if [ ! -f "$DATA/acl" ]; then
    cat > "$DATA/acl" <<'ACL'
# Permessi del broker CerHub (file in /app/data, incluso nei backup).
# Dopo una modifica riavvia l'app.

# App CerHub: legge tutte le misure e pubblica il proprio stato
user cerhub-app
topic read cercollettiva/#
topic readwrite CerCollettiva/status
topic readwrite cercollettiva/status

# Tutti gli altri utenti (misuratori): solo sotto cercollettiva/<nome utente>/
pattern readwrite cercollettiva/%u/#
ACL
fi
# Aggiunte facoltative alla configurazione
[ -f "$DATA/mosquitto-extra.conf" ] && cp "$DATA/mosquitto-extra.conf" "$RUN/extra/"

chmod 700 "$DATA/persistence"
chmod 600 "$DATA/passwd" "$DATA/acl"
chown -R cloudron:cloudron "$DATA" "$RUN"

echo "==> Avvio di Mosquitto $(mosquitto -h 2>/dev/null | head -1 | awk '{print $3}')"
exec /usr/local/bin/gosu cloudron:cloudron mosquitto -c /app/code/mosquitto.conf
