from django.urls import path

from . import views

app_name = 'adesioni'

urlpatterns = [
    path('', views.scelta, name='scelta'),
    path('privati/', views.compila, {'tipo': 'PRIVATO'}, name='privati'),
    path('aziende/', views.compila, {'tipo': 'AZIENDA'}, name='aziende'),
    path('le-mie/', views.mie, name='mie'),
    path('<uuid:token>/', views.riepilogo, name='riepilogo'),
    path('<uuid:token>/modifica/', views.modifica, name='modifica'),
    path('<uuid:token>/firma/', views.firma, name='firma'),
    path('<uuid:token>/firmata/', views.ritorno, name='ritorno'),
    path('<uuid:token>/documento/<str:quale>/', views.documento, name='documento'),
]
