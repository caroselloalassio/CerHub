# core/views/api/cer.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
import logging

from ...models import CERConfiguration, Plant
from energy.models import DeviceMeasurement

logger = logging.getLogger(__name__)

@login_required
def cer_power_api(request):
    """API per dati di potenza in tempo reale delle CER"""
    try:
        time_threshold = timezone.now() - timedelta(minutes=5)
        
        # Recupera CER accessibili
        if request.user.is_staff:
            cer_list = CERConfiguration.objects.all()
        else:
            cer_list = CERConfiguration.objects.filter(
                memberships__user=request.user,
                memberships__is_active=True
            )
            
        cer_data = []
        for cer in cer_list:
            # Calcola potenze
            producer_power = 0
            consumer_power = 0
            
            plants = Plant.objects.filter(
                cer_configuration=cer,
                is_active=True
            )
            
            for plant in plants:
                device = plant.devices.first()
                if device:
                    measurement = DeviceMeasurement.objects.filter(
                        device=device,
                        timestamp__gte=time_threshold
                    ).order_by('-timestamp').first()
                    
                    if measurement:
                        if plant.plant_type == 'PRODUCER' and measurement.power > 0:
                            producer_power += measurement.power
                        elif plant.plant_type == 'CONSUMER':
                            consumer_power += abs(measurement.power)
            
            # Converti in kW
            producer_power_kw = round(producer_power / 1000.0, 2)
            consumer_power_kw = round(consumer_power / 1000.0, 2)
            net_power_kw = round(
                min(producer_power_kw, consumer_power_kw), 
                2
            )
            
            cer_data.append({
                'id': cer.id,
                'name': cer.name,
                'producer_power': producer_power_kw,
                'consumer_power': consumer_power_kw,
                'net_power': net_power_kw,
                'members_count': cer.gse_members_count,
                'plants_count': cer.production_plants_count,
                'withdrawal_points_count': cer.withdrawal_points_count
            })
            
        return JsonResponse({
            'data': cer_data,
            'timestamp': timezone.now().isoformat(),
            'total_cer': len(cer_data)
        })
        
    except Exception as e:
        logger.error(f"Error in cer_power_api: {str(e)}", exc_info=True)
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )