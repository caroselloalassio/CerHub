"""Logica delle adesioni online: PDF, firma, creazione dell'utente, email."""
import io
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image, ImageOps

from . import documenso
from .models import Adesione
from .pdf import genera_pdf

logger = logging.getLogger(__name__)

LATO_MASSIMO = 2000          # pixel: lato lungo delle foto del documento
GIORNI_BOZZE = 30            # le domande non firmate vengono eliminate dopo questi giorni
MESI_NON_ACCOLTE = 12        # le domande non accolte vengono eliminate dopo questi mesi dall'esito
ORE_ACCESSO_DA_LINK = 48     # dopo la firma, il link ricevuto per email vale ancora per queste ore


def origine():
    return getattr(settings, 'APP_ORIGIN', 'http://localhost:8000').rstrip('/')


def url_assoluto(nome, *args):
    return origine() + reverse(nome, args=args)


# --- Immagini ---------------------------------------------------------------

def prepara_immagine(caricato):
    """Normalizza la foto del documento: orientamento corretto, JPEG, dimensione
    contenuta, senza metadati (posizione GPS, modello del telefono...)."""
    try:
        caricato.seek(0)
        img = Image.open(caricato)
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
    except Exception as exc:
        raise ValidationError('Il file caricato non è un\'immagine leggibile.') from exc
    img.thumbnail((LATO_MASSIMO, LATO_MASSIMO))
    out = io.BytesIO()
    img.save(out, format='JPEG', quality=85, optimize=True)
    return ContentFile(out.getvalue())


# --- PDF --------------------------------------------------------------------

def rigenera_pdf(adesione):
    dati, pos = genera_pdf(adesione)
    if adesione.pdf_modulo:
        adesione.pdf_modulo.delete(save=False)
    adesione.pdf_modulo.save('domanda.pdf', ContentFile(dati), save=False)
    adesione.firma_pagina = pos['page']
    adesione.firma_x, adesione.firma_y = pos['x'], pos['y']
    adesione.firma_l, adesione.firma_h = pos['width'], pos['height']
    adesione.save()


# --- Firma ------------------------------------------------------------------

def annulla_firma(adesione):
    """Annulla una firma avviata e non conclusa (es. perché i dati vengono corretti)."""
    if adesione.firma_busta:
        documenso.annulla_busta(adesione.firma_busta)
    adesione.firma_busta = ''
    adesione.firma_url = ''
    adesione.stato = Adesione.COMPILATA


def avvia_firma(adesione):
    """Crea (se serve) la busta di firma e restituisce l'indirizzo a cui mandare il firmatario."""
    if adesione.stato == Adesione.IN_FIRMA and adesione.firma_url:
        return adesione.firma_url
    if adesione.stato != Adesione.COMPILATA:
        raise documenso.ErroreFirma('La domanda è già stata firmata.')
    adesione.pdf_modulo.open('rb')
    pdf = adesione.pdf_modulo.read()
    adesione.pdf_modulo.close()
    busta = documenso.crea_busta(
        titolo=f'Domanda di adesione CER Hub – {adesione.intestatario}',
        pdf=pdf,
        nome_file=f'domanda-di-adesione-{adesione.numero}.pdf',
        firmatario_nome=adesione.nome_completo,
        firmatario_email=adesione.email,
        campo_firma={'page': adesione.firma_pagina, 'x': adesione.firma_x, 'y': adesione.firma_y,
                     'width': adesione.firma_l, 'height': adesione.firma_h},
        riferimento=str(adesione.token),
        url_ritorno=url_assoluto('adesioni:ritorno', adesione.token),
    )
    adesione.firma_busta = busta
    adesione.save(update_fields=['firma_busta', 'aggiornata_il'])
    adesione.firma_url = documenso.distribuisci(busta)
    adesione.stato = Adesione.IN_FIRMA
    adesione.save(update_fields=['firma_url', 'stato', 'aggiornata_il'])
    return adesione.firma_url


def sincronizza(adesione_id):
    """Controlla sul servizio di firma se la domanda è stata firmata; se sì scarica
    il documento, crea l'utente e manda le email. Restituisce l'adesione aggiornata."""
    appena_firmata = False
    with transaction.atomic():
        adesione = Adesione.objects.select_for_update().get(pk=adesione_id)
        if adesione.stato != Adesione.IN_FIRMA or not adesione.firma_busta:
            return adesione
        busta = documenso.leggi_busta(adesione.firma_busta)
        stato = busta.get('status')
        if stato == 'COMPLETED':
            pdf = documenso.scarica_firmato(busta)
            adesione.pdf_firmato.save('firmata.pdf', ContentFile(pdf), save=False)
            firmatari = [r for r in busta.get('recipients', []) if r.get('signedAt')]
            adesione.segna_firmata()
            if firmatari:
                from django.utils.dateparse import parse_datetime
                adesione.firmata_il = parse_datetime(firmatari[0]['signedAt']) or adesione.firmata_il
            adesione.utente = adesione.utente or trova_o_crea_utente(adesione)
            adesione.save()
            appena_firmata = True
        elif stato in ('REJECTED', 'CANCELLED'):
            adesione.firma_busta = ''
            adesione.firma_url = ''
            adesione.stato = Adesione.COMPILATA
            adesione.save()
    if appena_firmata:
        try:
            invia_mail_firmata(adesione)
            invia_mail_associazione(adesione)
        except Exception:  # la firma è valida anche se la posta non parte
            logger.exception('Invio email dopo la firma non riuscito (adesione %s)', adesione.pk)
    return adesione


