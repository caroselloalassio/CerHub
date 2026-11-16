# energy/management/commands/pulizia_misure.py
from django.core.management.base import BaseCommand

from energy.services.misure import pulisci_misure, giorni_conservazione_potenza


class Command(BaseCommand):
    help = ("Elimina le misure che non servono più: potenza più vecchia del periodo di "
            "conservazione, dettaglio per fase, vecchie righe di energia al minuto "
            "(riportate prima nell'energia oraria). L'app la esegue da sola ogni 6 ore.")

    def handle(self, *args, **options):
        risultato = pulisci_misure()
        self.stdout.write(f"Conservazione potenza: {giorni_conservazione_potenza()} giorni")
        for chiave, valore in risultato.items():
            self.stdout.write(f"{chiave}: {valore}")
