#!/bin/bash
# Avvio di CerHub su Cloudron.
set -eu

DATA=/app/data
RUN=/run/cerhub
APPS="users core energy documents adesioni"

echo "==> Preparazione cartelle"
mkdir -p "$RUN/tmp" "$DATA/logs" "$DATA/media/documents/gaudi"
for app in $APPS; do
    mkdir -p "$DATA/migrations/$app"
    touch "$DATA/migrations/$app/__init__.py"
done

# Segreti generati una sola volta e conservati nei dati (quindi nei backup)
if [[ ! -f "$DATA/secrets.env" ]]; then
    echo "==> Primo avvio: genero i segreti"
    {
        echo "SECRET_KEY='$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')'"
        echo "FIELD_ENCRYPTION_KEY='$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')'"
    } > "$DATA/secrets.env"
    chmod 600 "$DATA/secrets.env"
fi

# File per impostazioni facoltative (es. MQTT_HOST, MQTT_USER...): si modifica
# dal File Manager di Cloudron e si riavvia l'app.
if [[ ! -f "$DATA/env.sh" ]]; then
    cat > "$DATA/env.sh" <<'EOF'
# Impostazioni facoltative di CerHub. Togli il commento e riavvia l'app.
# export MQTT_HOST=
# export MQTT_PORT=1883
# export MQTT_USER=
# export MQTT_PASS=
# export MQTT_TLS=False
#
# Firma elettronica delle adesioni online (Documenso su firme.cerhub.it):
# export DOCUMENSO_API_TOKEN=
EOF
fi

chown -R cloudron:cloudron "$DATA" "$RUN"

set -a
# shellcheck disable=SC1091
source "$DATA/secrets.env"
# shellcheck disable=SC1091
source "$DATA/env.sh"
set +a

export DJANGO_SETTINGS_MODULE=cercollettiva.settings.cloudron
export HOME="$RUN"
cd /app/code

# Il repository non versiona le migrazioni: vengono generate qui e conservate
# in /app/data/migrations, così restano coerenti con il database tra un
# aggiornamento e l'altro.
echo "==> Migrazioni database"
gosu cloudron:cloudron python3 manage.py makemigrations --noinput $APPS
gosu cloudron:cloudron python3 manage.py migrate --noinput

# Il client MQTT parte solo con RUN_MAIN impostato (vedi energy/apps.py).
# Un solo processo con più thread: così c'è un unico client MQTT.
export RUN_MAIN=true

echo "==> Avvio gunicorn"
exec gosu cloudron:cloudron gunicorn cercollettiva.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 8 \
    --worker-class gthread \
    --timeout 120 \
    --worker-tmp-dir "$RUN/tmp" \
    --access-logfile - \
    --error-logfile - \
    --forwarded-allow-ips '*'
