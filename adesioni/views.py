import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import documenso, services
from .forms import AdesioneAziendaForm, AdesionePrivatoForm
from .models import Adesione

logger = logging.getLogger(__name__)

MAX_DOMANDE_ORA = 6          # per indirizzo IP
MAX_ATTESE = 15              # ricariche della pagina di attesa dopo la firma

FORMS = {Adesione.PRIVATO: AdesionePrivatoForm, Adesione.AZIENDA: AdesioneAziendaForm}


def _ip(request):
    inoltrato = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (inoltrato.split(',')[0].strip() if inoltrato else request.META.get('REMOTE_ADDR')) or None


def _mie_in_sessione(request):
    return request.session.get('adesioni', [])


def _ricorda(request, adesione):
    elenco = _mie_in_sessione(request)
    if str(adesione.token) not in elenco:
        request.session['adesioni'] = (elenco + [str(adesione.token)])[-10:]


def _accesso(request, adesione):
    """Chi può vedere la domanda: lo staff, l'utente a cui appartiene, il browser che
    l'ha compilata e chi ha il link personale finché questo è valido."""
    u = request.user
    if u.is_authenticated and (u.is_staff or adesione.utente_id == u.pk):
        return True
    if str(adesione.token) in _mie_in_sessione(request) and services.link_ancora_valido(adesione):
        return True
    return services.link_ancora_valido(adesione)


def _carica(request, token):
    """Restituisce (adesione, None) oppure (None, risposta di reindirizzamento al login)."""
    adesione = get_object_or_404(Adesione, token=token)
    if _accesso(request, adesione):
        return adesione, None
    if request.user.is_authenticated:
        raise Http404
    messages.info(request, 'Per vedere questa domanda accedi all\'area soci.')
    return None, redirect_to_login(request.get_full_path())


def _contesto(**extra):
    return {'firma_attiva': documenso.configurato(), 'email_associazione': settings.ADESIONI_EMAIL_ASSOCIAZIONE,
            **extra}


def scelta(request):
    return render(request, 'adesioni/scelta.html', _contesto())


def _iniziali(request):
    u = request.user
    if not u.is_authenticated:
        return {}
    return {'nome': u.first_name, 'cognome': u.last_name, 'email': u.email, 'cellulare': u.phone or '',
            'codice_fiscale': (u.fiscal_code or '') if u.legal_type == 'PRIVATE' else ''}


def _salva(request, form, adesione_esistente=None):
    """Salva la domanda, normalizza le foto, rigenera il PDF."""
    with transaction.atomic():
        adesione = form.save(commit=False)
        for nome in ('doc_fronte', 'doc_retro'):
            caricato = form.cleaned_data.get(nome)
            if caricato and hasattr(caricato, 'read') and nome in form.changed_data:
                immagine = services.prepara_immagine(caricato)
                if adesione_esistente and getattr(adesione_esistente, nome):
                    getattr(adesione_esistente, nome).delete(save=False)
                getattr(adesione, nome).save(f'{nome}.jpg', immagine, save=False)
        if adesione_esistente is None:
            adesione.ip = _ip(request)
            adesione.user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
            if request.user.is_authenticated and not request.user.is_staff:
                adesione.utente = request.user
        adesione.save()
        services.rigenera_pdf(adesione)
    return adesione


@never_cache
def compila(request, tipo):
    Form = FORMS[tipo]
    if not documenso.configurato():
        return render(request, 'adesioni/non_attiva.html', _contesto(), status=503)
    if request.method == 'POST':
        chiave = f'adesioni:ip:{_ip(request)}'
        if cache.get(chiave, 0) >= MAX_DOMANDE_ORA:
            messages.error(request, 'Troppe domande inviate da questa connessione: riprova più tardi.')
            return redirect('adesioni:scelta')
        form = Form(request.POST, request.FILES)
        if form.is_valid():
            try:
                adesione = _salva(request, form)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                cache.set(chiave, cache.get(chiave, 0) + 1, 3600)
                _ricorda(request, adesione)
                request.session['ga_events'] = ['generate_lead']
                try:
                    services.invia_mail_riprendi(adesione)
                except Exception:
                    logger.exception('Email di riepilogo non inviata (adesione %s)', adesione.pk)
                try:
                    services.pulizia()
                except Exception:
                    logger.exception('Pulizia delle domande non firmate non riuscita')
                return redirect('adesioni:riepilogo', token=adesione.token)
    else:
        form = Form(initial=_iniziali(request))
    return render(request, 'adesioni/modulo.html', _contesto(form=form, tipo=tipo, modifica=False))


