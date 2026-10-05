"""Generazione del PDF della domanda di adesione (da firmare elettronicamente).

Il testo ricalca i moduli dell'associazione ("Domanda di Adesione" per privati
e per società/associazioni) con gli allegati A, B e C.
"""
import io
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

VERDE = colors.HexColor('#00796b')
GRIGIO = colors.HexColor('#555555')
BORDO = colors.HexColor('#c9d6d2')
FONDO = colors.HexColor('#f1f7f5')

ASSOCIAZIONE = {
    'nome': 'CER Hub',
    'cf': '90076120097',
    'sede': 'viale Martiri della Libertà 6, 17031 Albenga (SV)',
    'email': 'info@cerhub.it',
}

BASE = ParagraphStyle('base', fontName='Helvetica', fontSize=9.5, leading=13, alignment=TA_JUSTIFY)
PICCOLO = ParagraphStyle('piccolo', parent=BASE, fontSize=8.5, leading=11.5)
MINUTO = ParagraphStyle('minuto', parent=BASE, fontSize=8, leading=10.4)
ETICHETTA = ParagraphStyle('etichetta', parent=BASE, fontSize=8, leading=10, textColor=GRIGIO, alignment=0)
VALORE = ParagraphStyle('valore', parent=BASE, fontName='Helvetica-Bold', alignment=0)
TITOLO = ParagraphStyle('titolo', parent=BASE, fontName='Helvetica-Bold', fontSize=15, leading=19,
                        alignment=TA_CENTER, textColor=VERDE)
SOTTOTITOLO = ParagraphStyle('sottotitolo', parent=BASE, fontSize=11, leading=14, alignment=TA_CENTER)
SEZIONE = ParagraphStyle('sezione', parent=BASE, fontName='Helvetica-Bold', fontSize=10.5, leading=14,
                         textColor=VERDE, spaceBefore=8, spaceAfter=4, alignment=0)
CENTRATO = ParagraphStyle('centrato', parent=BASE, fontName='Helvetica-Bold', fontSize=11, alignment=TA_CENTER,
                          spaceBefore=8, spaceAfter=6)


class Spunta(Flowable):
    """Casella spuntata disegnata a mano (non dipende dai caratteri del lettore PDF)."""
    lato = 3.1 * mm

    def wrap(self, *args):
        return self.lato, self.lato + 1.2 * mm

    def draw(self):
        c, l = self.canv, self.lato
        c.setStrokeColor(VERDE)
        c.setLineWidth(0.8)
        c.rect(0, 0, l, l)
        c.setLineWidth(1.3)
        c.setLineCap(1)
        p = c.beginPath()
        p.moveTo(l * 0.2, l * 0.52)
        p.lineTo(l * 0.42, l * 0.25)
        p.lineTo(l * 0.82, l * 0.8)
        c.drawPath(p)


def _p(testo, stile=BASE):
    return Paragraph(testo, stile)


def _e(valore):
    return escape(str(valore)) if valore not in (None, '') else '—'


class RiquadroFirma(Flowable):
    """Riquadro vuoto per la firma: registra pagina e posizione per Documenso."""

    def __init__(self, larghezza=80 * mm, altezza=24 * mm):
        super().__init__()
        self.width = larghezza
        self.height = altezza
        self.posizione = None  # (pagina, x, y, larghezza, altezza) in punti, origine in basso a sinistra

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(BORDO)
        c.setDash(2, 2)
        c.rect(0, 0, self.width, self.height)
        x, y = c.absolutePosition(0, 0)
        self.posizione = (c.getPageNumber(), x, y, self.width, self.height)


def _griglia(righe, larghezze):
    """Tabella di coppie etichetta/valore: ogni cella è (etichetta, valore)."""
    dati = []
    for riga in righe:
        dati.append([[_p(escape(et), ETICHETTA), _p(_e(val), VALORE)] if et else '' for et, val in riga])
    t = Table(dati, colWidths=larghezze)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDO),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDO),
        ('BACKGROUND', (0, 0), (-1, -1), FONDO),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _piede(adesione):
    riga = (f"{ASSOCIAZIONE['nome']} · Codice Fiscale {ASSOCIAZIONE['cf']} · {ASSOCIAZIONE['sede']} · "
            f"{ASSOCIAZIONE['email']}")

    def disegna(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(GRIGIO)
        canvas.drawString(18 * mm, 10 * mm, riga)
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f'Domanda {adesione.numero} · pag. {doc.page}')
        canvas.restoreState()
    return disegna