# --- Utente -----------------------------------------------------------------

def _indirizzo(adesione):
    if adesione.is_azienda:
        parti = (adesione.sede_via, adesione.sede_civico, adesione.sede_cap, adesione.sede_comune,
                 adesione.sede_provincia)
    else:
        parti = (adesione.res_via, adesione.res_civico, adesione.res_cap, adesione.res_comune,
                 adesione.res_provincia)
    via, civico, cap, comune, prov = parti
    return f'{via} {civico}, {cap} {comune} ({prov})'[:255]


def trova_o_crea_utente(adesione):
    """L'aderente ha un utente nell'area soci: se esiste già con la stessa email lo
    riusa, altrimenti lo crea (la password la sceglie lui dal link ricevuto)."""
    User = get_user_model()
    email = adesione.email.strip().lower()
    esistente = User.objects.filter(email__iexact=email).order_by('id').first()
    if esistente:
        return esistente

    username = email[:150]
    if User.objects.filter(username__iexact=username).exists():
        username = f'{email[:140]}-{adesione.pk}'
    comuni = dict(
        username=username, email=email, first_name=adesione.nome[:150], last_name=adesione.cognome[:150],
        phone=adesione.cellulare[:20], address=_indirizzo(adesione), privacy_accepted=True,
        privacy_acceptance_date=timezone.now(), privacy_last_update=timezone.now(),
    )
    candidati = []
    if adesione.is_azienda and adesione.partita_iva and adesione.pec:
        tipo = 'ASSOCIATION' if adesione.tipologia == Adesione.ASSOCIAZIONE else 'BUSINESS'
        candidati.append(dict(
            legal_type=tipo, profit_type='NON_PROFIT' if tipo == 'ASSOCIATION' else 'PROFIT',
            legal_name=adesione.denominazione, vat_number=adesione.partita_iva, pec=adesione.pec,
            fiscal_code=(adesione.cf_ente or adesione.partita_iva)[:16]))
    # ripiego (e caso dei privati): profilo personale del firmatario
    candidati.append(dict(legal_type='PRIVATE', fiscal_code=adesione.codice_fiscale[:16],
                          vat_number=adesione.partita_iva or None))
    ultimo_errore = None
    for extra in candidati:
        utente = User(**comuni, **extra)
        # password casuale (non comunicata): l'aderente sceglie la propria dal link ricevuto
        # per email, e "Password dimenticata" funziona anche se il link scade
        utente.set_password(get_random_string(40))
        try:
            with transaction.atomic():
                utente.save()
            return utente
        except ValidationError as exc:
            ultimo_errore = exc
    raise ultimo_errore


def link_imposta_password(utente):
    uid = urlsafe_base64_encode(force_bytes(utente.pk))
    token = default_token_generator.make_token(utente)
    return url_assoluto('users:password_reset_confirm', uid, token)


# --- Email ------------------------------------------------------------------

FIRMA_MAIL = (
    '\n\nCER Hub – Comunità Energetica Rinnovabile\n'
    'Codice Fiscale 90076120097\n'
    'https://www.cerhub.it'
)


def _invia(oggetto, testo, destinatari, allegati=()):
    msg = EmailMessage(
        subject=oggetto, body=testo + FIRMA_MAIL, to=list(destinatari),
        reply_to=[settings.ADESIONI_EMAIL_ASSOCIAZIONE])
    for nome, contenuto in allegati:
        msg.attach(nome, contenuto, 'application/pdf')
    msg.send(fail_silently=False)


def invia_mail_riprendi(adesione):
    """Dopo la compilazione: link per riprendere e firmare anche in un secondo momento."""
    _invia(
        'La tua domanda di adesione a CER Hub: manca solo la firma',
        f'Ciao {adesione.nome},\n\n'
        'abbiamo ricevuto i dati della tua domanda di adesione alla Comunità Energetica Rinnovabile CER Hub.\n'
        'Per completarla manca solo la firma. Se non l\'hai ancora fatto, puoi rileggere la domanda e firmarla '
        'da qui:\n\n'
        f'{url_assoluto("adesioni:riepilogo", adesione.token)}\n\n'
        f'Il link è personale: non inoltrarlo. Le domande non firmate vengono eliminate dopo {GIORNI_BOZZE} giorni.\n'
        'Se non hai compilato tu questa domanda puoi ignorare questo messaggio.',
        [adesione.email])


