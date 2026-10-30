# CerHub MQTT — pacchetto Cloudron di Eclipse Mosquitto

Broker MQTT che riceve le misure dei dispositivi (Shelly Pro 3EM) e le passa
all'app CerHub. Installato su Cloudron come app a sé (`mqtt.cerhub.it`), quindi
compare tra le app, ha backup, log, terminale e riavvio come le altre.

## Come è fatto

- Immagine `cloudron/base` con il pacchetto `mosquitto` di Ubuntu.
- Addon `localstorage` (dati in `/app/data`, inclusi nei backup) e `tls`
  (certificato di `mqtt.cerhub.it`, copiato in `/run` a ogni avvio; Cloudron
  riavvia l'app quando lo rinnova).
- Porte:
  - `8883` MQTT su TLS, esposta da Cloudron come porta TCP dell'app
    (`MQTTS_PORT`, modificabile dalle impostazioni dell'app);
  - `8080` WebSocket, pubblicato da Cloudron in HTTPS su `wss://mqtt.cerhub.it/`;
    serve anche la pagina statica usata per il controllo di salute.
- Niente accessi anonimi. Utenti in `/app/data/passwd`, permessi in
  `/app/data/acl` (creato al primo avvio):
  - `cerhub-app` legge tutto sotto `cercollettiva/#`;
  - ogni altro utente scrive solo sotto `cercollettiva/<nome utente>/#`.
    Per i misuratori si usa come nome utente il POD e come prefisso MQTT sul
    dispositivo `cercollettiva/<POD>/<id-dispositivo>`.
- Aggiunte alla configurazione: `/app/data/mosquitto-extra.conf` (poi riavviare).

## Utenti

Dal terminale dell'app (Cloudron → app → Terminale) o dal server:

    cloudron exec --app mqtt.cerhub.it -- mqtt-utente aggiungi IT001E10397856
    cloudron exec --app mqtt.cerhub.it -- mqtt-utente elenco
    cloudron exec --app mqtt.cerhub.it -- mqtt-utente rimuovi IT001E10397856

`aggiungi` senza password ne genera una e la stampa. Le modifiche valgono
subito. Le credenziali vanno salvate in Bitwarden.

## Build e aggiornamento (sul server, come root)

    cd /opt/cerhub/src && git pull
    V=1.0.1   # nuova versione, aggiornare anche CloudronManifest.json
    docker build --pull -t 127.0.0.1:5000/it.cerhub.mqtt:$V cloudron/mosquitto
    docker push 127.0.0.1:5000/it.cerhub.mqtt:$V
    cd cloudron/mosquitto && cloudron update --image 127.0.0.1:5000/it.cerhub.mqtt:$V --app mqtt.cerhub.it

Prima installazione:

    cloudron install --image 127.0.0.1:5000/it.cerhub.mqtt:1.0.0 --location mqtt.cerhub.it -p MQTTS_PORT=8883
