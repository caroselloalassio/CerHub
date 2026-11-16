# energy/mqtt/manager.py
import json
import threading
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.core.cache import cache
from collections import deque 
from ..devices.registry import DeviceRegistry
from ..devices.base.device import MeasurementData, BaseDevice
from ..models import DeviceMeasurement, DeviceConfiguration, DeviceMeasurementDetail
from ..services.misure import aggiungi_energia_oraria, pulisci_misure
from .core import get_mqtt_service, MQTTMessage, TopicMatcher
from core.models import Plant

logger = logging.getLogger('energy.mqtt')

class DeviceManager:
    """Gestore dei dispositivi e delle loro misurazioni"""
    
    def __init__(self):
        # Inizializzazione thread safety
        self._lock = threading.Lock()
        
        # Inizializzazione stati
        self._configs_loaded = False
        self._topic_stats = {}
        self._active_topics = set()
        
        # Servizi e registry
        self._mqtt_service = get_mqtt_service()
        self._device_registry = DeviceRegistry()
        
        # Collections e cache
        self._devices = {}
        self._configs = {}
        self._last_energy_values = {}
        # Potenza: letture del minuto in corso per dispositivo (si salva la media)
        self._power_buffers = {}
        self._last_cleanup = None
        self._message_buffer = deque(maxlen=1000)
        self._cache_timeout = 3600
        
        # Caricamento configurazioni e setup handlers
        with self._lock:
            self._load_configurations()
            self._setup_message_handlers()

    def _is_duplicate(self, device_id: str, timestamp: datetime) -> bool:
        """Verifica duplicati con cache"""
        cache_key = f"last_msg_{device_id}"
        last_timestamp = cache.get(cache_key)
        
        if last_timestamp:
            time_diff = (timestamp - last_timestamp).total_seconds()
            if time_diff < 1:  # Configurabile in base alle esigenze
                logger.debug(f"Duplicate message detected for device {device_id}")
                return True
            
        cache.set(cache_key, timestamp, timeout=self._cache_timeout)
        return False

    def _setup_message_handlers(self):
        """Configura gli handler per i messaggi MQTT"""
        self._mqtt_service.register_handler(
            "cerhub/+/+/status/em:0",
             self._handle_power_message
        )
        self._mqtt_service.register_handler(
             "cerhub/+/+/status/emdata:0",
             self._handle_energy_message
        )

        self._mqtt_service.register_handler(
            "VePro/+/+/status/em:0",
            self._handle_power_message
        )
        self._mqtt_service.register_handler(
            "VePro/+/+/status/emdata:0",
            self._handle_energy_message
        )

    def _setup_cache_policy(self):
        """Configura policy di retention dati per GDPR"""
        self._cache_timeout = getattr(settings, 'MQTT_CACHE_TIMEOUT', 3600)
        self._data_retention = getattr(settings, 'MQTT_DATA_RETENTION_DAYS', 30)

    def _load_configurations(self) -> None:
        """Carica le configurazioni dei dispositivi dal database"""
        try:
            # Verifica se le configurazioni sono già caricate
            if self._configs_loaded:
                logger.debug("Configurations already loaded, skipping")
                return
                
            logger.info("Loading configurations...")
            configs = DeviceConfiguration.objects.filter(
                is_active=True
            ).select_related('plant')

            print("\n=== Configurazioni Dispositivi Trovate ===")
            print(f" |   Trovate {configs.count()} configurazioni attive   |")
            print("==========================================\n")
            
            # Reset delle configurazioni
            self._devices.clear()
            self._configs.clear()
            self._topic_stats.clear()
            self._active_topics.clear()
            
            for config in configs:
                self._load_single_config(config)

            print("\n============= Riepilogo ==================")
            print(f" |   Dispositivi caricati: {list(self._devices.keys())}")
            print("==========================================\n")
            
            # Marca le configurazioni come caricate
            self._configs_loaded = True

        except Exception as e:
            logger.error(f"Error loading configurations: {e}")
            raise

    def _load_single_config(self, config: DeviceConfiguration) -> None:
        """Carica una singola configurazione dispositivo"""
        try:
            # Log con dati mascherati per GDPR
            device_id_masked = f"{config.device_id[:3]}...{config.device_id[-3:]}"
            logger.debug(f"Caricamento dispositivo: {device_id_masked}")
            
            device = self._device_registry.get_device_by_vendor_model(
                config.vendor, 
                config.model
            )
            
            if device and config.mqtt_topic_template:
                self._devices[config.device_id] = device
                self._configs[config.device_id] = config
                self._last_energy_values[config.device_id] = None #inizializzo il valore
                #logger.info(f"Dispositivo {device_id_masked} caricato con successo")
            else:
                self._log_config_errors(config, device)
                
        except Exception as e:
            logger.error(f"Errore caricamento dispositivo {config.device_id}: {e}")

    def _handle_power_message(self, device_config, payload, topic):
        """Potenza: una riga al minuto con la media delle letture del minuto.

        Prima si salvava una riga per ogni messaggio (circa ogni 14 secondi) più tre
        righe di dettaglio per fase, mai lette dall'app.
        """
        try:
            adesso = timezone.now()
            potenza = float(payload.get('total_act_power', 0))
            minuto = adesso.replace(second=0, microsecond=0)
            chiave = device_config.device_id

            with self._lock:
                buf = self._power_buffers.get(chiave)
                if buf and buf['minuto'] != minuto:
                    self._salva_minuto(device_config, buf)
                    buf = None
                if buf is None:
                    buf = {'minuto': minuto, 'somma': 0.0, 'conteggio': 0, 'ultimo': payload}
                    self._power_buffers[chiave] = buf
                buf['somma'] += potenza
                buf['conteggio'] += 1
                buf['ultimo'] = payload

            self._pulizia_periodica(adesso)
            return True

        except Exception as e:
            logger.error(f"Error in _handle_power_message: {str(e)}", exc_info=True)
            return False

    def _salva_minuto(self, device_config, buf):
        """Salva la media della potenza di un minuto."""
        ultimo = buf['ultimo']
        tensioni = [float(ultimo.get(f'{fase}_voltage') or 0) for fase in 'abc']
        attiva = float(ultimo.get('total_act_power') or 0)
        apparente = float(ultimo.get('total_aprt_power') or 0)
        DeviceMeasurement.objects.create(
            device=device_config,
            plant=device_config.plant,
            timestamp=buf['minuto'],
            power=buf['somma'] / buf['conteggio'],
            voltage=max(tensioni),  # la fase collegata (con una sola fase le altre sono a 0)
            current=float(ultimo.get('total_current') or 0),
            power_factor=round(abs(attiva) / apparente, 3) if apparente > 0 else 1.0,
            energy_total=0,
            measurement_type='POWER',
            quality='GOOD'
        )

    def _pulizia_periodica(self, adesso):
        """Ogni 6 ore elimina le misure che non servono più."""
        if self._last_cleanup and adesso - self._last_cleanup < timedelta(hours=6):
            return
        self._last_cleanup = adesso
        try:
            pulisci_misure(adesso)
        except Exception as e:
            logger.error(f"Errore nella pulizia delle misure: {e}", exc_info=True)

    def _handle_energy_message(self, device_config, payload, topic):
        """Energia oraria (prelievo e immissione) dai contatori totali del dispositivo.

        I contatori dell'ultima lettura sono salvati nel database, quindi l'energia
        consumata mentre l'app è ferma (aggiornamenti, riavvii) non si perde: si
        distribuisce sulle ore del periodo. Prima si teneva solo in memoria il
        contatore del prelievo e l'immissione era ignorata.
        """
        try:
            adesso = timezone.now()
            prelievo = payload.get('total_act')
            if prelievo is None:
                return False
            prelievo = float(prelievo)
            immissione = float(payload.get('total_act_ret') or 0)

            prec_prelievo = device_config.last_energy_total
            prec_immissione = device_config.last_energy_ret_total
            prec_at = device_config.last_energy_at

            if prec_prelievo is not None and prec_at is not None:
                d_prelievo = prelievo - prec_prelievo
                d_immissione = immissione - prec_immissione if prec_immissione is not None else 0.0
                ore = max((adesso - prec_at).total_seconds() / 3600.0, 1 / 60)
                if d_prelievo < 0 or d_immissione < 0:
                    logger.warning(
                        f"Contatori di {device_config.device_id} diminuiti (dispositivo azzerato?): "
                        f"si riparte dai nuovi valori"
                    )
                elif (d_prelievo + d_immissione) / 1000.0 > 250 * ore:
                    logger.warning(
                        f"Salto di energia non plausibile per {device_config.device_id}: "
                        f"{d_prelievo:.0f} Wh prelievo, {d_immissione:.0f} Wh immissione in {ore:.2f} h"
                    )
                else:
                    aggiungi_energia_oraria(
                        device_config, prec_at, adesso,
                        d_prelievo / 1000.0, d_immissione / 1000.0
                    )

            # update() e non save(): non deve far partire il segnale che ricarica le configurazioni
            DeviceConfiguration.objects.filter(pk=device_config.pk).update(
                last_energy_total=prelievo,
                last_energy_ret_total=immissione,
                last_energy_at=adesso,
            )
            device_config.last_energy_total = prelievo
            device_config.last_energy_ret_total = immissione
            device_config.last_energy_at = adesso
            return True

        except Exception as e:
            logger.error(f"Error processing energy message: {str(e)}", exc_info=True)
            return False

    def _create_phase_details(self, measurement: DeviceMeasurement, payload: Dict[str, Any]):
        """Crea i dettagli delle misurazioni per fase"""
        phases = ['a', 'b', 'c']
        for phase in phases:
            if all(key in payload for key in [f'{phase}_voltage', f'{phase}_current', f'{phase}_act_power']):
                DeviceMeasurementDetail.objects.create(
                    measurement=measurement,
                    phase=phase,
                    voltage=payload.get(f'{phase}_voltage', 0),
                    current=payload.get(f'{phase}_current', 0),
                    power=payload.get(f'{phase}_act_power', 0),
                    power_factor=payload.get(f'{phase}_pf', 1.0),
                    frequency=payload.get(f'{phase}_freq', 50.0)
                )

    def _log_config_errors(self, config: DeviceConfiguration, device: Optional[BaseDevice]):
        """Registra gli errori di configurazione in modo sicuro"""
        device_id_masked = f"{config.device_id[:3]}...{config.device_id[-3:]}"
        if not device:
            logger.warning(f"Dispositivo {device_id_masked}: vendor/model non supportato")
        if not config.mqtt_topic_template:
            logger.warning(f"Dispositivo {device_id_masked}: template MQTT mancante")

    def get_subscription_topics(self) -> List[str]:
        """Ottiene tutti i topic da sottoscrivere"""
        topics = []
        for device_id, config in self._configs.items():
            device = self._devices.get(device_id)
            if device and config.mqtt_topic_template:
                base_topic = '/'.join(config.mqtt_topic_template.split('/')[:3])
                device_topics = device.get_topics(base_topic)
                topics.extend(device_topics)
        return list(set(topics))

    def refresh_configurations(self) -> None:
        """Aggiorna le configurazioni dei dispositivi"""
        self._load_configurations()
        if self._mqtt_service.is_connected:
            topics = self.get_subscription_topics()
            for topic in topics:
                self._mqtt_service.register_handler(topic, self._handle_power_message)
    
    def _find_device_for_topic(self, topic: str) -> Optional[DeviceConfiguration]:
        try:
            #logger.info(f"Processing topic: {topic}")
            
            # Cerca tra tutti i device configurati nel database
            devices = DeviceConfiguration.objects.filter(is_active=True)
            #logger.info(f"Found {devices.count()} active devices in DB")
            
            for device in devices:
                #logger.info(f"\nChecking device: {device.device_id}")
                #logger.info(f"MQTT template: {device.mqtt_topic_template}")
                
                if not device.mqtt_topic_template:
                    logger.warning(f"Device {device.device_id} has no MQTT template")
                    continue
                    
                # Ottieni il topic base rimuovendo il suffisso
                base_topic = device.mqtt_topic_template.replace('/status/em:0', '')
                
                # Costruisci i topic possibili per questo device
                device_topics = [
                    f"{base_topic}/status/em:0",
                    f"{base_topic}/status/emdata:0"
                ]
                
                #logger.info(f"Possible topics for device {device.device_id}:")
                for dt in device_topics:
                    logger.info(f"  - {dt}")
                
                # Confronta il topic ricevuto con i topic possibili del device
                if topic in device_topics:
                    #logger.info(f"Match found! Device: {device.device_id}, Plant: {device.plant.name}")
                    return device
                
            logger.warning(f"No device found for topic: {topic}")
            return None
                
        except Exception as e:
            logger.error(f"Error searching device for topic {topic}: {str(e)}", 
                        exc_info=True)
            return None
    
    def process_message(self, topic: str, data: Any) -> bool:
        try:
            #logger.info(f"\n=== PROCESS MESSAGE START ===")
            #logger.info(f"Processing topic: {topic}")
            
            device_config = self._find_device_for_topic(topic)
            if not device_config:
                logger.warning(f"No device found for topic: {topic}")
                return False

            payload = self._parse_payload(data)
            if not payload:
                return False
                    
            msg_key = f"{topic}_{device_config.device_id}__{hash(str(payload))}"
            
            # Verifica duplicati con chiave univoca
            if cache.get(msg_key):
                logger.debug(f"Duplicate message detected: {msg_key}")
                return True

            # Salvo il messaggio e processo
            with transaction.atomic():
                success = False
                if 'em:0' in topic:
                    success = self._handle_power_message(device_config, payload, topic)
                elif 'emdata:0' in topic:
                    success = self._handle_energy_message(device_config, payload, topic)
                else:
                    logger.warning(f"Unsupported topic format: {topic}")
                    return False
                        
                if success:
                    # Marca il messaggio come processato
                    cache.set(msg_key, True, timeout=300) 
                    #logger.info(f"Message processed successfully: {msg_key}") 
                    
                    # Aggiorna solo last_seen, senza refresh delle configurazioni
                    with self._lock:
                        device_config.last_seen = timezone.now()
                        device_config.save(update_fields=['last_seen'])
                    
                    return True
                        
                return False

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return False

    def _parse_payload(self, data: Any) -> Optional[Dict]:
        """Decodifica il payload JSON in modo sicuro"""
        try:
            if isinstance(data, bytes):
                return json.loads(data.decode('utf-8'))
            elif isinstance(data, str): 
                return json.loads(data)
            elif isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None

    def _anonymize_topic(self, topic: str) -> str:
            """Anonimizza i dati sensibili nel topic per GDPR"""
            parts = topic.split('/')
            if len(parts) >= 3:
                # Maschera l'identificativo del dispositivo/POD
                parts[2] = f"{parts[2][:3]}...{parts[2][-3:]}"
            return '/'.join(parts)