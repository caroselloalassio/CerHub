# Plugin WordPress `cerhub-site` (www.cerhub.it)

Plugin dell'associazione per il sito informativo www.cerhub.it:

- banner di consenso ai cookie senza servizi esterni (stesso cookie `cerhub_consent`
  usato dall'area soci app.cerhub.it);
- Google Analytics e Jetpack Stats caricati solo dopo il consenso;
- antispam del modulo di contatto (Contact Form 7) senza servizi esterni:
  campo-trappola e controllo sul tempo di compilazione;
- piè di pagina con Privacy Policy, Cookie Policy, "Preferenze cookie" e Codice Fiscale.

Installazione/aggiornamento: copiare la cartella `cerhub-site` in
`wp-content/plugins/` del sito (sul server Cloudron:
`/home/yellowtent/appsdata/<id app www.cerhub.it>/data/wp-content/plugins/`),
proprietario `www-data`.
