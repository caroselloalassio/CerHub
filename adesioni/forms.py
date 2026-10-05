from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from core.models import CERConfiguration

from . import validators as v
from .models import Adesione

DIMENSIONE_MASSIMA = 12 * 1024 * 1024  # 12 MB per foto

DICHIARAZIONI = {
    'dich_esclusioni': 'Dichiaro che non sussistono le cause di esclusione dall’accesso agli incentivi di cui '
                       'all’art. 3 comma 3 lettere (a) (b) (c) (d) del Decreto CACER.',
    'dich_no_incentivi': 'Dichiaro che alla data odierna il punto di connessione associato al Codice POD non '
                         'risulta già beneficiario degli incentivi previsti dal Decreto CACER.',
    'dich_no_ssp': 'Dichiaro che alla data odierna sul punto di connessione associato al Codice POD non risulta '
                   'attivo il servizio di Scambio Sul Posto.',
    'dich_pmi': 'Dichiaro di appartenere alla categoria delle piccole medie imprese (“PMI”): meno di 250 occupati '
                'e fatturato annuo non superiore a 50 milioni di euro, oppure totale di bilancio annuo non '
                'superiore a 43 milioni di euro.',
    'dich_statuto': 'Dichiaro di avere preso visione dello Statuto e del Regolamento della Comunità Energetica '
                    'Rinnovabile, di approvarli in ogni loro parte, di condividerne principi e finalità e di '
                    'impegnarmi a rispettare le disposizioni statutarie vigenti e le delibere degli organi sociali.',
    'dich_dati': 'Acconsento al trattamento dei dati personali e di consumo relativi alla fornitura di energia '
                 'elettrica del POD indicato, da parte della Comunità Energetica Rinnovabile e di terzi da questa '
                 'incaricati, per le finalità della Comunità e secondo l’informativa (Allegato B della domanda).',
    'dich_variazioni': 'Mi impegno a comunicare prontamente alla Comunità Energetica Rinnovabile eventuali '
                       'cambiamenti rispetto alle informazioni e dichiarazioni rilasciate (es. sostituzione del '
                       'contatore, variazione del conto corrente, cause di esclusione dagli incentivi).',
}

MAIUSCOLI = ('codice_fiscale', 'pod', 'iban', 'partita_iva', 'cf_ente', 'nascita_provincia', 'res_provincia',
             'sede_provincia', 'cat_provincia')


class FotoDocumento(forms.ImageField):
    widget = forms.ClearableFileInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.widget = forms.FileInput(attrs={'accept': 'image/*',
                                             'class': 'form-control'})

    def clean(self, data, initial=None):
        f = super().clean(data, initial)
        if f and hasattr(f, 'size') and f.size > DIMENSIONE_MASSIMA:
            raise ValidationError('La foto è troppo pesante (massimo 12 MB).')
        return f