def invia_mail_firmata(adesione):
    utente = adesione.utente
    righe = [
        f'Ciao {adesione.nome},',
        '',
        f'la domanda di adesione {adesione.numero} alla Comunità Energetica Rinnovabile CER Hub è stata firmata. '
        'La trovi in allegato.',
        '',
        'La domanda sarà ora esaminata dagli organi dell\'associazione: ti scriveremo appena c\'è l\'esito.',
        '',
    ]
    if utente and utente.last_login is None:
        righe += [
            'Abbiamo creato il tuo accesso all\'area soci, dove ritrovi sempre i documenti firmati.',
            f'Nome utente: {utente.username}',
            'Scegli la tua password da qui (il link vale 3 giorni):',
            link_imposta_password(utente),
            '',
            'Se il link è scaduto usa "Password dimenticata" nella pagina di accesso:',
            url_assoluto('users:login'),
        ]
    else:
        righe += [
            'Ritrovi sempre i documenti firmati nella tua area soci:',
            url_assoluto('adesioni:mie'),
        ]
    adesione.pdf_firmato.open('rb')
    pdf = adesione.pdf_firmato.read()
    adesione.pdf_firmato.close()
    _invia('Domanda di adesione a CER Hub firmata', '\n'.join(righe), [adesione.email],
           allegati=[(f'domanda-di-adesione-{adesione.numero}-firmata.pdf', pdf)])


def invia_mail_associazione(adesione):
    _invia(
        f'Nuova domanda di adesione firmata: {adesione.intestatario}',
        f'È stata firmata la domanda di adesione {adesione.numero}.\n\n'
        f'Aderente: {adesione.intestatario} ({adesione.get_tipo_display()})\n'
        f'Firmatario: {adesione.nome_completo} – {adesione.email} – {adesione.cellulare}\n'
        f'POD: {adesione.pod}\n'
        f'Configurazione: {adesione.cer.name if adesione.cer_id else "da assegnare"}\n\n'
        'Per esaminarla e registrare l\'esito:\n'
        f'{origine()}/ceradmin/adesioni/adesione/{adesione.pk}/change/',
        [settings.ADESIONI_EMAIL_ASSOCIAZIONE])


def invia_mail_esito(adesione):
    if adesione.stato == Adesione.APPROVATA:
        oggetto = 'La tua domanda di adesione a CER Hub è stata accolta'
        testo = (f'Ciao {adesione.nome},\n\n'
                 f'la domanda di adesione {adesione.numero} è stata accolta: benvenuto in CER Hub!\n\n'
                 'L\'attivazione dell\'incentivo è subordinata all\'accettazione dell\'istanza da parte del GSE: '
                 'ti terremo aggiornato.\n\n'
                 f'La tua area soci: {url_assoluto("users:login")}')
    else:
        oggetto = 'Esito della tua domanda di adesione a CER Hub'
        testo = (f'Ciao {adesione.nome},\n\n'
                 f'ci dispiace, la domanda di adesione {adesione.numero} non è stata accolta.\n'
                 'Per maggiori informazioni puoi rispondere a questo messaggio.')
    _invia(oggetto, testo, [adesione.email])


# --- Accesso e pulizia ------------------------------------------------------

def link_ancora_valido(adesione):
    """Il link personale (token) dà accesso finché la domanda è da firmare e per
    poche ore dopo la firma; poi i documenti si vedono solo dall'area soci."""
    if adesione.da_firmare:
        return True
    return bool(adesione.firmata_il and timezone.now() - adesione.firmata_il < timedelta(hours=ORE_ACCESSO_DA_LINK))


def elimina(adesione):
    for campo in (adesione.doc_fronte, adesione.doc_retro, adesione.pdf_modulo, adesione.pdf_firmato):
        if campo:
            campo.delete(save=False)
    adesione.delete()


def pulizia():
    """Elimina le domande compilate e mai firmate più vecchie di GIORNI_BOZZE giorni."""
    limite = timezone.now() - timedelta(days=GIORNI_BOZZE)
    n = 0
    for adesione in Adesione.objects.filter(stato__in=[Adesione.COMPILATA, Adesione.IN_FIRMA], creata_il__lt=limite):
        if adesione.stato == Adesione.IN_FIRMA and documenso.configurato():
            try:  # potrebbe essere stata firmata senza tornare sul sito
                adesione = sincronizza(adesione.pk)
            except documenso.ErroreFirma:
                continue
            if adesione.stato not in (Adesione.COMPILATA, Adesione.IN_FIRMA):
                continue
        if adesione.firma_busta:
            documenso.annulla_busta(adesione.firma_busta)
        elimina(adesione)
        n += 1
    # domande non accolte: eliminate dopo MESI_NON_ACCOLTE mesi dall'esito
    limite = timezone.now() - timedelta(days=30 * MESI_NON_ACCOLTE)
    for adesione in Adesione.objects.filter(stato=Adesione.RIFIUTATA, esito_il__lt=limite):
        elimina(adesione)
        n += 1
    return n
