from django.urls import path
from . import views

app_name = 'sync'

urlpatterns = [
    path('ping/', views.ping, name='ping'),
    path('push/', views.push, name='push'),
    path('pull/', views.pull, name='pull'),
    path('statut/', views.statut, name='statut'),
    path('declencher/', views.declencher, name='declencher'),
]
