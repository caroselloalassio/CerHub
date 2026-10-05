# cercollettiva/cloudron_storage.py
import logging

from django.conf import settings
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class TolerantManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Come lo storage di WhiteNoise, ma un file statico citato in un template e
    assente dal progetto produce un link non funzionante (404 sul singolo file)
    invece di un errore 500 sull'intera pagina.
    """
    manifest_strict = False

    def url(self, name, force=False):
        try:
            return super().url(name, force=force)
        except ValueError:
            logger.warning("File statico mancante: %s", name)
            return settings.STATIC_URL + name
