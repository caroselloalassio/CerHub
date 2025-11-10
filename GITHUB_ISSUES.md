# GitHub Issues - CerCollettiva Project Analysis

Queste issue sono state generate dall'analisi del progetto. Crea le issue su GitHub copiando titolo e descrizione.

---

## 🔥 PRIORITÀ ALTA

### Issue #1: Implementare test suite completo per il progetto

**Labels**: `priority:high`, `type:testing`, `technical-debt`

**Description**:
La copertura dei test è attualmente al 5-10%, molto al di sotto dello standard di qualità del 80%. È necessario implementare una suite di test completa.

**Tasks**:

#### Testing MQTT Client
- [ ] Test connessione/disconnessione broker MQTT
- [ ] Test message handling e gestione queue (10.000 messaggi)
- [ ] Test buffer management (1.000 messaggi)
- [ ] Test reconnection logic con exponential backoff
- [ ] Test ACL authorization per topic
- [ ] Test thread-safety e worker threads
- [ ] Test timeout e gestione errori di rete

#### Testing Processore GAUDI
- [ ] Test parsing PDF con documenti sample reali
- [ ] Test estrazione POD (Point of Delivery)
- [ ] Test estrazione dati da diverse versioni formato GAUDI
- [ ] Test gestione errori e documenti malformati
- [ ] Test validazione dati estratti
- [ ] Test stati processamento (PENDING, PROCESSING, COMPLETED, FAILED)

#### Testing Views Django
- [ ] Test autenticazione e autorizzazione per tutte le viste
- [ ] Test form submission e validazione
- [ ] Test redirect e permissions (ADMIN, MEMBER, VIEWER)
- [ ] Test context data e template rendering
- [ ] Test GDPR consent required mixin
- [ ] Test data protection mixin (mascheramento dati)

#### Integration Tests
- [ ] Test end-to-end: caricamento → processamento → storage documento GAUDI
- [ ] Test flusso completo registrazione utente con consensi GDPR
- [ ] Test gestione membership CER (join, role changes, leave)
- [ ] Test dispositivi IoT → MQTT → database → dashboard
- [ ] Test calcolo energia condivisa e ripartizione economica

#### Test Infrastructure
- [ ] Setup pytest-cov o coverage.py
- [ ] Configurare threshold minimo 80% per nuovi commit
- [ ] Integrare coverage reporting in CI/CD
- [ ] Creare fixtures comuni per test (users, CER, plants, devices)
- [ ] Documentare come scrivere e eseguire test

**Acceptance Criteria**:
- [ ] Coverage totale >= 80%
- [ ] Tutti i moduli critici (MQTT, GAUDI, views) >= 90%
- [ ] Test eseguibili con `python manage.py test`
- [ ] Report coverage generato automaticamente
- [ ] Documentazione testing nel README

**Estimated Effort**: 40-60 ore

---

### Issue #2: Migliorare sicurezza - Spostare encryption key da settings a environment

**Labels**: `priority:high`, `type:security`, `GDPR`

**Description**:
Attualmente `FIELD_ENCRYPTION_KEY` è hardcoded in `cercollettiva/settings/base.py`:
```python
FIELD_ENCRYPTION_KEY = 'DeN2PosBdpf14DwdYqeTgzcT0Ysfk3lfGMqEI9nls9k='
```

Questo rappresenta un rischio di sicurezza. La chiave deve essere gestita come secret tramite variabili d'ambiente.

**Tasks**:
- [ ] Modificare `cercollettiva/settings/base.py` per leggere key da environment
- [ ] Aggiornare `.env.example` con `FIELD_ENCRYPTION_KEY=`
- [ ] Aggiungere validazione obbligatoria in `production.py` (raise se mancante)
- [ ] Documentare generazione chiave sicura in README.md
- [ ] Aggiungere script per generare nuove chiavi: `python manage.py generate_encryption_key`
- [ ] Testare migrazione in staging con rotazione chiave
- [ ] Aggiornare documentazione deployment

**Security Note**:
La chiave attuale nel codice deve essere considerata compromessa e NON usata in produzione.

**Acceptance Criteria**:
- [ ] Nessuna chiave di encryption hardcoded nel codice
- [ ] Production settings fallisce se FIELD_ENCRYPTION_KEY non è impostata
- [ ] Documentazione completa per generazione e rotazione chiavi
- [ ] Test in staging completati con successo

**Estimated Effort**: 4-6 ore

---

### Issue #3: Implementare audit log per accessi dati personali (GDPR)

**Labels**: `priority:high`, `type:feature`, `GDPR`, `compliance`

**Description**:
Per conformità GDPR articolo 30 (registro delle attività di trattamento), è necessario implementare un sistema di audit log che traccia tutti gli accessi ai dati personali degli utenti.

