FROM cloudron/base:5.1.0

RUN mkdir -p /app/code /app/data
WORKDIR /app/code

# Dipendenze Python in un virtualenv dedicato
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /app/code/requirements.txt
# Django resta sulla serie 5.0 del progetto, ma con le correzioni di sicurezza
RUN python3 -m venv /app/venv && \
    pip install --no-cache-dir --upgrade pip && \
    sed -i 's/^Django==5\.0$/Django>=5.0.14,<5.1/' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/code

# Il filesystem dell'app è in sola lettura: le cartelle scrivibili diventano
# collegamenti verso /app/data (persistente, nei backup).
RUN rm -rf /app/code/logs /app/code/media && \
    ln -s /app/data/logs /app/code/logs && \
    ln -s /app/data/media /app/code/media && \
    for app in users core energy documents; do \
        rm -rf /app/code/$app/migrations && \
        ln -s /app/data/migrations/$app /app/code/$app/migrations; \
    done

# File statici raccolti in fase di build (serviti da WhiteNoise)
RUN mkdir -p /run/cerhub/tmp /app/data/media /app/data/logs && \
    SECRET_KEY=build \
    FIELD_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
    CLOUDRON_POSTGRESQL_DATABASE=x CLOUDRON_POSTGRESQL_USERNAME=x \
    CLOUDRON_POSTGRESQL_PASSWORD=x CLOUDRON_POSTGRESQL_HOST=localhost \
    CLOUDRON_REDIS_URL=redis://localhost:6379 \
    DJANGO_SETTINGS_MODULE=cercollettiva.settings.cloudron \
    python3 manage.py collectstatic --noinput && \
    rm -rf /run/cerhub /app/data/media /app/data/logs && \
    chmod +x /app/code/cloudron/start.sh

EXPOSE 8000
CMD [ "/app/code/cloudron/start.sh" ]
