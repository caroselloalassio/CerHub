from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.admin import admin_site

from . import documenso, services
from .models import Adesione


@admin.register(Adesione, site=admin_site)
class AdesioneAdmin(admin.ModelAdmin):
    list_display = ('numero', 'intestatario', 'tipo', 'pod', 'cer', 'stato', 'creata_il', 'firmata_il')
    list_filter = ('stato', 'tipo', 'cer')
    search_fields = ('nome', 'cognome', 'denominazione', 'email', 'pod', 'codice_fiscale', 'partita_iva')
    date_hierarchy = 'creata_il'
    actions = ('approva', 'non_accogliere', 'aggiorna_firma')
    readonly_fields = ('numero', 'file', 'token', 'stato', 'utente', 'firma_busta', 'firmata_il', 'creata_il',
                       'aggiornata_il', 'ip', 'user_agent', 'esito_il', 'esito_da')
    fieldsets = (
        ('Domanda', {'fields': ('numero', 'tipo', 'stato', 'file', 'cer', 'utente', 'note')}),
        ('Firmatario', {'fields': (('nome', 'cognome'), 'codice_fiscale', ('nascita_comune', 'nascita_provincia',
                                   'nascita_stato'), 'nascita_data', ('cellulare', 'email'))}),
        ('Residenza', {'fields': (('res_via', 'res_civico'), ('res_cap', 'res_comune', 'res_provincia'),
                                  'res_stato')}),
        ('Soggetto', {'fields': ('tipologia', 'qualita', 'denominazione', ('partita_iva', 'cf_ente'), 'ateco', 'pec',
                                 ('sede_via', 'sede_civico'), ('sede_cap', 'sede_comune', 'sede_provincia'),
                                 'sede_stato', 'studio_associato', 'account_gse')}),
        ('Contatore', {'fields': ('pod', 'potenza_impegnata', 'tensione', 'generazione', 'fasi')}),
        ('Riferimenti catastali', {'fields': (('cat_sezione', 'cat_foglio', 'cat_particella', 'cat_subalterno'),
                                              ('cat_indirizzo', 'cat_civico'),
                                              ('cat_cap', 'cat_comune', 'cat_provincia'))}),
        ('Accredito', {'fields': ('iban',)}),
        ('Tracciamento', {'classes': ('collapse',), 'fields': (
            'token', 'firma_busta', 'firmata_il', 'creata_il', 'aggiornata_il', 'ip', 'user_agent', 'esito_il',
            'esito_da')}),
    )

    def has_add_permission(self, request):
        return False  # le domande nascono solo dal modulo online

    def get_readonly_fields(self, request, obj=None):
        campi = list(super().get_readonly_fields(request, obj))
        if obj and not obj.da_firmare:
            # dopo la firma i dati dichiarati non si toccano più: restano modificabili solo
            # configurazione e note interne
            modificabili = {'cer', 'note'}
            campi += [f.name for f in obj._meta.fields if f.name not in modificabili and f.name not in campi]
        return campi

    @admin.display(description='Numero')
    def numero(self, obj):
        return obj.numero

    @admin.display(description='Aderente')
    def intestatario(self, obj):
        return obj.intestatario

    @admin.display(description='File')
    def file(self, obj):
        voci = [('firmata', 'Domanda firmata', obj.pdf_firmato), ('domanda', 'Domanda (non firmata)', obj.pdf_modulo),
                ('documento-fronte', 'Documento – fronte', obj.doc_fronte),
                ('documento-retro', 'Documento – retro', obj.doc_retro)]
        return format_html_join(
            ' · ', '<a href="{}" target="_blank" rel="noopener">{}</a>',
            ((reverse('adesioni:documento', args=[obj.token, chiave]), etichetta)
             for chiave, etichetta, campo in voci if campo)) or '—'

    def _esito(self, request, queryset, stato, verbo):
        fatte = 0
        for adesione in queryset:
            if adesione.stato not in (Adesione.FIRMATA, Adesione.APPROVATA, Adesione.RIFIUTATA):
                self.message_user(request, f'{adesione.numero}: non ancora firmata, esito non registrato.',
                                  messages.WARNING)
                continue
            if adesione.stato == stato:
                continue
            adesione.stato = stato
            adesione.esito_il = timezone.now()
            adesione.esito_da = request.user
            adesione.save()
            try:
                services.invia_mail_esito(adesione)
            except Exception as exc:  # l'esito resta registrato
                self.message_user(request, f'{adesione.numero}: email all\'aderente non inviata ({exc}).',
                                  messages.WARNING)
            fatte += 1
        if fatte:
            self.message_user(request, f'Domande {verbo}: {fatte}. Gli aderenti sono stati avvisati per email.')

    @admin.action(description='Accogli le domande selezionate (avvisa l\'aderente)')
    def approva(self, request, queryset):
        self._esito(request, queryset, Adesione.APPROVATA, 'accolte')

    @admin.action(description='Non accogliere le domande selezionate (avvisa l\'aderente)')
    def non_accogliere(self, request, queryset):
        self._esito(request, queryset, Adesione.RIFIUTATA, 'non accolte')

    @admin.action(description='Controlla lo stato della firma')
    def aggiorna_firma(self, request, queryset):
        if not documenso.configurato():
            self.message_user(request, 'Servizio di firma non configurato.', messages.ERROR)
            return
        firmate = 0
        for adesione in queryset.filter(stato=Adesione.IN_FIRMA):
            try:
                if services.sincronizza(adesione.pk).stato == Adesione.FIRMATA:
                    firmate += 1
            except documenso.ErroreFirma as exc:
                self.message_user(request, f'{adesione.numero}: {exc}', messages.WARNING)
        self.message_user(request, f'Controllo completato: {firmate} domande risultano ora firmate.')

    def delete_model(self, request, obj):
        services.elimina(obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            services.elimina(obj)
