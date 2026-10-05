# documents/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, ListView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Document, DocumentAccess
from .forms import DocumentUploadForm
from core.models import Plant

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import redirect
from django.conf import settings
#import os
#import magic

from django.views.generic.edit import DeleteView

from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger(__name__)


def user_can_access_plant(user, plant):
    """Lo staff accede a tutti gli impianti, gli altri utenti solo ai propri"""
    return user.is_staff or user.is_superuser or plant.owner_id == user.pk


class DocumentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Document
    template_name = 'documents/document_confirm_delete.html'
    
    def test_func(self):
        document = self.get_object()
        return self.request.user == document.uploaded_by
    
    def get_success_url(self):
        # Se la richiesta proviene dalla pagina del profilo, torna al profilo
        referer = self.request.META.get('HTTP_REFERER', '')
        if '/users/profile/' in referer:
            return reverse_lazy('users:profile')
        return reverse_lazy('documents:list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Il documento è stato eliminato con successo.")
        return super().delete(request, *args, **kwargs)
    
    def handle_no_permission(self):
        messages.error(self.request, "Non hai i permessi per eliminare questo documento.")
        return redirect('documents:list')
    
class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/list.html'
    context_object_name = 'documents'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        documents = self.get_queryset()
        
        # Inizializza il dizionario document_groups
        context['document_groups'] = {
            'identity': documents.filter(type='ID_DOC'),
            'technical': documents.filter(type__in=['SYSTEM_CERT', 'PANELS_PHOTO', 'INVERTER_PHOTO', 'PANELS_LIST']),
            'administrative': documents.filter(type__in=['BILL', 'GSE_DOC']),
            'other': documents.filter(type='OTHER'),
            'gaudi': documents.filter(type='GAUDI')  # Aggiunto qui il gruppo gaudi
        }
        
        # Documenti in scadenza
        context['expiring_documents'] = documents.filter(
            retention_date__lte=timezone.now().date() + timezone.timedelta(days=30)
        )
        
        # Documenti con dati personali
        if self.request.user.has_perm('documents.view_personal_data'):
            context['personal_documents'] = documents.filter(
                Q(type__in=['ID_DOC', 'BILL']) | Q(data_classification='PERSONAL')
            )
        
        # Plant context se arriva dalla vista di un impianto
        plant = self.get_plant()
        if plant:
            context['plant'] = plant
            # Documenti d'archivio caricati dall'area di amministrazione
            context['legacy_documents'] = plant.documents.all()
            
        return context

    def get_plant(self):
        """
        Impianto indicato con ?plant=<id>, se presente.
        Risponde 404 se l'impianto non esiste o l'utente non puo' accedervi.
        """
        if not hasattr(self, '_plant'):
            self._plant = None
            plant_id = self.request.GET.get('plant')
            if plant_id:
                if not plant_id.isdigit():
                    raise Http404
                plant = get_object_or_404(Plant, pk=plant_id)
                if not user_can_access_plant(self.request.user, plant):
                    raise Http404
                self._plant = plant
        return self._plant

    def get_queryset(self):
        plant = self.get_plant()
        if plant:
            # Tutti i documenti dell'impianto (accesso gia' verificato in get_plant)
            base_queryset = Document.objects.filter(plant=plant).select_related('plant')
        else:
            base_queryset = Document.objects.filter(
                uploaded_by=self.request.user
            ).select_related('plant')
        
        # Filtra documenti confidenziali se l'utente non ha i permessi
        if not self.request.user.has_perm('documents.view_confidential'):
            base_queryset = base_queryset.exclude(data_classification='CONFIDENTIAL')
            
        return base_queryset

class DocumentUploadView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentUploadForm
    template_name = 'documents/upload.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Ottieni l'impianto dal parametro URL (solo se l'utente puo' gestirlo)
        self.plant = get_object_or_404(Plant, pk=self.kwargs.get('plant_id'))
        if not user_can_access_plant(request.user, self.plant):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plant'] = self.plant
        return context

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        form.instance.source = 'USER'
        form.instance.plant = self.plant
        
        # Imposta automaticamente la classificazione per documenti con dati personali
        if form.instance.type in ['ID_DOC', 'BILL']:
            form.instance.data_classification = 'PERSONAL'
        
        response = super().form_valid(form)
        messages.success(self.request, "Documento caricato con successo.")
        return response

    def get_success_url(self):
        # Ritorna alla pagina dell'impianto dopo il caricamento
        return reverse_lazy('core:plant_detail', kwargs={'pk': self.plant.pk})

class DocumentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Document
    template_name = 'documents/detail.html'
    context_object_name = 'document'

    def test_func(self):
        document = self.get_object()
        user = self.request.user
        
        # Verifica permessi base: chi ha caricato il documento, lo staff
        # oppure il proprietario dell'impianto a cui il documento e' associato
        is_plant_owner = bool(document.plant_id and document.plant.owner_id == user.pk)
        if document.uploaded_by != user and not user.is_staff and not is_plant_owner:
            return False
            
        # Verifica permessi speciali
        if document.data_classification == 'CONFIDENTIAL':
            return user.has_perm('documents.view_confidential')
        if document.contains_personal_data:
            return user.has_perm('documents.view_personal_data')
            
        return True

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Registra l'accesso
        DocumentAccess.objects.create(
            document=obj,
            accessed_by=self.request.user,
            access_ip=self.request.META.get('REMOTE_ADDR')
        )
        return obj

class GaudiUploadView(DocumentUploadView):
    """View specializzata per il caricamento degli attestati Gaudì"""
    template_name = 'documents/gaudi_upload.html'

    def form_valid(self, form):
        form.instance.type = 'GAUDI'
        form.instance.data_classification = 'CONFIDENTIAL'
        return super().form_valid(form)

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)