def _immagine(campo, larghezza_max, altezza_max):
    try:
        campo.open('rb')
        dati = io.BytesIO(campo.read())
        campo.close()
        img = Image(dati)
        scala = min(larghezza_max / img.imageWidth, altezza_max / img.imageHeight)
        img.drawWidth = img.imageWidth * scala
        img.drawHeight = img.imageHeight * scala
        img.hAlign = 'CENTER'
        return img
    except Exception:  # file illeggibile: il PDF si genera comunque
        return _p('Immagine non disponibile.')


INFORMATIVA = [
    ('Titolare del trattamento.',
     'Il titolare del trattamento è la Comunità Energetica Rinnovabile CER Hub, con sede in '
     f"{ASSOCIAZIONE['sede']}, codice fiscale {ASSOCIAZIONE['cf']}, mail {ASSOCIAZIONE['email']}."),
    ('Finalità del trattamento e base giuridica.',
     'La Comunità Energetica Rinnovabile tratta i tuoi dati personali per lo svolgimento dell’attività '
     'istituzionale finalizzata a consentire un migliore e più efficiente sfruttamento dell’energia elettrica '
     'prodotta con fonti rinnovabili ed in particolare:<br/>'
     'a) per la gestione del rapporto associativo (invio della corrispondenza, convocazione alle sedute degli '
     'organi, procedure amministrative interne) e per l’organizzazione ed esecuzione del servizio;<br/>'
     'b) per adempiere agli obblighi di legge (es. fiscali, assicurativi, ecc.) riferiti ai soci della Comunità '
     'Energetica Rinnovabile;<br/>'
     'c) per l’invio (tramite posta, posta elettronica, newsletter o numero di cellulare o altri mezzi '
     'informatici) di comunicazioni legate all’attività e iniziative della Comunità Energetica Rinnovabile;<br/>'
     'd) per l’analisi dei consumi al solo fine di valutare eventuali interventi per migliorare la performance '
     'energetica della Comunità Energetica Rinnovabile;<br/>'
     'e) per la gestione degli eventuali contributi economici spettanti, nelle modalità descritte '
     'nell’“Allegato A – Condizioni per il riconoscimento degli eventuali contributi economici spettanti”.<br/>'
     'La base giuridica dei trattamenti in precedenza elencati è rappresentata dalla richiesta di adesione e dal '
     'contratto associativo (art. 6 comma 1 lett. b GDPR), e dagli obblighi legali a cui è tenuta la Comunità '
     'Energetica Rinnovabile (art. 6 comma 1 lett. c GDPR).'),
    ('Sottoscrizione online.',
     'Per la sottoscrizione online della domanda la Comunità Energetica Rinnovabile raccoglie la copia del '
     'documento d’identità del firmatario e i dati tecnici della firma elettronica (data, ora, indirizzo IP e '
     'indirizzo e-mail), al solo fine di identificare il firmatario e di documentare l’avvenuta sottoscrizione.'),
    ('Modalità e principi del trattamento.',
     'Il trattamento avverrà nel rispetto del GDPR e della normativa in materia di privacy e data protection, '
     'nonché dei principi di liceità, correttezza e trasparenza, adeguatezza e pertinenza, con modalità cartacee '
     'ed informatiche, ad opera di persone autorizzate dalla Comunità Energetica Rinnovabile e con l’adozione di '
     'misure adeguate di protezione, in modo da garantire la sicurezza e la riservatezza dei dati.'),
    ('Necessità del conferimento.',
     'Il conferimento dei dati anagrafici e di contatto è necessario in quanto strettamente legato alla gestione '
     'del rapporto associativo.'),
    ('Comunicazione dei dati e trasferimento all’estero dei dati.',
     'I dati potranno essere comunicati agli altri soci ai fini dell’organizzazione ed esecuzione del servizio. '
     'I dati potranno, inoltre, essere comunicati ai soggetti deputati allo svolgimento di attività a cui la '
     'Comunità Energetica Rinnovabile è tenuta in base ad obbligo di legge e a tutte quelle persone fisiche e/o '
     'giuridiche, pubbliche e/o private quando la comunicazione risulti necessaria o funzionale allo svolgimento '
     'dell’attività istituzionale. I dati potranno essere trasferiti a destinatari con sede extra UE che hanno '
     'sottoscritto accordi diretti ad assicurare un livello di protezione adeguato dei dati personali, o comunque '
     'previa verifica che il destinatario garantisca adeguate misure di protezione. Ove necessario o opportuno, i '
     'soggetti cui vengono trasmessi i dati per lo svolgimento di attività per conto della Comunità Energetica '
     'Rinnovabile saranno nominati Responsabili del trattamento ai sensi dell’art. 28 GDPR.'),
    ('Periodo di conservazione dei dati.',
     'I dati personali oggetto di trattamento per le finalità sopra descritte saranno conservati nel rispetto dei '
     'principi di proporzionalità e necessità, e comunque fino a che non siano state perseguite le finalità del '
     'trattamento. In particolare, i dati saranno utilizzati dalla Comunità Energetica Rinnovabile fino alla '
     'cessazione del rapporto associativo. I dati personali saranno cancellati decorsi 10 anni dalla cessazione '
     'del rapporto contrattuale, fatte salve le esigenze di riscossione dei crediti residui o la gestione dei dati '
     'in ipotesi di eventuali contestazioni o reclami, quali ad esempio quelle aventi ad oggetto le fatture emesse.'),
    ('Diritti dell’interessato.',
     'Nella qualità di interessato, puoi esercitare, ove applicabili, i diritti specificati all’art. 15 - 22 GDPR '
     '(il diritto all’accesso, rettifica e cancellazione dei dati, il diritto di limitazione e opposizione al '
     'trattamento, il diritto di revocare il consenso al trattamento). I suddetti diritti possono essere esercitati '
     'mediante comunicazione scritta da inviare a mezzo posta elettronica o a mezzo Raccomandata presso la sede '
     'della Comunità Energetica Rinnovabile. Inoltre, hai la facoltà di proporre reclamo al Garante per la '
     'Protezione dei dati personali qualora tu ritenga che il trattamento che ti riguarda violi il GDPR o la '
     'normativa italiana.'),
]


