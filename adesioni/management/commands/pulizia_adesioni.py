from django.core.management.base import BaseCommand

from adesioni import services


class Command(BaseCommand):
    help = 'Elimina le domande di adesione compilate e mai firmate oltre il termine di conservazione.'

    def handle(self, *args, **options):
        self.stdout.write(f'Domande eliminate: {services.pulizia()}')
