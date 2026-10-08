"""
URL configuration for monitoring endpoints
"""
from django.contrib.auth.decorators import user_passes_test
from django.urls import path
from .views import (
    HealthCheckView,
    DatabaseHealthView,
    MQTTHealthView,
    CacheHealthView,
    SystemHealthView,
    StatusView,
    MetricsView
)

app_name = 'monitoring'

# Solo /monitoring/health/ resta pubblica (controllo di Cloudron, aggiornamento
# automatico e UptimeRobot). Le altre pagine mostrano dettagli del server e
# sono riservate allo staff: chi non lo e' viene mandato al login.
staff_only = user_passes_test(lambda u: u.is_active and u.is_staff)

urlpatterns = [
    # Basic health check
    path('health/', HealthCheckView.as_view(), name='health'),
    
    # Service-specific health checks
    path('health/database/', staff_only(DatabaseHealthView.as_view()), name='health_database'),
    path('health/mqtt/', staff_only(MQTTHealthView.as_view()), name='health_mqtt'),
    path('health/cache/', staff_only(CacheHealthView.as_view()), name='health_cache'),
    path('health/system/', staff_only(SystemHealthView.as_view()), name='health_system'),
    
    # Aggregated status
    path('status/', staff_only(StatusView.as_view()), name='status'),
    
    # Prometheus metrics
    path('metrics/', staff_only(MetricsView.as_view()), name='metrics'),
]