@never_cache
def modifica(request, token):
    adesione, risposta = _carica(request, token)
    if risposta:
        return risposta
    if not adesione.da_firmare:
        messages.info(request, 'La domanda è già stata firmata e non può più essere modificata.')
        return redirect('adesioni:riepilogo', token=token)
    Form = FORMS[adesione.tipo]
    if request.method == 'POST':
        form = Form(request.POST, request.FILES, instance=adesione)
        if form.is_valid():
            try:
                precedente = Adesione.objects.get(pk=adesione.pk)
                if precedente.stato == Adesione.IN_FIRMA:
                    services.annulla_firma(adesione)
                adesione = _salva(request, form, adesione_esistente=precedente)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Dati aggiornati: controlla la domanda e firmala.')
                return redirect('adesioni:riepilogo', token=token)
    else:
        form = Form(instance=adesione)
    return render(request, 'adesioni/modulo.html', _contesto(form=form, tipo=adesione.tipo, modifica=True,
                                                               adesione=adesione))


@never_cache
def riepilogo(request, token):
    adesione, risposta = _carica(request, token)
    if risposta:
        return risposta
    if adesione.stato == Adesione.IN_FIRMA and documenso.configurato():
        try:
            adesione = services.sincronizza(adesione.pk)
        except documenso.ErroreFirma:
            pass
    return render(request, 'adesioni/riepilogo.html', _contesto(adesione=adesione))


@require_POST
def firma(request, token):
    adesione, risposta = _carica(request, token)
    if risposta:
        return risposta
    if not adesione.da_firmare:
        return redirect('adesioni:riepilogo', token=token)
    try:
        indirizzo = services.avvia_firma(adesione)
    except documenso.ErroreFirma as exc:
        logger.error('Avvio firma non riuscito (adesione %s): %s', adesione.pk, exc)
        messages.error(request, 'In questo momento non riusciamo ad aprire la pagina di firma. '
                                'Riprova tra qualche minuto: i tuoi dati sono salvati.')
        return redirect('adesioni:riepilogo', token=token)
    _ricorda(request, adesione)
    return redirect(indirizzo)


@never_cache
def ritorno(request, token):
    """Pagina a cui il servizio di firma rimanda dopo la firma."""
    adesione, risposta = _carica(request, token)
    if risposta:
        return risposta
    if adesione.stato == Adesione.IN_FIRMA:
        try:
            adesione = services.sincronizza(adesione.pk)
        except documenso.ErroreFirma:
            pass
    if adesione.stato == Adesione.IN_FIRMA:
        # il documento firmato viene sigillato dal servizio di firma in pochi secondi
        try:
            n = int(request.GET.get('n', 0)) + 1
        except ValueError:
            n = 1
        if n <= MAX_ATTESE:
            return render(request, 'adesioni/attesa.html', _contesto(adesione=adesione, n=n))
        return redirect('adesioni:riepilogo', token=token)
    if adesione.stato == Adesione.FIRMATA:
        _ricorda(request, adesione)
        request.session['ga_events'] = ['sign_up']
    return redirect('adesioni:riepilogo', token=token)


FILES = {
    'domanda': ('pdf_modulo', 'domanda-di-adesione.pdf', 'application/pdf'),
    'firmata': ('pdf_firmato', 'domanda-di-adesione-firmata.pdf', 'application/pdf'),
    'documento-fronte': ('doc_fronte', 'documento-fronte.jpg', 'image/jpeg'),
    'documento-retro': ('doc_retro', 'documento-retro.jpg', 'image/jpeg'),
}


@never_cache
def documento(request, token, quale):
    adesione, risposta = _carica(request, token)
    if risposta:
        return risposta
    if quale not in FILES:
        raise Http404
    campo, nome, tipo = FILES[quale]
    f = getattr(adesione, campo)
    if not f:
        raise Http404
    try:
        aperto = f.open('rb')
    except FileNotFoundError:
        raise Http404
    risposta = FileResponse(aperto, content_type=tipo, as_attachment='scarica' in request.GET,
                            filename=f'{adesione.numero}-{nome}')
    risposta['X-Robots-Tag'] = 'noindex'
    return risposta


@login_required
def mie(request):
    adesioni = Adesione.objects.filter(utente=request.user).select_related('cer')
    return render(request, 'adesioni/mie.html', _contesto(adesioni=adesioni))