**Requirements GDPR**:
- Chi ha acceduto ai dati (user_id)
- Quali dati sono stati acceduti (resource_type, resource_id)
- Quando (timestamp)
- Da dove (IP address, user agent)
- Quale operazione (READ, UPDATE, DELETE, EXPORT)
- Motivo dell'accesso (purpose)

**Tasks**:

#### Modello Audit Log
- [ ] Creare modello `GDPRAuditLog` in `users/models.py`
- [ ] Campi: user, target_user, resource_type, resource_id, action, purpose, ip_address, user_agent, timestamp
- [ ] Indici database per query performance
- [ ] Retention policy (es. 3 anni come richiesto GDPR)

#### Middleware/Decorator
- [ ] Creare decorator `@audit_personal_data_access` per viste
- [ ] Middleware per catturare automaticamente IP e user agent
- [ ] Integrare con GDPRConsentRequiredMixin esistente

#### Dashboard Compliance
- [ ] Vista admin per visualizzare audit logs
- [ ] Filtri per utente, data, tipo operazione
- [ ] Export audit log per compliance officer (CSV, PDF)
- [ ] Alert su accessi anomali (frequenza, orari)

#### Applicazione
- [ ] Applicare audit a tutte le viste che accedono dati personali
- [ ] Audit su export dati GDPR
- [ ] Audit su modifiche profilo utente
- [ ] Audit su accesso documenti confidenziali

**Acceptance Criteria**:
- [ ] Ogni accesso a dati personali viene loggato
- [ ] Dashboard audit accessibile solo a compliance officer
- [ ] Export audit log funzionante
- [ ] Retention policy implementata con cleanup automatico
- [ ] Documentazione per compliance

**Estimated Effort**: 20-30 ore

---

### Issue #4: Sistema automatico per richieste GDPR (data export/delete)

**Labels**: `priority:high`, `type:feature`, `GDPR`, `compliance`

