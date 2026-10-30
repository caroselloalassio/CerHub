FROM cloudron/base:5.1.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends mosquitto mosquitto-clients && \
    rm -rf /var/lib/apt/lists/* /etc/mosquitto/conf.d/*

RUN mkdir -p /app/code
COPY start.sh mosquitto.conf mqtt-utente /app/code/
COPY www /app/code/www
RUN chmod +x /app/code/start.sh /app/code/mqtt-utente && \
    ln -sf /app/code/mqtt-utente /usr/local/bin/mqtt-utente

WORKDIR /app/code
CMD [ "/app/code/start.sh" ]