class AdesioneBaseForm(forms.ModelForm):
    doc_fronte = FotoDocumento(label='Documento d’identità – fronte')
    doc_retro = FotoDocumento(label='Documento d’identità – retro')
    # trappola per i compilatori automatici: deve restare vuoto
    sito_web = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    obbligatori = ()
    dichiarazioni = ('dich_esclusioni', 'dich_no_incentivi', 'dich_no_ssp', 'dich_statuto', 'dich_dati',
                     'dich_variazioni')

    class Meta:
        model = Adesione
        fields = [
            'nome', 'cognome', 'nascita_comune', 'nascita_provincia', 'nascita_stato', 'nascita_data',
            'cellulare', 'email', 'codice_fiscale', 'account_gse',
            'pod', 'potenza_impegnata', 'tensione', 'generazione', 'fasi',
            'cat_sezione', 'cat_foglio', 'cat_particella', 'cat_subalterno', 'cat_indirizzo', 'cat_civico',
            'cat_comune', 'cat_cap', 'cat_provincia',
            'cer', 'iban',
            'dich_esclusioni', 'dich_no_incentivi', 'dich_no_ssp', 'dich_pmi', 'dich_statuto', 'dich_dati',
            'dich_variazioni',
        ]
        localized_fields = ('potenza_impegnata',)  # accetta la virgola decimale
        widgets = {
            'nascita_data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'tensione': forms.RadioSelect, 'generazione': forms.RadioSelect, 'fasi': forms.RadioSelect,
            'account_gse': forms.RadioSelect(choices=[(True, 'Sì'), (False, 'No')]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        modifica = bool(self.instance and self.instance.pk)
        self.fields['cer'].queryset = CERConfiguration.objects.filter(is_active=True).order_by('name')
        self.fields['cer'].required = False
        self.fields['cer'].empty_label = 'Non lo so: la assegna CER Hub in base al mio POD'
        self.fields['cer'].label_from_instance = lambda c: f'{c.name} (cabina primaria {c.primary_substation})'
        self.fields['cer'].label = 'Configurazione a cui chiedi di aderire'
        self.fields['account_gse'].required = False
        # scelte senza la voce vuota "---------"
        self.fields['tensione'].choices = Adesione.TENSIONI
        self.fields['generazione'].choices = Adesione.GENERAZIONI
        self.fields['fasi'].choices = Adesione.FASI
        self.fields['nascita_provincia'].help_text = 'Sigla, es. SV. Lascia vuoto se nato all’estero.'
        self.fields['pod'].help_text = 'Lo trovi sulla bolletta dell’energia elettrica: inizia con “IT”.'
        self.fields['potenza_impegnata'].help_text = 'In kW, come indicato in bolletta (es. 3 oppure 4,5).'
        self.fields['iban'].help_text = 'Del conto intestato al titolare del POD, per l’accredito degli eventuali contributi.'
        self.fields['cat_sezione'].help_text = 'Facoltativa.'
        self.fields['cat_subalterno'].help_text = 'Di solito indicato come “sub”.'
        for nome in self.obbligatori:
            self.fields[nome].required = True
        for nome in self.dichiarazioni:
            self.fields[nome].required = True
            self.fields[nome].label = DICHIARAZIONI[nome]
            self.fields[nome].error_messages['required'] = 'Questa dichiarazione è obbligatoria.'
        if 'dich_pmi' in self.fields:
            self.fields['dich_pmi'].label = DICHIARAZIONI['dich_pmi']
            self.fields['dich_pmi'].required = False
        if modifica:  # le foto già caricate restano, se non vengono sostituite
            self.fields['doc_fronte'].required = False
            self.fields['doc_retro'].required = False
        for nome, campo in self.fields.items():
            w = campo.widget
            if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
                w.attrs['class'] = 'form-check-input'
                continue
            classe = 'form-select' if isinstance(w, forms.Select) else 'form-control'
            w.attrs['class'] = (w.attrs.get('class', '') + ' ' + classe).strip() if classe not in w.attrs.get('class', '') else w.attrs['class']
            if nome in MAIUSCOLI:
                w.attrs['style'] = 'text-transform:uppercase'
            if nome.endswith('_provincia'):
                w.attrs['maxlength'] = 2
            if nome.endswith('_cap'):
                w.attrs.update({'maxlength': 5, 'inputmode': 'numeric'})
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['cellulare'].widget.attrs.update({'autocomplete': 'tel', 'inputmode': 'tel'})

    # --- pulizia dei singoli campi -------------------------------------------
    def _maiuscolo(self, nome):
        return v.normalizza(self.cleaned_data.get(nome))

    def clean_sito_web(self):
        if self.cleaned_data.get('sito_web'):
            raise ValidationError('Richiesta non valida.')
        return ''

    def clean_codice_fiscale(self):
        cf = self._maiuscolo('codice_fiscale')
        v.valida_codice_fiscale(cf)
        return cf

    def clean_pod(self):
        pod = self._maiuscolo('pod')
        v.valida_pod(pod)
        return pod

    def clean_iban(self):
        iban = self._maiuscolo('iban')
        v.valida_iban(iban)
        return iban

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_nascita_data(self):
        d = self.cleaned_data['nascita_data']
        oggi = date.today()
        eta = oggi.year - d.year - ((oggi.month, oggi.day) < (d.month, d.day))
        if d > oggi or eta > 120:
            raise ValidationError('Data di nascita non valida.')
        if eta < 18:
            raise ValidationError('Per presentare la domanda bisogna essere maggiorenni.')
        return d

    def clean_potenza_impegnata(self):
        p = self.cleaned_data['potenza_impegnata']
        if p <= 0 or p > 100000:
            raise ValidationError('Indica la potenza impegnata in kW.')
        return p

    def clean_account_gse(self):
        return bool(self.cleaned_data.get('account_gse'))

    def _provincia(self, nome, obbligatoria=True):
        p = self._maiuscolo(nome)
        if not p and not obbligatoria:
            return ''
        if len(p) != 2 or not p.isalpha():
            raise ValidationError('Indica la sigla della provincia (2 lettere).')
        return p

    def clean_nascita_provincia(self):
        return self._provincia('nascita_provincia', obbligatoria=False)

    def clean_cat_provincia(self):
        return self._provincia('cat_provincia')

    def clean_cat_cap(self):
        v.valida_cap(self.cleaned_data.get('cat_cap'))
        return self.cleaned_data['cat_cap'].strip()

    def _richiedi(self, dati, nomi):
        for nome in nomi:
            if not dati.get(nome) and nome not in self.errors:
                self.add_error(nome, 'Campo obbligatorio.')

    def _sede(self, dati):
        """Controlli su sede legale e partita IVA (ditte individuali e società)."""
        self._richiedi(dati, ['sede_comune', 'sede_via', 'sede_civico', 'sede_cap', 'sede_provincia', 'sede_stato'])
        if dati.get('sede_cap'):
            try:
                v.valida_cap(dati['sede_cap'])
            except ValidationError as e:
                self.add_error('sede_cap', e)
        prov = v.normalizza(dati.get('sede_provincia'))
        if prov and (len(prov) != 2 or not prov.isalpha()):
            self.add_error('sede_provincia', 'Indica la sigla della provincia (2 lettere).')
        dati['sede_provincia'] = prov
        if dati.get('partita_iva'):
            dati['partita_iva'] = v.normalizza(dati['partita_iva'])
            try:
                v.valida_partita_iva(dati['partita_iva'])
            except ValidationError as e:
                self.add_error('partita_iva', e)


class AdesionePrivatoForm(AdesioneBaseForm):
    obbligatori = ('res_comune', 'res_via', 'res_civico', 'res_cap', 'res_provincia', 'res_stato')

    class Meta(AdesioneBaseForm.Meta):
        fields = AdesioneBaseForm.Meta.fields + [
            'res_comune', 'res_via', 'res_civico', 'res_cap', 'res_provincia', 'res_stato',
            'tipologia', 'sede_comune', 'sede_via', 'sede_civico', 'sede_cap', 'sede_provincia', 'sede_stato',
            'partita_iva', 'ateco',
        ]
        widgets = {**AdesioneBaseForm.Meta.widgets, 'tipologia': forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['dich_pmi']
        self.fields['tipologia'].choices = [c for c in Adesione.TIPOLOGIE if c[0] in (Adesione.PERSONA, Adesione.DITTA)]
        self.fields['tipologia'].choices = [
            (Adesione.PERSONA, 'Persona fisica (altre persone individuali)'),
            (Adesione.DITTA, 'Imprenditore / Ditta individuale / Impresa agricola'),
        ]
        self.fields['sede_stato'].label = 'Nazione'
        if not self.is_bound and not self.instance.pk:
            self.fields['tipologia'].initial = Adesione.PERSONA

    def clean_res_provincia(self):
        return self._provincia('res_provincia')

    def clean_res_cap(self):
        v.valida_cap(self.cleaned_data.get('res_cap'))
        return self.cleaned_data['res_cap'].strip()

    def clean(self):
        dati = super().clean()
        if dati.get('tipologia') == Adesione.DITTA:
            self._richiedi(dati, ['partita_iva', 'ateco'])
            self._sede(dati)
        else:
            for nome in ('sede_comune', 'sede_via', 'sede_civico', 'sede_cap', 'sede_provincia', 'partita_iva',
                         'ateco'):
                dati[nome] = ''
        return dati

    def save(self, commit=True):
        self.instance.tipo = Adesione.PRIVATO
        return super().save(commit)


class AdesioneAziendaForm(AdesioneBaseForm):
    obbligatori = ('qualita', 'denominazione', 'ateco', 'pec', 'sede_comune', 'sede_via', 'sede_civico',
                   'sede_cap', 'sede_provincia', 'sede_stato')

    class Meta(AdesioneBaseForm.Meta):
        fields = AdesioneBaseForm.Meta.fields + [
            'qualita', 'denominazione', 'partita_iva', 'cf_ente', 'ateco', 'pec',
            'sede_comune', 'sede_via', 'sede_civico', 'sede_cap', 'sede_provincia', 'sede_stato',
            'tipologia', 'studio_associato',
        ]
        widgets = {
            **AdesioneBaseForm.Meta.widgets,
            'tipologia': forms.RadioSelect, 'qualita': forms.RadioSelect,
            'studio_associato': forms.RadioSelect(choices=[(True, 'Sì'), (False, 'No')]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipologia'].choices = [c for c in Adesione.TIPOLOGIE if c[0] in (Adesione.PMI, Adesione.ASSOCIAZIONE)]
        self.fields['qualita'].choices = Adesione.QUALITA
        self.fields['studio_associato'].required = False
        self.fields['denominazione'].label = 'Società/Associazione denominata'
        self.fields['sede_comune'].label = 'Sede nel Comune di'
        self.fields['partita_iva'].help_text = 'Indica la partita IVA, il codice fiscale o entrambi.'
        self.fields['pec'].help_text = 'Posta elettronica certificata della società/associazione.'
        self.fields['codice_fiscale'].label = 'Codice fiscale del firmatario'
        if not self.is_bound and not self.instance.pk:
            self.fields['qualita'].initial = 'RAPPRESENTANTE'

    def clean_studio_associato(self):
        return bool(self.cleaned_data.get('studio_associato'))

    def clean_cf_ente(self):
        cf = self._maiuscolo('cf_ente')
        if cf:
            v.valida_cf_ente(cf)
        return cf

    def clean(self):
        dati = super().clean()
        self._sede(dati)
        if not dati.get('partita_iva') and not dati.get('cf_ente') and 'cf_ente' not in self.errors:
            self.add_error('partita_iva', 'Indica la partita IVA oppure il codice fiscale della società/associazione.')
        if dati.get('tipologia') == Adesione.PMI and not dati.get('dich_pmi'):
            self.add_error('dich_pmi', 'Questa dichiarazione è obbligatoria per le PMI.')
        if dati.get('tipologia') != Adesione.PMI:
            dati['dich_pmi'] = False
        return dati

    def save(self, commit=True):
        self.instance.tipo = Adesione.AZIENDA
        return super().save(commit)