**Description**:
Implementare sistema automatizzato per gestire richieste GDPR degli utenti (diritto all'oblio, portabilità dati) come richiesto dagli articoli 17 e 20 del GDPR.

**Features Richieste**:

#### 1. Data Export (Art. 20 GDPR - Portabilità)
- [ ] Endpoint `/api/gdpr/export-my-data/` (POST)
- [ ] Raccolta tutti i dati utente da tutte le tabelle
- [ ] Export in formato JSON strutturato
- [ ] Export alternativo in PDF human-readable
- [ ] Include: profilo, membership CER, documenti, consensi, audit log
- [ ] Email con link download sicuro (expire 48h)
- [ ] Log richiesta in audit trail

#### 2. Data Deletion (Art. 17 GDPR - Oblio)
- [ ] Endpoint `/api/gdpr/delete-my-data/` (POST)
- [ ] Conferma via email con token (double opt-in)
- [ ] Grace period 30 giorni per cancellazione effettiva
- [ ] Anonymization invece di hard delete dove richiesto per integrità dati
- [ ] Gestione foreign keys e dipendenze (impianti, documenti)
- [ ] Notifica admin per revisione manuale se necessario
- [ ] Certificato di cancellazione inviato via email

#### 3. Interface Utente
- [ ] Sezione "I miei dati GDPR" nel profilo utente
- [ ] Pulsante "Scarica i miei dati"
- [ ] Pulsante "Elimina il mio account"
- [ ] Storico richieste GDPR
- [ ] FAQ e informazioni legali

#### 4. Admin Interface
- [ ] Dashboard richieste GDPR pending
- [ ] Workflow approvazione/rigetto con motivazione
- [ ] Notifiche email automatiche
- [ ] Report mensili richieste GDPR

**Acceptance Criteria**:
- [ ] Utente può richiedere export dati in autonomia
- [ ] Export completo disponibile entro 24h
- [ ] Processo deletion con double opt-in funzionante
- [ ] Grace period 30 giorni implementato
- [ ] Email notifiche automatiche configurate
- [ ] Conformità GDPR verificata da legal team
- [ ] Documentazione utente e admin

**Estimated Effort**: 30-40 ore

---

## ⚙️ PRIORITÀ MEDIA

### Issue #5: Setup Docker e containerizzazione del progetto

**Labels**: `priority:medium`, `type:devops`, `infrastructure`

**Description**:
Implementare containerizzazione completa del progetto per semplificare sviluppo, testing e deployment.

**Tasks**:

#### Dockerfile Multi-Stage
- [ ] Stage `base`: dipendenze comuni Python
- [ ] Stage `development`: hot-reload, debug tools, test dependencies
- [ ] Stage `production`: ottimizzato, no dev deps, security hardened
- [ ] Gestione sicura secrets con build args
- [ ] User non-root per security
- [ ] Health checks endpoint

#### Docker Compose
- [ ] Service `web`: Django application (development/production profiles)
- [ ] Service `db`: PostgreSQL 15 con persistent volume
- [ ] Service `redis`: Redis per cache e Channels
- [ ] Service `mqtt`: Mosquitto broker per testing
- [ ] Service `nginx`: Reverse proxy con SSL
- [ ] Networks isolati (frontend, backend, database)
- [ ] Volumes per media files, static files, logs

#### Development Workflow
- [ ] `docker-compose.yml` per development
- [ ] `docker-compose.prod.yml` per production
- [ ] Hot-reload codice Python
- [ ] Debugger attachment support
- [ ] Script `make dev` per startup rapido

#### Documentation
- [ ] README.md aggiornato con Docker instructions
- [ ] Guida troubleshooting Docker
- [ ] Best practices per sviluppo con containers

**Acceptance Criteria**:
- [ ] `docker-compose up` avvia tutto il progetto funzionante
- [ ] Hot-reload funziona in development
- [ ] Production image < 500MB
- [ ] Health checks passano
- [ ] Documentazione completa

**Estimated Effort**: 16-24 ore

---

### Issue #6: Implementare CI/CD pipeline completa

**Labels**: `priority:medium`, `type:devops`, `automation`

**Description**:
Setup pipeline CI/CD per automated testing, quality checks e deployment.

**Pipeline Stages**:

#### 1. Continuous Integration (CI)
**Trigger**: ogni push, pull request

- [ ] **Lint & Format**
  - flake8 per PEP8 compliance
  - black per code formatting
  - isort per import sorting
  - pylint per code quality

- [ ] **Security Checks**
  - bandit per security issues
  - safety per vulnerable dependencies
  - secrets scanning (prevent commit secrets)

- [ ] **Testing**
  - python manage.py test
  - Coverage report (fail se < 80%)
  - Unit tests
  - Integration tests

- [ ] **Build**
  - Docker image build
  - Static files collection
  - Database migrations check (no conflicts)

#### 2. Continuous Deployment (CD)
**Trigger**: merge su main/master, manual per production

- [ ] **Staging Deployment** (automatico su main)
  - Deploy su ambiente staging
  - Smoke tests
  - Notifica Slack/Discord

- [ ] **Production Deployment** (manuale)
  - Approval workflow
  - Blue-green deployment
  - Database migrations
  - Health checks
  - Rollback automatico se fail

#### 3. Notification & Reporting
- [ ] Slack/Discord webhooks per build status
- [ ] Email su failure pipeline production
- [ ] Coverage badge nel README
- [ ] Build status badge

**Technology Stack**:
Opzioni da valutare:
- GitHub Actions (consigliato se GitHub)
- GitLab CI
- Jenkins
- CircleCI

**Tasks**:
- [ ] Creare `.github/workflows/ci.yml` (o equivalente)
- [ ] Creare `.github/workflows/cd-staging.yml`
- [ ] Creare `.github/workflows/cd-production.yml`
- [ ] Setup secrets in repository (DB_PASSWORD, SECRET_KEY, etc.)
- [ ] Configurare runners/agents
- [ ] Documentare processo e workflow

**Acceptance Criteria**:
- [ ] Pipeline CI esegue su ogni PR
- [ ] Test falliti bloccano merge
- [ ] Deploy staging automatico funzionante
- [ ] Deploy production con approval funzionante
- [ ] Notifiche configurate
- [ ] Documentazione completa

**Estimated Effort**: 24-32 ore

---

### Issue #7: Migliorare documentazione tecnica del progetto

**Labels**: `priority:medium`, `type:documentation`

**Description**:
La documentazione tecnica è incompleta. È necessario documentare API, architettura e processi.

**Tasks**:

#### 1. API Documentation (drf-yasg)
- [ ] Installare e configurare drf-yasg
- [ ] Endpoint Swagger UI: `/api/docs/`
- [ ] Endpoint ReDoc: `/api/redoc/`
- [ ] Documentare tutti gli endpoint REST con:
  - Description chiara
  - Request/response schemas
  - Examples
  - Authentication requirements
  - Error responses
- [ ] Export OpenAPI spec (YAML)

#### 2. Architecture Diagrams
- [ ] **Database Schema (ERD)**
  - Usare django-extensions: `python manage.py graph_models -a -o erd.png`
  - O strumento online (dbdiagram.io, draw.io)
  - Mostrare tutte le relazioni tra modelli

- [ ] **MQTT Message Flow**
  - Diagramma: Device → MQTT Broker → Django → Database
  - Topic structure e naming conventions
  - Message formats per vendor
  - Error handling flow

- [ ] **User Authentication Flow**
  - Registration con GDPR consent
  - Login/logout
  - Password reset
  - CER membership approval

- [ ] **Document Processing Pipeline**
  - Upload → Validation → Processing → Storage
  - GAUDI processor dettagli
  - Error handling e retry logic

#### 3. Developer Guides
- [ ] **Guida: Aggiungere nuovo vendor IoT**
  - Template device class
  - Implementare parse_message()
  - MQTT topic configuration
  - Testing checklist
  - Example completo (es. SMA inverter)

- [ ] **Guida: Deployment Production**
  - Prerequisiti server (OS, RAM, storage)
  - Step-by-step installation
  - Configuration best practices
  - SSL/TLS setup
  - Database optimization
  - Backup procedures
  - Monitoring setup
  - Troubleshooting common issues

- [ ] **Guida: Configurazione GSE**
  - Decreto CACER requirements
  - Come configurare portale GSE
  - Mapping dati CerCollettiva → GSE
  - Calcolo incentivi step-by-step
  - FAQ normativa

#### 4. Code Documentation
- [ ] Docstrings per tutte le classi e funzioni pubbliche
- [ ] Type hints (Python 3.10+ syntax)
- [ ] Comments per logica complessa
- [ ] README per ogni app Django

**Acceptance Criteria**:
- [ ] API docs accessibili e complete
- [ ] Tutti i diagrammi creati e nel repository
- [ ] Guide developer complete e testate
- [ ] Docstrings coverage > 80%
- [ ] Nuovi developer possono setup progetto in < 1 ora

**Estimated Effort**: 24-32 ore

---

### Issue #8: Dashboard real-time MQTT monitoring

**Labels**: `priority:medium`, `type:feature`, `monitoring`

**Description**:
Implementare dashboard per monitorare in tempo reale lo stato del sistema MQTT e dei dispositivi IoT.

**Features**:

#### 1. MQTT Broker Status
- [ ] Connection status (connected/disconnected)
- [ ] Uptime
- [ ] Last successful message timestamp
- [ ] Reconnection attempts count
- [ ] Current retry delay

#### 2. Message Statistics
- [ ] Messages received (last hour/day/week)
- [ ] Message rate (msg/second)
- [ ] Message latency (tempo tra publish e receive)
- [ ] Queue size (current/max)
- [ ] Buffer size (current/max)
- [ ] Dropped messages count

#### 3. Device Status
- [ ] Lista tutti i dispositivi con status
  - Online/Offline (based on last message)
  - Last seen timestamp
  - Message count
  - Error count
- [ ] Filtri per vendor, tipo, CER, stato
- [ ] Search by device name/serial

#### 4. Energy Production Real-Time
- [ ] Grafici live potenza prodotta (Chart.js)
- [ ] Aggiornamento ogni 5-10 secondi via WebSocket
- [ ] Aggregazione per CER
- [ ] Aggregazione per impianto
- [ ] Storico ultime 24h

#### 5. Alerts & Notifications
- [ ] Alert su dispositivi offline > 15 minuti
- [ ] Alert su error rate > threshold
- [ ] Alert su queue overflow
- [ ] Visual indicators (red/yellow/green)
- [ ] Email notifications (configurabile)

#### 6. Technical Implementation
- [ ] WebSocket consumer (`energy/consumers.py`)
- [ ] Channel groups per real-time updates
- [ ] Redis pub/sub integration
- [ ] Frontend JavaScript per WebSocket client
- [ ] Auto-reconnect WebSocket on disconnect
- [ ] Fallback polling se WebSocket non disponibile

**Acceptance Criteria**:
- [ ] Dashboard accessibile da menu admin
- [ ] Dati real-time con latency < 2 secondi
- [ ] Grafici responsive e user-friendly
- [ ] Alert funzionanti e configurabili
- [ ] Performance testata con 50+ dispositivi

**Estimated Effort**: 24-32 ore

---

### Issue #9: Sistema notifiche email automatiche

**Labels**: `priority:medium`, `type:feature`, `notifications`

**Description**:
Implementare sistema completo di notifiche email automatiche per eventi critici del sistema.

**Email Types**:

#### 1. Document Processing
- [ ] **Documento processato con successo**
  - Subject: "Documento GAUDI elaborato con successo"
  - Body: riepilogo dati estratti, link al documento
  - Template HTML professionale

- [ ] **Errore processamento documento**
  - Subject: "Errore nell'elaborazione del documento"
  - Body: descrizione errore, azioni suggerite
  - Link per ricaricamento

#### 2. Alerts Impianti
- [ ] **Impianto offline**
  - Subject: "Alert: Impianto [nome] offline"
  - Body: dettagli, ultimo messaggio ricevuto, troubleshooting
  - Severity: HIGH

- [ ] **Produzione anomala**
  - Subject: "Alert: Produzione impianto sotto soglia"
  - Body: grafici, dati storici, confronto media
  - Severity: MEDIUM

- [ ] **Errore dispositivo IoT**
  - Subject: "Alert: Errore dispositivo [nome]"
  - Body: tipo errore, impatto, azioni correttive

#### 3. Report CER
- [ ] **Report mensile CER**
  - Subject: "Report mensile CER [nome] - [mese/anno]"
  - Body: energia prodotta/consumata/condivisa, incentivi, grafici
  - Attachment PDF
  - Inviato a tutti i membri CER

- [ ] **Report trimestrale GSE**
  - Subject: "Report trimestrale per invio GSE"
  - Body: riepilogo dati, istruzioni invio portale GSE
  - Solo per admin CER

#### 4. User Management
- [ ] **Benvenuto nuovo utente**
  - Subject: "Benvenuto in CerCollettiva"
  - Body: guida primi passi, link utili, contatti supporto

- [ ] **Membership CER approvata**
  - Subject: "La tua richiesta di adesione è stata approvata"
  - Body: dettagli CER, prossimi step, link dashboard

- [ ] **Membership CER scaduta**
  - Subject: "Rinnovo membership CER"
  - Body: istruzioni rinnovo

#### 5. Technical Implementation
- [ ] Email templates HTML responsive (usando Django templates)
- [ ] CSS inline per compatibilità email clients
- [ ] Text version fallback
- [ ] Task queue (Celery) per invio asincrono
- [ ] Retry logic per SMTP failures
- [ ] Unsubscribe link (GDPR compliant)
- [ ] Email preferences per utente (quali email ricevere)
- [ ] Admin interface per preview templates
- [ ] Test email functionality nel admin

**Acceptance Criteria**:
- [ ] Tutti i tipi di email implementati e testati
- [ ] Templates professionali e brand-consistent
- [ ] Invio asincrono funzionante (no blocking)
- [ ] Unsubscribe preferences funzionanti
- [ ] Logging email inviate per audit
- [ ] Rate limiting per prevenire spam

**Estimated Effort**: 20-28 ore

---

### Issue #10: Completare admin interfaces per tutte le app

**Labels**: `priority:medium`, `type:enhancement`, `admin`

**Description**:
Attualmente solo `core/admin.py` è registrato. Le app `energy`, `documents` e `users` necessitano di admin interface complete.

**Tasks**:

#### 1. energy/admin.py
- [ ] Registrare modelli:
  - DeviceType (list_display: vendor, model, is_active)
  - Device (list_display: name, device_type, serial_number, plant, is_active)
  - DeviceConfiguration (inline con Device)
  - Measurement (list_display: device, timestamp, power_w, energy_kwh)
  - MQTTBroker (list_display: host, port, is_active)
  - MQTTAuditLog (list_display: timestamp, event_type, device, message)

- [ ] **Filtri avanzati**:
  - Device: per vendor, tipo, CER, status
  - Measurement: per device, date range, tipo misura
  - Audit log: per event type, severity, date range

- [ ] **Search fields**:
  - Device: name, serial_number
  - Measurement: device__name

- [ ] **Custom actions**:
  - Bulk activate/deactivate devices
  - Bulk delete old measurements (older than X months)
  - Export measurements to CSV
  - Test MQTT connection

- [ ] **Inline admins**:
  - Device → Measurements (ultimi 10)
  - Device → Configuration

#### 2. documents/admin.py
- [ ] Registrare modelli:
  - Document (list_display: type, plant, uploaded_by, uploaded_at, processing_status)

- [ ] **Preview documenti**:
  - Thumbnail per immagini
  - Link download per PDF
  - Preview inline se possibile

- [ ] **Filtri**:
  - Type, source, processing_status
  - Date range upload
  - Plant, CER

- [ ] **Custom actions**:
  - Riprocessa documenti GAUDI failed
  - Bulk download selected documents
  - Mark as reviewed/approved

- [ ] **Validazione**:
  - Check file size on upload
  - Validate file extension

#### 3. users/admin.py (miglioramenti)
- [ ] **Enhanced CustomUser admin**:
  - Fieldsets organizzati per tipo utente
  - Different fields visible based on legal_type
  - GDPR consents section
  - Membership CER inline

- [ ] **Filtri avanzati**:
  - Legal type, profit type
  - GDPR consents status
  - CER membership
  - Active/inactive
  - Date joined range

- [ ] **Custom actions**:
  - Export user data (GDPR compliance)
  - Send welcome email
  - Reset GDPR consents
  - Bulk activate/deactivate

#### 4. Global Improvements
- [ ] Custom admin site header/title
- [ ] Dashboard widgets con statistiche chiave
- [ ]Permissioning corretto (staff vs superuser)
- [ ] Audit trail for admin actions (django-simple-history)
- [ ] Admin docs enabled

**Acceptance Criteria**:
- [ ] Tutti i modelli principali hanno admin interface
- [ ] Filtri e search funzionanti
- [ ] Custom actions testate
- [ ] Preview documenti funzionante
- [ ] Performance testata con grandi dataset (1000+ records)

**Estimated Effort**: 16-24 ore

---

## 📋 PRIORITÀ BASSA (Backlog)

### Issue #11: Ottimizzazioni database e performance

**Labels**: `priority:low`, `type:optimization`, `performance`

**Description**:
Analizzare e ottimizzare performance database per supportare crescita del sistema.

**Tasks**:

#### 1. Slow Query Analysis
- [ ] Abilitare slow query log PostgreSQL
- [ ] Identificare query > 100ms
- [ ] Analizzare EXPLAIN ANALYZE per query problematiche
- [ ] Documentare findings

#### 2. Database Indexes
- [ ] Indici per foreign keys più usate
- [ ] Indici compositi per query comuni:
  - Measurement: (device_id, timestamp)
  - Document: (plant_id, type, uploaded_at)
  - Alert: (user_id, is_read, created_at)
- [ ] Partial indexes dove appropriato
- [ ] GIN indexes per JSONB fields

#### 3. Query Optimization
- [ ] select_related() per foreign keys
- [ ] prefetch_related() per reverse relations
- [ ] only()/defer() per campi non necessari
- [ ] Pagination per liste grandi
- [ ] Cached properties dove appropriato

#### 4. Database Maintenance
- [ ] Scheduled VACUUM ANALYZE
- [ ] Reindex schedule
- [ ] Table partitioning per Measurement (by timestamp)
- [ ] Archive old data (> 2 anni)

#### 5. Caching Strategy
- [ ] Redis caching per query frequenti
- [ ] Cache invalidation strategy
- [ ] Template fragment caching
- [ ] Low-level cache API per calcoli pesanti

**Acceptance Criteria**:
- [ ] Tutte le query < 50ms (95th percentile)
- [ ] Dashboard load time < 2 secondi
- [ ] Database size crescita lineare controllata
- [ ] Documentazione strategia caching

**Estimated Effort**: 20-30 ore

---

### Issue #12: Implementare OCR per documenti scansionati

**Labels**: `priority:low`, `type:feature`, `enhancement`

**Description**:
Aggiungere supporto OCR per estrarre testo da documenti GAUDI scansionati (immagini).

**Tasks**:
- [ ] Integrare Tesseract OCR
- [ ] Pre-processing immagini (deskew, denoise, threshold)
- [ ] Riconoscimento lingua italiana
- [ ] Fallback: se PDF ha testo, usa quello; altrimenti OCR
- [ ] Post-processing per pulizia testo OCR
- [ ] Confidence score per validazione
- [ ] UI per review manuale se confidence bassa
- [ ] Testing con campioni reali scansionati

**Acceptance Criteria**:
- [ ] OCR funziona su scansioni qualità media/alta
- [ ] Accuracy > 95% su font standard
- [ ] Fallback corretto PDF text vs OCR
- [ ] Performance accettabile (< 30 secondi per documento)

**Estimated Effort**: 16-24 ore

---

### Issue #13: Sistema checksum/hash per integrità documenti

**Labels**: `priority:low`, `type:feature`, `security`

**Description**:
Implementare sistema di verifica integrità documenti con hash crittografici.

**Tasks**:
- [ ] Calcolare SHA-256 hash al momento upload
- [ ] Salvare hash nel modello Document
- [ ] Verifica hash su ogni accesso al file
- [ ] Rilevamento documenti duplicati (stesso hash)
- [ ] Alert su modifica file (hash changed)
- [ ] Audit trail modifiche
- [ ] UI per verificare integrità documento

**Acceptance Criteria**:
- [ ] Hash calcolato per tutti i nuovi documenti
- [ ] Verifica integrità funzionante
- [ ] Detection duplicati implementata
- [ ] Alert su modifiche non autorizzate

**Estimated Effort**: 8-12 ore

---

### Issue #14: Ottimizzare Energy Calculator performance

**Labels**: `priority:low`, `type:optimization`, `performance`

**Description**:
Migliorare performance calcoli energetici per gestire grandi volumi di dati.

**Tasks**:
- [ ] Profiling con django-debug-toolbar
- [ ] Identificare bottleneck calcoli
- [ ] Caching più aggressivo (TTL ottimizzato)
- [ ] Query optimization (bulk operations)
- [ ] Async calculation per dataset grandi (Celery)
- [ ] Pre-calcolo aggregazioni giornaliere/mensili
- [ ] Materialized views per statistiche frequenti
- [ ] Testing con dataset 100k+ measurements

**Acceptance Criteria**:
- [ ] Calcolo incentivi mensili CER < 5 secondi
- [ ] Dashboard statistiche < 2 secondi
- [ ] Support 1M+ measurements senza degradazione
- [ ] Cache hit rate > 80%

**Estimated Effort**: 16-24 ore

---

### Issue #15: Dashboard pubblico CER con statistiche anonimizzate

**Labels**: `priority:low`, `type:feature`, `enhancement`

**Description**:
Creare dashboard pubblico accessibile senza login per mostrare impatto ambientale CER.

**Features**:
- [ ] Statistiche anonimizzate CER
  - Energia prodotta (totale, mensile)
  - CO2 risparmiata
  - Numero membri (anonimo)
  - Numero impianti (senza dettagli)
- [ ] Grafici interattivi (Chart.js)
  - Produzione nel tempo
  - Mix energetico
  - Impatto ambientale
- [ ] Mappa impianti (posizioni approssimate per privacy)
- [ ] Widget embeddable per siti esterni
- [ ] SEO optimized
- [ ] Mobile responsive

**Acceptance Criteria**:
- [ ] Nessun dato personale visibile
- [ ] Performance eccellente (< 1s load)
- [ ] Widget testato su siti esterni
- [ ] Analytics integrato

**Estimated Effort**: 20-28 ore

---

### Issue #16: App mobile o PWA per utenti CER

**Labels**: `priority:low`, `type:feature`, `mobile`

**Description**:
Sviluppare app mobile nativa o Progressive Web App per accesso utenti in mobilità.

**Options**:
1. **PWA** (Progressive Web App)
   - Pro: un solo codebase, web-based
   - Contro: alcune limitazioni native features

2. **React Native**
   - Pro: native performance, single codebase iOS/Android
   - Contro: richiede team con competenze React

3. **Flutter**
   - Pro: performance eccellenti, UI moderna
   - Contro: nuovo linguaggio (Dart)

**Features MVP**:
- [ ] Login/logout
- [ ] Dashboard personale
- [ ] Vista impianti utente
- [ ] Grafici produzione
- [ ] Notifiche push
- [ ] Scan QR code dispositivi
- [ ] Upload documenti con camera

**Tasks** (se PWA):
- [ ] Service worker per offline support
- [ ] Manifest.json
- [ ] Installable prompt
- [ ] Push notifications setup
- [ ] Responsive design ottimizzato mobile
- [ ] Testing su iOS/Android

**Estimated Effort**: 60-80 ore (MVP)

---

### Issue #17: Sistema previsione produzione con ML

**Labels**: `priority:low`, `type:feature`, `machine-learning`

**Description**:
Implementare sistema di previsione produzione energetica usando machine learning.

**Features**:
- [ ] Raccolta dati storici produzione
- [ ] Integrazione API meteo (OpenWeatherMap)
- [ ] Feature engineering (temperatura, irradiazione, stagione, etc.)
- [ ] Modello ML (es. Random Forest, LSTM)
- [ ] Training pipeline
- [ ] Prediction API endpoint
- [ ] Dashboard previsioni 7 giorni
- [ ] Alert su anomalie (produzione reale vs prevista)
- [ ] Re-training periodico automatico

**Technology Stack**:
- scikit-learn o TensorFlow
- Celery per training asincrono
- Redis per cache predictions

**Estimated Effort**: 60-80 ore

---

### Issue #18: Integrazione diretta portale GSE

**Labels**: `priority:low`, `type:feature`, `integration`

**Description**:
Integrare direttamente con portale GSE per import/export automatico dati.

**Note**: Dipende da disponibilità API GSE ufficiali.

**Tasks**:
- [ ] Ricerca API GSE disponibili
- [ ] Autenticazione (probabilmente SPID/CIE)
- [ ] Import dati energia condivisa
- [ ] Export report per GSE
- [ ] Validazione dati pre-invio
- [ ] Gestione errori e retry
- [ ] Audit log operazioni GSE
- [ ] Documentazione processo

**Estimated Effort**: 40-60 ore (se API disponibili)

---

### Issue #19: Refactoring - Separare requirements.txt per environment

**Labels**: `priority:low`, `type:refactoring`, `technical-debt`

**Description**:
Organizzare dipendenze in file separati per migliorare gestione e deploy.

**Structure**:
```
requirements/
├── base.txt          # Dipendenze comuni a tutti gli env
├── dev.txt           # Development only (debug toolbar, ipython, etc.)
├── prod.txt          # Production only (gunicorn, sentry-sdk, etc.)
└── test.txt          # Testing only (pytest, coverage, factory_boy, etc.)
```

**Tasks**:
- [ ] Creare directory `requirements/`
- [ ] Spostare dipendenze comuni in `base.txt`
- [ ] Identificare dev-only deps → `dev.txt`
- [ ] Identificare prod-only deps → `prod.txt`
- [ ] Creare `test.txt` con testing tools
- [ ] Aggiornare Dockerfile per usare requirements corretti
- [ ] Aggiornare documentazione
- [ ] Testare installazione in tutti gli environment

**Estimated Effort**: 4-6 ore

---

### Issue #20: Code review e refactoring legacy code

**Labels**: `priority:low`, `type:refactoring`, `technical-debt`

**Description**:
Identificare e risolvere code smells, migliorare qualità generale codebase.

**Tasks**:
- [ ] Setup pylint/flake8 con config strict
- [ ] Run sonarqube o code climate per analysis
- [ ] Identificare code smells:
  - Funzioni troppo lunghe (> 50 linee)
  - Complessità ciclomatica alta
  - Code duplication
  - Magic numbers
  - Poor naming
- [ ] Prioritize refactoring based on:
  - Frequenza modifiche file
  - Criticità componente
  - Bug history
- [ ] Refactoring incrementale:
  - Extract method
  - Rename variables/functions
  - Add type hints
  - Improve docstrings
  - Simplify conditionals
- [ ] Testing dopo ogni refactoring
- [ ] Documentare pattern e best practices

**Acceptance Criteria**:
- [ ] Pylint score > 8.0/10
- [ ] Nessuna funzione > 50 linee (salvo giustificazioni)
- [ ] Tutte le funzioni pubbliche con docstrings
- [ ] Code duplication < 3%

**Estimated Effort**: 40-60 ore (ongoing)

---

## 📝 Note per l'implementazione

### Come creare le issue su GitHub:

#### Metodo 1: Manualmente via Web UI
1. Vai su GitHub → Issues → New Issue
2. Copia titolo e descrizione da questo file
3. Aggiungi le label indicate
4. Assegna milestone se appropriato
5. Salva

#### Metodo 2: Via GitHub CLI (se disponibile localmente)
```bash
# Installa gh se non presente
# https://cli.github.com/

# Login
gh auth login

# Crea issue da questo file (esempio)
gh issue create \
  --title "Implementare test suite completo per il progetto" \
  --body-file issue-templates/issue-01.md \
  --label "priority:high,type:testing,technical-debt"
```

#### Metodo 3: Script Automatico
Puoi creare uno script bash che legge questo file e crea le issue automaticamente.

### Label da creare nel repository GitHub:

**Priorità**:
- `priority:high` (colore: rosso #d73a4a)
- `priority:medium` (colore: arancione #fbca04)
- `priority:low` (colore: verde #0e8a16)

**Tipo**:
- `type:testing` (colore: blu #0075ca)
- `type:security` (colore: rosso scuro #b60205)
- `type:feature` (colore: verde chiaro #a2eeef)
- `type:documentation` (colore: azzurro #0075ca)
- `type:devops` (colore: viola #5319e7)
- `type:refactoring` (colore: grigio #d4c5f9)
- `type:optimization` (colore: giallo #fef2c0)
- `type:enhancement` (colore: celeste #84b6eb)

**Altri**:
- `GDPR` (colore: rosso #d73a4a)
- `compliance` (colore: rosso #e99695)
- `technical-debt` (colore: marrone #c5def5)
- `infrastructure` (colore: grigio #d4c5f9)
- `monitoring` (colore: viola #5319e7)
- `admin` (colore: azzurro #1d76db)
- `mobile` (colore: verde #7057ff)
- `machine-learning` (colore: viola scuro #5319e7)

---

## 📊 Project Milestones (Suggeriti)

### Milestone 1: "Quality & Security" - 2 mesi
Issues: #1, #2, #3, #4
Goal: Portare testing a 80%, completare GDPR compliance

### Milestone 2: "DevOps & Infrastructure" - 1 mese
Issues: #5, #6, #7
Goal: CI/CD funzionante, Docker setup, documentazione completa

### Milestone 3: "Features & UX" - 2 mesi
Issues: #8, #9, #10
Goal: Dashboard monitoring, notifiche, admin completo

### Milestone 4: "Optimization & Future" - Ongoing
Issues: #11-20
Goal: Performance, features avanzate, technical debt

---

## 🎯 Priorità immediate (next 2 weeks)

Se devi scegliere da dove partire, consiglio:
1. **Issue #1** - Testing (critico per stabilità)
2. **Issue #2** - Encryption key security (vulnerabilità)
3. **Issue #5** - Docker (semplifica tutto il resto)
4. **Issue #6** - CI/CD (previene regressioni)

Dopo queste 4 issue, il progetto avrà fondamenta solide per crescere.

---

**Generated by**: CerCollettiva Project Analysis
**Date**: 2025-11-10
**Total Issues**: 20 (4 High, 6 Medium, 10 Low priority)
**Estimated Total Effort**: 500-700 ore
