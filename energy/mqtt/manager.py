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
            "cercollettiva/+/+/status/em:0",
             self._handle_power_message
        )
        self._mqtt_service.register_handler(
             "cercollettiva/+/+/status/emdata:0",
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
        try:
            current_timestamp = timezone.now()
            
            # Verifica duplicati usando una chiave più precisa
            msg_key = f"{device_config.device_id}_{current_timestamp.timestamp()}"
            if cache.get(msg_key):
                logger.debug(f"Messaggio duplicato ignorato: {msg_key}")
                return True

            # Estrai i valori con validazione
            power_value = float(payload.get('total_act_power', 0))
            energy_total = float(payload.get('total_act', 0))
            voltage = float(payload.get('a_voltage', 0))
            current_amp = float(payload.get('a_current', 0))
            power_factor = float(payload.get('total_pf', 1.0))

            # Salva con transazione atomica
            with transaction.atomic():
                measurement = DeviceMeasurement.objects.create(
                    device=device_config,
                    plant=device_config.plant,
                    timestamp=current_timestamp,
                    power=power_value,
                    voltage=voltage,
                    current=current_amp,
                    power_factor=power_factor,
                    energy_total=energy_total,
                    measurement_type='POWER',
                    quality='GOOD'
                )

                # Salva i dettagli delle fasi
                self._create_phase_details(measurement, payload)

                # Aggiorna last_seen
                device_config.last_seen = current_timestamp
                device_config.save(update_fields=['last_seen'])

                # Cache del messaggio processato
                cache.set(msg_key, True, timeout=300)

            return True

        except Exception as e:
            logger.error(f"Error in _handle_power_message: {str(e)}", exc_info=True)
            return False

    def _handle_energy_message(self, device_config, payload, topic):
        """Gestisce i messaggi di energia calcolando il delta tra letture consecutive"""
        try:
            current_timestamp = timezone.now()
            
            # Estrai il valore di energia totale dal payload (in Wh)
            current_energy_total = float(payload.get('total_act', 0))
            
            # Recupera l'ultimo valore di energia per questo dispositivo
            last_energy = self._last_energy_values.get(device_config.device_id)
            
            # Calcola il delta solo se abbiamo un valore precedente
            if last_energy is not None:
                energy_delta = current_energy_total - last_energy
                
                # Verifica che il delta sia positivo e ragionevole (es. max 100000 Wh = 100 kWh in 15 min)
                if 0 <= energy_delta <= 100000:  
                    # Crea la misurazione con il delta calcolato
                    measurement = DeviceMeasurement.objects.create(
                        device=device_config,
                        plant=device_config.plant,
                        timestamp=current_timestamp,
                        power=0,  # Per i messaggi di energia, la potenza istantanea non è disponibile
                        voltage=0,  # Valore di default
                        current=0,  # Valore di default
                        energy_total=energy_delta / 1000.0,  # Convertiamo da Wh a kWh prima di salvare
                        measurement_type='ENERGY',
                        quality='GOOD'
                    )
                    
                    logger.info(f"""
                        Energy delta calculated for device {device_config.device_id}:
                        - Previous reading: {last_energy:.3f} Wh
                        - Current reading: {current_energy_total:.3f} Wh
                        - Delta: {energy_delta:.3f} Wh ({energy_delta/1000.0:.3f} kWh)
                    """)
                else:
                    logger.warning(f"""
                        Invalid energy delta for device {device_config.device_id}:
                        - Previous reading: {last_energy:.3f} Wh
                        - Current reading: {current_energy_total:.3f} Wh
                        - Delta: {energy_delta:.3f} Wh
                    """)
            else:
                logger.info(f"First energy reading for device {device_config.device_id}: {current_energy_total:.3f} Wh")
            
            # Aggiorna l'ultimo valore per la prossima lettura (manteniamo il valore in Wh)
            self._last_energy_values[device_config.device_id] = current_energy_total
            
            # Aggiorna il timestamp dell'ultimo dato ricevuto
            device_config.update_last_seen()
            
            return True

        except Exception as e:
            logger.error(f"Error processing energy message: {str(e)}")
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