def dichiarazioni(adesione):
    """Testi delle dichiarazioni obbligatorie, nell'ordine del modulo."""
    az = adesione.is_azienda
    titolare = 'la Società/Associazione è titolare intestatario' if az else 'è titolare intestatario'
    testi = [
        'che non sussistono le cause di esclusione dall’accesso agli incentivi di cui all’art. 3 comma 3 lettere '
        '(a) (b) (c) (d) del Decreto CACER;',
        'che alla data odierna il punto di connessione associato al Codice POD non risulta già beneficiario degli '
        'incentivi previsti dal Decreto CACER;',
        'che alla data odierna sul punto di connessione associato al Codice POD non risulta attivo il servizio di '
        'Scambio Sul Posto;',
    ]
    if az and adesione.tipologia == adesione.PMI:
        testi.append(
            'di appartenere alla categoria delle piccole medie imprese (“PMI”), dove per PMI si intendono le '
            'imprese che hanno meno di 250 occupati e un fatturato annuo non superiore a 50 milioni di euro, oppure '
            'un totale di bilancio annuo non superiore a 43 milioni di euro;')
    testi += [
        'di avere preso visione dello Statuto e del Regolamento della Comunità Energetica Rinnovabile, di approvarli '
        'in ogni loro parte, di condividere i principi e le finalità della Comunità Energetica Rinnovabile e di '
        'impegnarsi a rispettare le disposizioni statutarie vigenti e le delibere degli organi sociali validamente '
        'costituiti;',
        'di acconsentire al trattamento dei dati personali e di consumo relativi alla fornitura di energia elettrica '
        f'di cui al/ai POD del quale {titolare}, da parte della Comunità Energetica Rinnovabile e da parte di terzi '
        'da questa incaricati, ai fini necessari al raggiungimento dello scopo della Comunità Energetica '
        'Rinnovabile, nel rispetto della normativa applicabile sulla “data protection” (Regolamento Europeo sulla '
        'protezione dei dati personali n. 679/2016, cd. “GDPR” e D. Lgs. n. 196/2003, cd. “Codice Privacy”, come '
        'novellato dal D. Lgs. n. 101/2018) e di quanto previsto all’informativa presente nell’Allegato B. I '
        'suddetti dati potranno essere trattati da parte di terzi ai fini dell’espletamento delle procedure '
        'finalizzate alla gestione ed esecuzione dei contratti di cui la Comunità Energetica Rinnovabile è parte, '
        'per permettere l’accesso al servizio di valorizzazione ed incentivazione dell’energia elettrica condivisa;',
        'di impegnarsi a comunicare prontamente alla Comunità Energetica Rinnovabile eventuali cambiamenti rispetto '
        'alle informazioni e/o dichiarazioni rilasciate nella presente Domanda di Adesione (es. sostituzione del '
        'contatore, variazione conto corrente bancario, sussistenza delle cause di esclusione dall’accesso agli '
        'incentivi previsti dal Decreto CACER).',
    ]
    return testi


