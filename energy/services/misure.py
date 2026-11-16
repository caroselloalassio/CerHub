# energy/services/misure.py
"""Energia oraria per POD e conservazione delle misure (CerHub).

- L'energia si salva per ora (EnergyAggregate, periodo '1H'): energy_out = prelievo
  dalla rete, energy_in = immissione, in kWh. È il dato che serve alla CER (il GSE
  calcola l'energia condivisa ora per ora) e si conserva senza scadenza.
- La potenza si salva al massimo una volta al minuto (media del minuto) e si
  conserva per CERHUB_POWER_RETENTION_DAYS giorni (predefinito 7).
- Il dettaglio per fase non si salva più.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from ..models import DeviceMeasurement, DeviceMeasurementDetail, EnergyAggregate

logger = logging.getLogger('energy.mqtt')

PERIODO_ORARIO = '1H'


def giorni_conservazione_potenza() -> int:
    return int(getattr(settings, 'CERHUB_POWER_RETENTION_DAYS', 7))


def _inizio_ora(t):
    return t.replace(minute=0, second=0, microsecond=0)


def aggiungi_energia_oraria(device, inizio, fine, kwh_prelevati, kwh_immessi):
    """Somma l'energia alle ore che cadono tra inizio e fine, in proporzione al tempo
    (se l'app è rimasta ferma, l'energia del periodo si distribuisce sulle ore)."""
    if kwh_prelevati <= 0 and kwh_immessi <= 0:
        return
    durata = (fine - inizio).total_seconds()
    quote = []
    if durata <= 0:
        quote.append((_inizio_ora(fine), 1.0))
    else:
        t = inizio
        while t < fine:
            ora = _inizio_ora(t)
            successivo = min(ora + timedelta(hours=1), fine)
            quote.append((ora, (successivo - t).total_seconds() / durata))
            t = successivo
    with transaction.atomic():
        for ora, quota in quote:
            agg = (EnergyAggregate.objects.select_for_update()
                   .filter(device=device, period=PERIODO_ORARIO, start_time=ora).first())
            if agg is None:
                agg = EnergyAggregate.objects.create(
                    device=device, period=PERIODO_ORARIO, start_time=ora,
                    end_time=ora + timedelta(hours=1), timestamp=ora)
            EnergyAggregate.objects.filter(pk=agg.pk).update(
                energy_out=F('energy_out') + kwh_prelevati * quota,
                energy_in=F('energy_in') + kwh_immessi * quota,
            )


def energia_oggi(devices):
    """Energia di oggi (giorno locale) in kWh: (prelevata, immessa)."""
    inizio = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    tot = EnergyAggregate.objects.filter(
        device__in=devices, period=PERIODO_ORARIO, start_time__gte=inizio
    ).aggregate(prelevata=Sum('energy_out'), immessa=Sum('energy_in'))
    return float(tot['prelevata'] or 0), float(tot['immessa'] or 0)


def pulisci_misure(adesso=None) -> dict:
    """Elimina le misure che non servono più. Si può rilanciare quante volte si vuole."""
    adesso = adesso or timezone.now()
    risultato = {}

    # Vecchie righe ENERGY (energia al minuto, solo prelievo): prima si riportano
    # nell'energia oraria, poi si eliminano. Il nuovo codice non le crea più.
    vecchie = DeviceMeasurement.objects.filter(measurement_type='ENERGY').select_related('device')
    convertite = 0
    with transaction.atomic():
        for m in vecchie.iterator():
            if m.device_id and m.energy_total and m.energy_total > 0:
                aggiungi_energia_oraria(m.device, m.timestamp, m.timestamp, m.energy_total, 0)
                convertite += 1
        risultato['energia_convertita'] = convertite
        risultato['righe_energia_eliminate'] = vecchie.delete()[0]

    # Dettaglio per fase: non più usato
    risultato['dettagli_fase_eliminati'] = DeviceMeasurementDetail.objects.all().delete()[0]

    # Potenza: si tiene solo il periodo recente
    limite = adesso - timedelta(days=giorni_conservazione_potenza())
    risultato['potenze_eliminate'] = DeviceMeasurement.objects.filter(timestamp__lt=limite).delete()[0]

    logger.info(f"Pulizia misure: {risultato}")
    return risultato
