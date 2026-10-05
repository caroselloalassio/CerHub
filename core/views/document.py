# core/views/document.py
#
# I documenti degli impianti sono gestiti dall'app "documents".
# Le rotte storiche sotto /plants/<id>/documents/ restano valide e
# reindirizzano alle pagine di quell'app, dopo aver verificato che
# l'utente possa accedere all'impianto.

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .base import BasePlantView
from ..models import PlantDocument


def plant_documents_url(plant_id):
    """URL della lista documenti (app documents) filtrata per impianto"""
    return f"{reverse('documents:list')}?plant={plant_id}"


class PlantDocumentListView(BasePlantView):
    """Lista documenti di un impianto: reindirizza alla lista dell'app documents"""
    http_method_names = ['get', 'head', 'options']

    def get(self, request, *args, **kwargs):
        plant = self.get_plant_if_allowed(kwargs['pk'])
        return redirect(plant_documents_url(plant.pk))


class PlantDocumentUploadView(BasePlantView):
    """Caricamento documento per un impianto: reindirizza al caricamento dell'app documents"""
    http_method_names = ['get', 'head', 'options']

    def get(self, request, *args, **kwargs):
        plant = self.get_plant_if_allowed(kwargs['pk'])
        return redirect('documents:upload', plant_id=plant.pk)


class PlantDocumentDeleteView(BasePlantView):
    """
    Eliminazione di un documento d'archivio (modello PlantDocument,
    caricato dall'area di amministrazione). Solo POST.
    """
    http_method_names = ['post', 'options']

    def post(self, request, *args, **kwargs):
        plant = self.get_plant_if_allowed(kwargs['pk'])
        document = get_object_or_404(
            PlantDocument,
            pk=kwargs['document_id'],
            plant=plant
        )

        try:
            document_name = document.name
            document.delete()
            messages.success(
                request,
                _('Documento "%(name)s" eliminato con successo') % {'name': document_name}
            )
        except Exception as e:
            messages.error(request, str(e))

        return redirect(plant_documents_url(plant.pk))
