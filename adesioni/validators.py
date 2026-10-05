"""Controlli formali sui dati della domanda di adesione."""
import re

from django.core.exceptions import ValidationError

_CF_ODD = {
    **{str(i): v for i, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
    **{c: v for c, v in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                            [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20,
                             11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23])},
}


def normalizza(value):
    return re.sub(r'\s+', '', (value or '')).upper()


def valida_codice_fiscale(value):
    """Codice fiscale di persona fisica (16 caratteri, con carattere di controllo)."""
    cf = normalizza(value)
    if not re.fullmatch(r'[A-Z0-9]{16}', cf):
        raise ValidationError('Il codice fiscale deve avere 16 caratteri.')
    totale = 0
    for i, c in enumerate(cf[:15]):
        if i % 2 == 0:  # posizioni dispari (1ª, 3ª, ...)
            totale += _CF_ODD[c]
        else:
            totale += int(c) if c.isdigit() else ord(c) - ord('A')
    if chr(ord('A') + totale % 26) != cf[15]:
        raise ValidationError('Il codice fiscale non è corretto: controlla i caratteri inseriti.')


def valida_partita_iva(value):
    piva = normalizza(value)
    if not re.fullmatch(r'\d{11}', piva):
        raise ValidationError('La partita IVA deve avere 11 cifre.')
    s = 0
    for i, ch in enumerate(piva[:10]):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    if (10 - s % 10) % 10 != int(piva[10]):
        raise ValidationError('La partita IVA non è corretta: controlla le cifre inserite.')


def valida_cf_ente(value):
    """Codice fiscale di società o ente: 11 cifre (come la partita IVA) oppure 16 caratteri."""
    v = normalizza(value)
    if re.fullmatch(r'\d{11}', v):
        return valida_partita_iva(v)
    return valida_codice_fiscale(v)


def valida_iban(value):
    iban = normalizza(value)
    if not re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}', iban):
        raise ValidationError('IBAN non valido.')
    if iban.startswith('IT') and len(iban) != 27:
        raise ValidationError('Un IBAN italiano ha 27 caratteri.')
    riordinato = iban[4:] + iban[:4]
    numero = ''.join(str(int(c, 36)) for c in riordinato)
    if int(numero) % 97 != 1:
        raise ValidationError('IBAN non corretto: controlla i caratteri inseriti.')


def valida_pod(value):
    pod = normalizza(value)
    if not re.fullmatch(r'IT\d{3}E[0-9A-Z]{8,10}', pod):
        raise ValidationError('Il codice POD inizia con "IT" ed ha 14 o 15 caratteri (es. IT001E12345678).')


def valida_cap(value):
    if not re.fullmatch(r'\d{5}', (value or '').strip()):
        raise ValidationError('Il CAP ha 5 cifre.')