class GaudiDetailView(DocumentDetailView):
    """View specializzata per i dettagli degli attestati Gaudì"""
    template_name = 'documents/gaudi_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_object()
        
        # Aggiungi dati specifici Gaudì
        if document.plant and document.plant.gaudi_verified:
            context['gaudi_data'] = {
                'request_code': document.plant.gaudi_request_code,
                'censimp_code': document.plant.censimp_code,
                'validation_date': document.plant.validation_date,
                'nominal_power': document.plant.nominal_power,
                'expected_production': document.plant.expected_yearly_production,
            }
            
        return context

@require_POST
@login_required
def process_gaudi_attestation(request, pk):
    """
    Endpoint per elaborare manualmente un attestato Gaudì
    Utile in caso di errori nell'elaborazione automatica
    """
    document = get_object_or_404(Document, pk=pk, type='GAUDI')
    
    # Verifica permessi
    if not request.user.is_staff and document.plant.owner != request.user:
        return JsonResponse({
            'success': False,
            'error': "Non hai i permessi per elaborare questo documento"
        }, status=403)

    try:
        success = document.process_gaudi_attestation()
        if success:
            messages.success(request, "Attestato Gaudì elaborato con successo")
            return JsonResponse({'success': True})
        else:
            return JsonResponse({
                'success': False,
                'error': document.processing_errors
            }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def upload_gaudi_attestation(request, plant_id):
    """View per caricare un attestato Gaudì"""
    logger.info("=== Inizio Upload Attestato Gaudì ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"Content Type: {request.content_type}")
    logger.info(f"Files disponibili: {list(request.FILES.keys())}")
    logger.info(f"POST data disponibile: {list(request.POST.keys())}")
    
    if request.method != 'POST':
        logger.warning("Metodo non consentito")
        return JsonResponse({
            'success': False,
            'error': 'Metodo non consentito'
        }, status=405)
    
    if 'attestation' not in request.FILES:
        logger.warning("File attestation non trovato nella richiesta")
        logger.warning(f"Files ricevuti: {request.FILES}")
        return JsonResponse({
            'success': False,
            'error': 'Nessun file caricato'
        }, status=400)

    try:
        file = request.FILES['attestation']
        logger.info(f"File ricevuto: {file.name} ({file.content_type}, {file.size} bytes)")
        
        plant = get_object_or_404(Plant, id=plant_id)
        
        if not request.user.is_staff and plant.owner != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Non hai i permessi per questo impianto'
            }, status=403)

        document = Document.objects.create(
            type='GAUDI',
            file=file,
            plant=plant,
            uploaded_by=request.user,
            source='USER',
            notes=request.POST.get('notes', ''),
            gdpr_consent=request.POST.get('gdpr_consent') == 'on'
        )

        logger.info(f"Documento creato con successo (ID: {document.id})")

        return JsonResponse({
            'success': True,
            'document_id': document.id,
            'message': 'Attestato caricato con successo'
        })

    except Exception as e:
        logger.error(f"Errore durante l'upload: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def gaudi_processing_status(request, pk):
    """Endpoint per verificare lo stato di elaborazione"""
    document = get_object_or_404(Document, pk=pk, type='GAUDI')
    
    # Verifica permessi
    if not request.user.is_staff and document.plant.owner != request.user:
        return JsonResponse({
            'success': False,
            'error': _('Non hai i permessi per questo documento')
        }, status=403)

    return JsonResponse({
        'success': True,
        'status': document.processing_status,
        'errors': document.processing_errors if document.processing_status == 'FAILED' else None,
        'processed_at': document.processed_at.isoformat() if document.processed_at else None
    })

@login_required
def gaudi_attestation_details(request, pk):
    """View per visualizzare i dettagli di un attestato Gaudì"""
    document = get_object_or_404(Document, pk=pk, type='GAUDI')
    
    # Verifica permessi
    if not request.user.is_staff and document.plant.owner != request.user:
        return JsonResponse({
            'success': False,
            'error': _('Non hai i permessi per questo documento')
        }, status=403)

    # Registra l'accesso al documento
    document.record_access(request.user)

    return JsonResponse({
        'success': True,
        'document': {
            'id': document.id,
            'uploaded_at': document.uploaded_at.isoformat(),
            'uploaded_by': document.uploaded_by.get_full_name() or document.uploaded_by.username,
            'plant': {
                'id': document.plant.id,
                'name': document.plant.name,
                'pod_code': document.plant.pod_code
            },
            'gaudi_data': {
                'request_code': document.plant.gaudi_request_code,
                'censimp_code': document.plant.censimp_code,
                'validation_date': document.plant.validation_date.isoformat() if document.plant.validation_date else None,
                'verified': document.plant.gaudi_verified
            } if document.plant else None
        }
    })