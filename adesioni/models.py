"""Domande di adesione online alla Comunità Energetica Rinnovabile "CER Hub"."""
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField


def _percorso(instance, filename, nome):
    return f'adesioni/{instance.token}/{nome}'


def percorso_fronte(instance, filename):
    return _percorso(instance, filename, 'documento-fronte.jpg')


def percorso_retro(instance, filename):
    return _percorso(instance, filename, 'documento-retro.jpg')


def percorso_modulo(instance, filename):
    return _percorso(instance, filename, 'domanda-di-adesione.pdf')


def percorso_firmato(instance, filename):
    return _percorso(instance, filename, 'domanda-di-adesione-firmata.pdf')


class Adesione(models.Model):
    PRIVATO = 'PRIVATO'
    AZIENDA = 'AZIENDA'
    TIPI = [
        (PRIVATO, 'Privato o ditta individuale'),
        (AZIENDA, 'Azienda o associazione'),
    ]

    COMPILATA = 'COMPILATA'
    IN_FIRMA = 'IN_FIRMA'
    FIRMATA = 'FIRMATA'
    APPROVATA = 'APPROVATA'
    RIFIUTATA = 'RIFIUTATA'
    STATI = [
        (COMPILATA, 'Compilata, da firmare'),
        (IN_FIRMA, 'Firma in corso'),
        (FIRMATA, 'Firmata, in attesa di approvazione'),
        (APPROVATA, 'Approvata'),
        (RIFIUTATA, 'Non accolta'),
    ]

    PERSONA = 'PERSONA'
    DITTA = 'DITTA'
    PMI = 'PMI'
    ASSOCIAZIONE = 'ASSOCIAZIONE'
    TIPOLOGIE = [
        (PERSONA, 'Altre persone individuali'),
        (DITTA, 'Imprenditore / Ditta individuale / Impresa agricola'),
        (PMI, 'PMI'),
        (ASSOCIAZIONE, 'Associazione con personalità giuridica di diritto privato'),
    ]

    QUALITA = [
        ('RAPPRESENTANTE', 'Rappresentante legale'),
        ('PROCURATORE', 'Procuratore'),
    ]
    TENSIONI = [
        ('BT', 'Bassa Tensione (BT), fino a 999 V'),
        ('MT', 'Media Tensione (MT), da 1000 V a 15000 V'),
    ]
    GENERAZIONI = [
        ('2G', 'Seconda generazione (2G)'),
        ('1G', 'Prima generazione (1G)'),
    ]
    FASI = [
        ('MONO', 'Monofase (230 V)'),
        ('TRI', 'Trifase (400 V)'),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField('Tipo di adesione', max_length=10, choices=TIPI)
    stato = models.CharField('Stato', max_length=12, choices=STATI, default=COMPILATA)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='adesioni', verbose_name='Utente')

    # --- Firmatario ---------------------------------------------------------
    nome = models.CharField('Nome', max_length=100)
    cognome = models.CharField('Cognome', max_length=100)
    nascita_comune = models.CharField('Comune di nascita', max_length=100)
    nascita_provincia = models.CharField('Provincia di nascita', max_length=2, blank=True)
    nascita_stato = models.CharField('Stato di nascita', max_length=60, default='Italia')
    nascita_data = models.DateField('Data di nascita')
    cellulare = models.CharField('Cellulare', max_length=20)
    email = models.EmailField('E-mail')
    codice_fiscale = models.CharField('Codice fiscale', max_length=16)

    # --- Residenza (privati) ------------------------------------------------
    res_comune = models.CharField('Comune di residenza', max_length=100, blank=True)
    res_via = models.CharField('Via', max_length=150, blank=True)
    res_civico = models.CharField('N. civico', max_length=10, blank=True)
    res_cap = models.CharField('CAP', max_length=5, blank=True)
    res_provincia = models.CharField('Provincia', max_length=2, blank=True)
    res_stato = models.CharField('Stato', max_length=60, blank=True, default='Italia')

    # --- Soggetto -----------------------------------------------------------
    tipologia = models.CharField('Tipologia di soggetto', max_length=12, choices=TIPOLOGIE)
    qualita = models.CharField('In qualità di', max_length=14, choices=QUALITA, blank=True)
    denominazione = models.CharField('Denominazione', max_length=255, blank=True)
    partita_iva = models.CharField('Partita IVA', max_length=11, blank=True)
    cf_ente = models.CharField('Codice fiscale della società/associazione', max_length=16, blank=True)
    ateco = models.CharField('Codice ATECO prevalente', max_length=12, blank=True)
    pec = models.EmailField('PEC', blank=True)
    sede_comune = models.CharField('Comune della sede legale', max_length=100, blank=True)
    sede_via = models.CharField('Via', max_length=150, blank=True)
    sede_civico = models.CharField('N. civico', max_length=10, blank=True)
    sede_cap = models.CharField('CAP', max_length=5, blank=True)
    sede_provincia = models.CharField('Provincia', max_length=2, blank=True)
    sede_stato = models.CharField('Stato', max_length=60, blank=True, default='Italia')
    studio_associato = models.BooleanField('Studio associato o società di professionisti', default=False)
    account_gse = models.BooleanField('Già iscritto con proprio account sulla piattaforma del GSE', default=False)

    # --- Contatore ----------------------------------------------------------
    pod = models.CharField('Codice POD', max_length=16)
    potenza_impegnata = models.DecimalField('Potenza impegnata (kW)', max_digits=8, decimal_places=2)
    tensione = models.CharField('Tensione di connessione', max_length=2, choices=TENSIONI)
    generazione = models.CharField('Generazione del contatore', max_length=2, choices=GENERAZIONI)
    fasi = models.CharField('Numero di fasi', max_length=4, choices=FASI)

    # --- Riferimenti catastali ---------------------------------------------
    cat_sezione = models.CharField('Sezione', max_length=10, blank=True)
    cat_foglio = models.CharField('Foglio', max_length=10)
    cat_particella = models.CharField('Particella', max_length=10)
    cat_subalterno = models.CharField('Subalterno', max_length=10)
    cat_indirizzo = models.CharField('Indirizzo', max_length=150)
    cat_civico = models.CharField('Numero civico', max_length=10)
    cat_comune = models.CharField('Comune', max_length=100)
    cat_cap = models.CharField('CAP', max_length=5)
    cat_provincia = models.CharField('Provincia', max_length=2)

    # --- Configurazione e pagamento ----------------------------------------
    cer = models.ForeignKey(
        'core.CERConfiguration', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='adesioni_online', verbose_name='Configurazione')
    iban = EncryptedCharField('IBAN', max_length=34)

    # --- Dichiarazioni (tutte obbligatorie nel modulo) ---------------------
    dich_esclusioni = models.BooleanField(default=False)
    dich_no_incentivi = models.BooleanField(default=False)
    dich_no_ssp = models.BooleanField(default=False)
    dich_pmi = models.BooleanField(default=False)
    dich_statuto = models.BooleanField(default=False)
    dich_dati = models.BooleanField(default=False)
    dich_variazioni = models.BooleanField(default=False)

    # --- File ---------------------------------------------------------------
    doc_fronte = models.FileField('Documento d\'identità (fronte)', upload_to=percorso_fronte, max_length=255)
    doc_retro = models.FileField('Documento d\'identità (retro)', upload_to=percorso_retro, max_length=255)
    pdf_modulo = models.FileField('Domanda da firmare', upload_to=percorso_modulo, max_length=255, blank=True)
    pdf_firmato = models.FileField('Domanda firmata', upload_to=percorso_firmato, max_length=255, blank=True)

    # --- Firma elettronica (Documenso) -------------------------------------
    firma_busta = models.CharField('Identificativo della busta di firma', max_length=100, blank=True)
    firma_url = models.URLField('Indirizzo di firma', max_length=500, blank=True)
    firma_pagina = models.PositiveSmallIntegerField(default=0)
    firma_x = models.FloatField(default=0)
    firma_y = models.FloatField(default=0)
    firma_l = models.FloatField(default=0)
    firma_h = models.FloatField(default=0)
    firmata_il = models.DateTimeField('Firmata il', null=True, blank=True)

    # --- Tracciamento -------------------------------------------------------
    creata_il = models.DateTimeField('Creata il', auto_now_add=True)
    aggiornata_il = models.DateTimeField(auto_now=True)
    ip = models.GenericIPAddressField('Indirizzo IP', null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    esito_il = models.DateTimeField('Esito registrato il', null=True, blank=True)
    esito_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Esito registrato da')
    note = models.TextField('Note interne', blank=True)

    class Meta:
        verbose_name = 'Domanda di adesione'
        verbose_name_plural = 'Domande di adesione'
        ordering = ['-creata_il']
        indexes = [
            models.Index(fields=['stato']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f'{self.intestatario} – {self.get_stato_display()}'

    # --- Comodità -----------------------------------------------------------
    @property
    def is_azienda(self):
        return self.tipo == self.AZIENDA

    @property
    def nome_completo(self):
        return f'{self.nome} {self.cognome}'.strip()

    @property
    def intestatario(self):
        """Soggetto che aderisce: la società/associazione oppure la persona."""
        return self.denominazione if self.is_azienda and self.denominazione else self.nome_completo

    @property
    def firmata(self):
        return self.stato in (self.FIRMATA, self.APPROVATA, self.RIFIUTATA) and bool(self.pdf_firmato)

    @property
    def da_firmare(self):
        return self.stato in (self.COMPILATA, self.IN_FIRMA)

    @property
    def numero(self):
        return f'AD-{self.creata_il:%Y}-{self.pk:04d}' if self.pk and self.creata_il else ''

    def get_absolute_url(self):
        return reverse('adesioni:riepilogo', args=[self.token])

    def segna_firmata(self):
        self.stato = self.FIRMATA
        self.firmata_il = self.firmata_il or timezone.now()
