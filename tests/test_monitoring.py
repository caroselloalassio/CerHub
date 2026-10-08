"""
Test suite for Monitoring endpoints
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
import json


class HealthCheckEndpointsTest(TestCase):
    """Test health check and monitoring endpoints"""
    
    def setUp(self):
        """Set up test clients: anonymous and staff"""
        self.client = Client()
        # Solo /monitoring/health/ e' pubblica: le altre pagine sono riservate allo staff
        staff = get_user_model().objects.create_user(
            username='staff_monitoring', password='test-monitoring-pass',
            first_name='Staff', last_name='Monitoring', is_staff=True,
        )
        self.staff_client = Client()
        self.staff_client.force_login(staff)
    
    def test_health_endpoint_accessible(self):
        """Test that health endpoint is accessible"""
        response = self.client.get('/monitoring/health/')
        self.assertEqual(response.status_code, 200)
        
        # Check JSON response
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        self.assertIn('uptime', data)
    
    def test_database_health_endpoint(self):
        """Test database health endpoint"""
        response = self.staff_client.get('/monitoring/health/database/')
        self.assertIn(response.status_code, [200, 207, 503])  # Any valid health status
        
        data = response.json()
        self.assertIn('service', data)
        self.assertEqual(data['service'], 'database')
        self.assertIn('status', data)
    
    def test_status_endpoint(self):
        """Test aggregated status endpoint"""
        response = self.staff_client.get('/monitoring/status/')
        self.assertIn(response.status_code, [200, 207, 503])
        
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('services', data)
        self.assertIn('timestamp', data)
    
    def test_status_endpoint_detailed(self):
        """Test detailed status endpoint"""
        response = self.staff_client.get('/monitoring/status/?detailed=true')
        self.assertIn(response.status_code, [200, 207, 503])
        
        data = response.json()
        self.assertIn('details', data)
        self.assertIn('django_version', data['details'])
        self.assertIn('python_version', data['details'])
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        response = self.staff_client.get('/monitoring/metrics/')
        self.assertEqual(response.status_code, 200)
        
        # Check content type
        self.assertIn('text/plain', response['Content-Type'])
        
        # Check that it contains metrics
        content = response.content.decode('utf-8')
        self.assertIn('system_cpu_usage_percent', content)
        self.assertIn('system_memory_usage_percent', content)
    
    def test_health_endpoints_no_cache(self):
        """Test that health endpoints are not cached"""
        response = self.client.get('/monitoring/health/')
        
        # Check cache control headers
        self.assertIn('Cache-Control', response.headers)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertTrue(
            'no-cache' in cache_control or 'no-store' in cache_control
        )
    
    def test_all_monitoring_endpoints(self):
        """Test all monitoring endpoints return valid responses"""
        endpoints = [
            '/monitoring/health/',
            '/monitoring/health/database/',
            '/monitoring/status/',
            '/monitoring/metrics/',
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.staff_client.get(endpoint)
                # Should not return 404 or 500
                self.assertNotEqual(response.status_code, 404)
                self.assertNotEqual(response.status_code, 500)

    def test_detail_endpoints_require_staff(self):
        """Only the basic health endpoint is public; the others redirect to login"""
        self.assertEqual(self.client.get('/monitoring/health/').status_code, 200)

        endpoints = [
            '/monitoring/health/database/',
            '/monitoring/health/mqtt/',
            '/monitoring/health/cache/',
            '/monitoring/health/system/',
            '/monitoring/status/',
            '/monitoring/metrics/',
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/users/login/', response['Location'])