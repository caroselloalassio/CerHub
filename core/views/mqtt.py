# core/views/mqtt.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.utils import timezone
import logging

from .base import BasePlantView
from ..models import Plant
from energy.models import DeviceConfiguration
from ..forms import PlantMQTTConfigForm

logger = logging.getLogger(__name__)

def check_mqtt_connection(host, port, username=None, password=None, use_ssl=False,
                          client_id=None, timeout=5):
    """
    Prova a collegarsi al broker MQTT indicato e restituisce True se il
    broker accetta la connessione entro `timeout` secondi.
    """
    import threading
    import paho.mqtt.client as mqtt

    connected = threading.Event()
    result = {'ok': False}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        is_failure = getattr(reason_code, 'is_failure', None)
        result['ok'] = (not is_failure) if is_failure is not None else (reason_code == 0)
        connected.set()

    client = mqtt.Client(
        client_id=client_id or '',
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.connect_timeout = timeout
    if username:
        client.username_pw_set(username, password or None)
    if use_ssl:
        client.tls_set()

    try:
        client.connect(host=host, port=int(port), keepalive=30)
        client.loop_start()
        connected.wait(timeout)
        return result['ok']
    except Exception as e:
        logger.info(f"Test connessione MQTT fallito verso {host}:{port}: {e}")
        return False
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass


class PlantMQTTConfigView(BasePlantView):
    """
    Configurazione MQTT per un impianto.

    Accessibile al proprietario dell'impianto e allo staff (404 per gli altri).
    """
    template_name = 'core/mqtt_config.html'
    form_class = PlantMQTTConfigForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plant = self.plant
        devices = list(DeviceConfiguration.objects.filter(plant=plant).order_by('device_id'))
        last_seen = max((d.last_seen for d in devices if d.last_seen), default=None)

        context.update({
            'plant': plant,
            'devices': devices,
            # Stato MQTT corrente (dati ricevuti negli ultimi 5 minuti)
            'mqtt_status': {
                'connected': bool(last_seen and
                                  (timezone.now() - last_seen).total_seconds() < 300),
                'last_seen': last_seen,
            },
        })
        return context

    def get(self, request, *args, **kwargs):
        self.plant = self.get_plant_if_allowed(kwargs['pk'])
        form = self.form_class(instance=self.plant)
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        self.plant = plant = self.get_plant_if_allowed(kwargs['pk'])
        form = self.form_class(request.POST, instance=plant)

        if not form.is_valid():
            messages.error(request, _("Controlla i dati inseriti."))
            return self.render_to_response(self.get_context_data(form=form))

        form.save()
        logger.info(f"MQTT config updated for plant {plant.id} by user {request.user}")

        # la prova di connessione apre un collegamento dal server verso un host
        # scelto da chi compila: è riservata allo staff
        if request.POST.get('action') != 'test' or not request.user.is_staff:
            messages.success(request, _("Configurazione MQTT aggiornata con successo"))
            return redirect('core:plant_detail', pk=plant.pk)

        # Salva e prova la connessione con i parametri appena salvati
        ok = check_mqtt_connection(
            host=plant.mqtt_broker,
            port=plant.mqtt_port,
            username=plant.mqtt_username,
            password=plant.mqtt_password,
            use_ssl=plant.use_ssl,
            client_id=f"{plant.mqtt_client_id}-test",
        )
        Plant.objects.filter(pk=plant.pk).update(mqtt_connected=ok)
        if ok:
            messages.success(
                request,
                _("Configurazione salvata. Connessione al broker MQTT riuscita.")
            )
        else:
            messages.warning(
                request,
                _("Configurazione salvata, ma la connessione al broker MQTT non è riuscita. "
                  "Verifica indirizzo, porta, SSL/TLS e credenziali.")
            )
        return redirect('core:plant_mqtt_config', pk=plant.pk)

def mqtt_reconnect_view(request, pk):
    """Vista per forzare la riconnessione MQTT"""
    plant = get_object_or_404(Plant, pk=pk)
    
    if not (request.user.is_staff or plant.owner == request.user):
        messages.error(request, _("Non hai i permessi per questa operazione"))
        return redirect('core:plant_list')
        
    try:
        if plant.test_mqtt_connection():
            messages.success(request, _("Riconnessione MQTT eseguita con successo"))
        else:
            messages.error(request, _("Riconnessione MQTT fallita"))
            
    except Exception as e:
        logger.error(
            f"Error reconnecting MQTT for plant {plant.id}: {str(e)}",
            exc_info=True
        )
        messages.error(request, str(e))
        
    return redirect('core:plant_detail', pk=pk)