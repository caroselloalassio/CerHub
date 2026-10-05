"""Client minimale per le API v2 di Documenso (firma elettronica su firme.cerhub.it)."""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30


class ErroreFirma(Exception):
    """Errore nel dialogo con il servizio di firma."""


def configurato():
    return bool(getattr(settings, 'DOCUMENSO_API_TOKEN', ''))


def _url(percorso):
    return settings.DOCUMENSO_URL.rstrip('/') + '/api/v2' + percorso


def _richiesta(metodo, percorso, **kwargs):
    if not configurato():
        raise ErroreFirma('Servizio di firma non configurato.')
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = settings.DOCUMENSO_API_TOKEN
    try:
        r = requests.request(metodo, _url(percorso), headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        logger.error('Documenso non raggiungibile: %s', exc)
        raise ErroreFirma('Servizio di firma non raggiungibile.') from exc
    if r.status_code >= 400:
        logger.error('Documenso %s %s -> %s %s', metodo, percorso, r.status_code, r.text[:500])
        raise ErroreFirma(f'Il servizio di firma ha risposto con un errore ({r.status_code}).')
    return r


def crea_busta(*, titolo, pdf, nome_file, firmatario_nome, firmatario_email, campo_firma,
               riferimento, url_ritorno):
    """Crea la busta con un firmatario e un campo firma. Restituisce l'id della busta."""
    payload = {
        'title': titolo[:255],
        'type': 'DOCUMENT',
        'externalId': riferimento,
        'recipients': [{
            'email': firmatario_email,
            'name': firmatario_nome[:255],
            'role': 'SIGNER',
            'fields': [{
                'type': 'SIGNATURE',
                'identifier': 0,
                'page': campo_firma['page'],
                'positionX': campo_firma['x'],
                'positionY': campo_firma['y'],
                'width': campo_firma['width'],
                'height': campo_firma['height'],
            }],
        }],
        'meta': {
            'subject': 'Domanda di adesione a CER Hub',
            'message': 'Firma la tua domanda di adesione alla Comunità Energetica Rinnovabile CER Hub.',
            'timezone': 'Europe/Rome',
            'dateFormat': 'dd/MM/yyyy HH:mm',
            'distributionMethod': 'NONE',
            'redirectUrl': url_ritorno,
            'language': 'it',
            'typedSignatureEnabled': True,
            'drawSignatureEnabled': True,
            'uploadSignatureEnabled': False,
        },
    }
    r = _richiesta(
        'POST', '/envelope/create',
        data={'payload': json.dumps(payload)},
        files=[('files', (nome_file, pdf, 'application/pdf'))],
    )
    return r.json()['id']


def distribuisci(busta_id):
    """Apre la busta alla firma e restituisce l'indirizzo di firma del firmatario."""
    r = _richiesta('POST', '/envelope/distribute', json={
        'envelopeId': busta_id,
        'meta': {'distributionMethod': 'NONE', 'timezone': 'Europe/Rome', 'dateFormat': 'dd/MM/yyyy HH:mm',
                 'language': 'it'},
    })
    dati = r.json()
    for destinatario in dati.get('recipients', []):
        if destinatario.get('role') == 'SIGNER' and destinatario.get('signingUrl'):
            return destinatario['signingUrl']
    raise ErroreFirma('Il servizio di firma non ha restituito l\'indirizzo di firma.')


def leggi_busta(busta_id):
    return _richiesta('GET', f'/envelope/{busta_id}').json()


def scarica_firmato(busta):
    """Scarica il PDF firmato (con certificato di firma) del primo documento della busta."""
    elementi = sorted(busta.get('envelopeItems', []), key=lambda e: e.get('order', 0))
    if not elementi:
        raise ErroreFirma('La busta non contiene documenti.')
    r = _richiesta('GET', f"/envelope/item/{elementi[0]['id']}/download", params={'version': 'signed'})
    contenuto = r.content
    if not contenuto.startswith(b'%PDF'):
        raise ErroreFirma('Il documento firmato ricevuto non è un PDF.')
    return contenuto


def annulla_busta(busta_id):
    try:
        _richiesta('POST', '/envelope/delete', json={'envelopeId': busta_id})
    except ErroreFirma:
        pass