def testo_richiesta(adesione):
    if adesione.cer_id:
        conf = (f'alla configurazione denominata <b>{_e(adesione.cer.name)}</b> (in seguito anche “Configurazione”) '
                f'sottesa alla cabina primaria numero <b>{_e(adesione.cer.primary_substation)}</b>')
    else:
        conf = ('alla configurazione (in seguito anche “Configurazione”) che sarà individuata dalla Comunità '
                'Energetica Rinnovabile in base alla cabina primaria a cui è collegato il POD indicato')
    soggetto = 'che la Società/Associazione sia ammessa' if adesione.is_azienda else 'di essere ammesso'
    return (
        f'{soggetto} {conf} appartenente alla Comunità Energetica Rinnovabile “CER Hub” costituita ai sensi del '
        'D. Lgs. 199/2021 e s.m.i., della Deliberazione ARERA 727/2022/R/EEL del 27 dicembre 2022 (“TIAD”), del '
        'Decreto Ministeriale 7 dicembre 2023 (“Decreto CACER”), delle regole operative per l’accesso al servizio '
        'per l’autoconsumo diffuso pubblicate il 23 febbraio 2024 e s.m.i. (“Regole Operative GSE”) (insieme, la '
        '“Normativa”) per condividere virtualmente i propri consumi di energia elettrica all’interno della '
        'Configurazione.')


