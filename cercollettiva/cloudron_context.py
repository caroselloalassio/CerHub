# cercollettiva/cloudron_context.py
from django.conf import settings


def analytics(request):
    """
    Dati per Google Analytics (caricato solo dopo il consenso dell'utente).
    Gli eventi messi in sessione da login e registrazione vengono inviati una volta sola.
    """
    events = []
    session = getattr(request, 'session', None)
    if session is not None and 'ga_events' in session:
        events = session.pop('ga_events') or []
    return {
        'GA_MEASUREMENT_ID': getattr(settings, 'GA_MEASUREMENT_ID', ''),
        'ga_events': events,
    }
