# core/views/api/mqtt.py

from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from ...models import Plant
from energy.models import DeviceConfiguration

logger = logging.getLogger(__name__)

@login_required
def mqtt_status_api(request, plant_id):
    """API per stato connessione MQTT"""
    try:
        # Verifica permessi
        if request.user.is_staff:
            plant = get_object_or_404(Plant, id=plant_id)
        else:
            plant = get_object_or_404(Plant, id=plant_id, owner=request.user)
            
        # Recupera device
        device = DeviceConfiguration.objects.filter(plant=plant).first()
        
        # Verifica stato connessione
        is_connected = False
        last_seen = None
        
        if device:
            if device.last_seen:
                time_diff = (timezone.now() - device.last_seen).total_seconds()
                is_connected = time_diff < 300  # 5 minuti
                last_seen = device.last_seen.isoformat()
                
        return JsonResponse({
            'mqtt_status': {
                'connected': is_connected,
                'last_seen': last_seen
            },
            'device_info': {
                'id': device.device_id if device else None,
                'type': device.get_device_type_display() if device else None
            } if device else None
        })
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in mqtt_status_api: {str(e)}", exc_info=True)
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )