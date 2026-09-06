from django.urls import path
from . import views

app_name = 'guichet'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('voyages/', views.VoyageListView.as_view(), name='voyage_list'),
    path('voyages/ajax/', views.voyage_list_ajax, name='voyage_list_ajax'),
    path('vente/<uuid:public_id>/', views.VenteView.as_view(), name='vente'),
    path('reservations/', views.ReservationsListView.as_view(), name='reservations'),
    path('reservations/ajax/', views.reservations_ajax, name='reservations_ajax'),

    # API endpoints
    path('api/creer-billet/<uuid:voyage_id>/', views.creer_billet, name='creer_billet'),
    path('api/payer/<uuid:billet_id>/', views.payer_reservation, name='payer_reservation'),
    path('api/vendre-autre/<uuid:billet_id>/', views.vendre_a_autre_client, name='vendre_a_autre_client'),
    path('api/sieges/<uuid:voyage_id>/', views.get_sieges_status, name='sieges_status'),
    path('api/billet/<uuid:billet_id>/', views.get_billet_info, name='billet_info'),
    path('api/destinations-billet/<uuid:billet_id>/', views.get_destinations_voyage, name='destinations_billet'),
    path('api/imprimer-billets/', views.imprimer_billets, name='imprimer_billets'),
]