def genera_pdf(adesione):
    """Restituisce (bytes del PDF, posizione firma) con la posizione in percentuale
    della pagina, origine in alto a sinistra: dict(page, x, y, width, height)."""
    a = adesione
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=f'Domanda di adesione CER Hub – {a.intestatario}', author='CER Hub',
        subject='Domanda di adesione alla Comunità Energetica Rinnovabile CER Hub')
    L = doc.width
    s = []

    logo = finders.find('images/cerhub-logo.png')
    if logo:
        img = Image(logo)
        scala = (11 * mm) / img.imageHeight
        img.drawHeight, img.drawWidth = 11 * mm, img.imageWidth * scala
        img.hAlign = 'CENTER'
        s += [img, Spacer(1, 10)]
    s += [_p('DOMANDA DI ADESIONE', TITOLO),
          _p('alla Comunità Energetica Rinnovabile “CER Hub”', SOTTOTITOLO), Spacer(1, 8)]

    nascita = f'{a.nascita_comune}' + (f' ({a.nascita_provincia})' if a.nascita_provincia else '')
    s.append(_p('Il sottoscritto', SEZIONE))
    s.append(_griglia([
        [('Nome', a.nome), ('Cognome', a.cognome), ('Codice fiscale', a.codice_fiscale)],
        [('Nato nel Comune di', nascita), ('Stato', a.nascita_stato), ('il', f'{a.nascita_data:%d/%m/%Y}')],
        [('Cellulare', a.cellulare), ('E-mail', a.email), ('', '')],
    ], [L / 3] * 3))

    if a.is_azienda:
        s.append(_p(f'in qualità di {escape(a.get_qualita_display().lower())} della Società/Associazione', SEZIONE))
        s.append(_griglia([
            [('Denominazione', a.denominazione), ('P.IVA', a.partita_iva), ('C.F.', a.cf_ente)],
            [('Sede nel Comune di', f'{a.sede_comune} ({a.sede_provincia})'),
             ('Via e numero', f'{a.sede_via}, {a.sede_civico}'), ('CAP e Stato', f'{a.sede_cap} – {a.sede_stato}')],
            [('Codice ATECO prevalente', a.ateco), ('PEC', a.pec), ('Tipologia di soggetto', a.get_tipologia_display())],
            [('Studio associato o società di professionisti', 'Sì' if a.studio_associato else 'No'),
             ('Già iscritto con proprio account sulla piattaforma del GSE', 'Sì' if a.account_gse else 'No'), ('', '')],
        ], [L / 3] * 3))
    else:
        s.append(Spacer(1, 4))
        s.append(_griglia([
            [('Residente nel Comune di', f'{a.res_comune} ({a.res_provincia})'),
             ('Via e numero', f'{a.res_via}, {a.res_civico}'), ('CAP e Stato', f'{a.res_cap} – {a.res_stato}')],
            [('Tipologia di soggetto', a.get_tipologia_display()),
             ('Già iscritto con proprio account sulla piattaforma del GSE', 'Sì' if a.account_gse else 'No'), ('', '')],
        ], [L / 3] * 3))
        if a.tipologia == a.DITTA:
            s.append(Spacer(1, 4))
            s.append(_griglia([
                [('Sede legale nel Comune di', f'{a.sede_comune} ({a.sede_provincia})'),
                 ('Via e numero', f'{a.sede_via}, {a.sede_civico}'), ('CAP e Nazione', f'{a.sede_cap} – {a.sede_stato}')],
                [('P.IVA', a.partita_iva), ('Codice ATECO prevalente', a.ateco), ('', '')],
            ], [L / 3] * 3))

    s.append(_p('Titolare del POD qui riportato – riferimenti tecnici del contatore di scambio con la rete', SEZIONE))
    s.append(_griglia([
        [('Codice POD', a.pod), ('Potenza impegnata', f'{a.potenza_impegnata} kW'.replace('.', ','))],
        [('Tensione di connessione del contatore', a.get_tensione_display()),
         ('Generazione del contatore', a.get_generazione_display())],
        [('Numero di fasi (tensione) di connessione', a.get_fasi_display()), ('', '')],
    ], [L / 2] * 2))

    s.append(_p('Riferimenti catastali associati al POD', SEZIONE))
    s.append(_griglia([
        [('Sezione', a.cat_sezione), ('Foglio', a.cat_foglio), ('Particella', a.cat_particella),
         ('Subalterno', a.cat_subalterno)],
        [('Indirizzo', f'{a.cat_indirizzo}, {a.cat_civico}'), ('Comune', a.cat_comune), ('CAP', a.cat_cap),
         ('Provincia', a.cat_provincia)],
    ], [L / 4] * 4))

    s.append(_p('CHIEDE', CENTRATO))
    s.append(_p(testo_richiesta(a)))
    s.append(Spacer(1, 6))
    intestatario_conto = 'intestato al titolare del POD'
    s.append(_p(
        ('La Società/Associazione' if a.is_azienda else 'Il sottoscritto') +
        ' autorizza l’accredito degli eventuali contributi economici derivanti dalla partecipazione alla Comunità '
        f'Energetica Rinnovabile sul conto corrente bancario {intestatario_conto} avente IBAN <b>{_e(a.iban)}</b>.'))
    s.append(Spacer(1, 4))
    s.append(_p('Le condizioni di riconoscimento degli eventuali contributi economici derivanti dalla partecipazione '
                'alla Comunità Energetica Rinnovabile sono descritte all’Allegato A.'))
    s.append(_p('Inoltre, dichiara:', SEZIONE))
    righe = [[Spunta(), _p(t, PICCOLO)] for t in dichiarazioni(a)]
    t = Table(righe, colWidths=[6 * mm, L - 6 * mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 1),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    s.append(t)

    riquadro = RiquadroFirma()
    data_firma = timezone.localtime(a.creata_il or timezone.now())
    blocco = Table(
        [[_p('Data di firma', ETICHETTA), _p('Il richiedente (firma)', ETICHETTA)],
         [_p(f'{data_firma:%d/%m/%Y}', VALORE), riquadro],
         ['', _p(escape(a.nome_completo), ETICHETTA)]],
        colWidths=[L - 86 * mm, 86 * mm])
    blocco.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    s.append(KeepTogether([
        Spacer(1, 6), _p('***', CENTRATO),
        _p('L’accoglimento della presente Domanda di Adesione è soggetto ad approvazione da parte degli organi di '
           'governance della Comunità Energetica Rinnovabile, in seguito alla verifica della sussistenza dei criteri '
           'di ammissione previsti dalla Normativa e dagli atti costitutivi della Comunità Energetica Rinnovabile.',
           PICCOLO),
        Spacer(1, 3),
        _p('Si segnala che l’attivazione dell’incentivo statale è subordinata all’accettazione dell’istanza di '
           'accesso al servizio per l’autoconsumo diffuso da parte del Gestore dei Servizi Energetici (“GSE”).',
           PICCOLO),
        Spacer(1, 10), blocco,
    ]))

    # --- Allegato A ---------------------------------------------------------
    s.append(PageBreak())
    s.append(_p('Allegato A – Condizioni per il riconoscimento degli eventuali contributi economici spettanti',
                CENTRATO))
    s.append(_p('Con la sottoscrizione della presente Domanda di Adesione si accettano le condizioni valide ai fini '
                'del riconoscimento da parte della CER dei contributi economici erogati dal Gestore dei Servizi '
                'Energetici (“GSE”) eventualmente spettanti per l’accesso al servizio di valorizzazione e '
                'incentivazione dell’energia condivisa, di seguito riportate:'))
    s.append(Spacer(1, 4))
    s.append(_p('a) I contributi economici, qualora previsti, sono determinati sulla base dei criteri di calcolo '
                'stabiliti dalla Comunità Energetica all’interno dei propri atti costitutivi;'))
    s.append(Spacer(1, 3))
    s.append(_p('b) I bonifici che, qualora previsti, saranno effettuati all’IBAN indicato nella presente Domanda di '
                'Adesione avranno periodicità di accredito dei contributi eventualmente spettanti in linea con quanto '
                'stabilito dagli atti costitutivi della Comunità Energetica Rinnovabile.'))

    # --- Allegato B ---------------------------------------------------------
    s.append(Spacer(1, 14))
    s.append(_p('Allegato B – Informativa ex art. 13 GDPR per i soci', CENTRATO))
    s.append(_p('Caro socio/a,<br/>ai sensi dell’art. 13 del Regolamento UE 2016/679 in materia di protezione dei '
                'dati personali (“GDPR”) ti informiamo di quanto segue.', MINUTO))
    for titolo, testo in INFORMATIVA:
        s.append(Spacer(1, 3))
        s.append(_p(f'<b>{titolo}</b> {testo}', MINUTO))

    # --- Allegato C ---------------------------------------------------------
    s.append(PageBreak())
    s.append(_p('Allegato C – Documento d’identità del firmatario', CENTRATO))
    s.append(_p('Fronte', ETICHETTA))
    s.append(_immagine(a.doc_fronte, L, 105 * mm))
    s.append(Spacer(1, 10))
    s.append(_p('Retro', ETICHETTA))
    s.append(_immagine(a.doc_retro, L, 105 * mm))

    piede = _piede(a)
    doc.build(s, onFirstPage=piede, onLaterPages=piede)

    pagina, x, y, w, h = riquadro.posizione
    PW, PH = A4
    posizione = {
        'page': pagina,
        'x': round(x / PW * 100, 3),
        'y': round((PH - y - h) / PH * 100, 3),
        'width': round(w / PW * 100, 3),
        'height': round(h / PH * 100, 3),
    }
    return buffer.getvalue(), posizione
