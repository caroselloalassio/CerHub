# CerHub su Cloudron

Pacchetto per eseguire CerHub come app Cloudron (`it.cerhub.app`) su
`app.cerhub.it`.

## Come è fatto

| File | A cosa serve |
|---|---|
| `Dockerfile` | Immagine basata su `cloudron/base`, dipendenze Python in `/app/venv`, file statici raccolti in fase di build |
| `CloudronManifest.json` | Manifest dell'app: addon `postgresql`, `redis`, `sendmail`, `localstorage` |
| `cloudron/start.sh` | Avvio: segreti, migrazioni, gunicorn |
| `cercollettiva/settings/cloudron.py` | Impostazioni Django lette dalle variabili `CLOUDRON_*` |
| `cloudron/server/` | Script che girano sul server: build, installazione e aggiornamento automatico |

Dati persistenti (inclusi nei backup di Cloudron) in `/app/data`:

- `secrets.env` — `SECRET_KEY` e `FIELD_ENCRYPTION_KEY`, generati al primo avvio.
  **Non vanno persi**: la seconda cifra le password dei broker MQTT nel database.
- `env.sh` — impostazioni facoltative (MQTT…); dopo una modifica riavviare l'app.
- `media/` — documenti caricati.
- `migrations/` — migrazioni Django. Il repository non le versiona, quindi
  vengono generate all'avvio e conservate qui perché restino allineate al
  database tra un aggiornamento e l'altro.

Il client MQTT parte dentro il processo web (un solo worker gunicorn con più
thread, così esiste un solo client) quando nel pannello è configurato un broker
attivo.

## Adesioni online e firma elettronica

L'app `adesioni` pubblica la domanda di adesione su `/adesione/` (privati e ditte
individuali, aziende e associazioni). Alla conferma genera il PDF della domanda e
lo manda in firma a Documenso, l'istanza dell'associazione su `firme.cerhub.it`
(app Cloudron, versione gratuita), tramite le API v2. Dopo la firma scarica il
documento firmato, crea l'utente dell'aderente e avvisa per email l'aderente e
l'associazione. Le domande si esaminano da `/ceradmin/adesioni/adesione/`.

- Il token API di Documenso sta in `/app/data/env.sh` (`DOCUMENSO_API_TOKEN`).
  Senza token l'adesione online mostra "in fase di attivazione".
- File delle domande (PDF, foto del documento) in `/app/data/media/adesioni/`,
  serviti solo dall'app a chi ne ha diritto.
- Le domande compilate e non firmate vengono eliminate dopo 30 giorni.

## Posta

Il dominio `cerhub.it` esce da un relay autenticato come `noreply@cerhub.it`:
il mittente dell'app in Cloudron (app → Email) deve restare `noreply@cerhub.it`,
altrimenti il server di posta rifiuta i messaggi ("Mittente non consentito").
Lo stesso vale per `firme.cerhub.it`.

## Aggiornamenti

Sul server un timer systemd (`cerhub-update.timer`, ogni notte) esegue
`/opt/cerhub/cerhub-update.sh`:

1. se sul ramo `main` del fork c'è un nuovo commit → build, push sul registry
   locale, `cloudron update` (Cloudron fa un backup prima di aggiornare);
2. una volta a settimana ricompila da zero per prendere aggiornamenti
   dell'immagine base e delle dipendenze Python; aggiorna solo se è cambiato
   qualcosa;
3. dopo l'aggiornamento controlla `/monitoring/health/`; se l'app non risponde
   ripristina la versione precedente e non riprova quel commit;
4. esito notificato su ntfy.

Comandi manuali (root sul server):

```bash
/opt/cerhub/cerhub-update.sh            # controlla e aggiorna se serve
/opt/cerhub/cerhub-update.sh --force    # ricompila e aggiorna comunque
tail -f /opt/cerhub/update.log
```

## Prima installazione

```bash
git clone https://github.com/caroselloalassio/CerHub.git /opt/cerhub/src
/opt/cerhub/src/cloudron/server/setup-server.sh --install
```

Subito dopo creare l'amministratore: finché non ne esiste uno la pagina
`/setup/` è aperta a chiunque.
