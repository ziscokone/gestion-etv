from django.urls import path
from . import views

app_name = 'vehicules'

urlpatterns = [
    # Modèles de véhicules
    path('modeles/', views.ModeleVehiculeListView.as_view(), name='modele_list'),
    path('modeles/ajax/', views.modele_list_ajax, name='modele_list_ajax'),
    path('modeles/ajouter/', views.ModeleVehiculeCreateView.as_view(), name='modele_create'),
    path('modeles/<int:pk>/modifier/', views.ModeleVehiculeUpdateView.as_view(), name='modele_update'),
    path('modeles/<int:pk>/supprimer/', views.ModeleVehiculeDeleteView.as_view(), name='modele_delete'),

    # Véhicules
    path('', views.VehiculeListView.as_view(), name='vehicule_list'),
    path('ajax/', views.vehicule_list_ajax, name='vehicule_list_ajax'),
    path('ajouter/', views.VehiculeCreateView.as_view(), name='vehicule_create'),
    path('<int:pk>/modifier/', views.VehiculeUpdateView.as_view(), name='vehicule_update'),
    path('<int:pk>/supprimer/', views.VehiculeDeleteView.as_view(), name='vehicule_delete'),

    # Réparations
    path('reparations/', views.ReparationVehiculeListView.as_view(), name='reparation_list'),
    path('reparations/ajax/', views.reparation_list_ajax, name='reparation_list_ajax'),
    path('reparations/ajouter/', views.ReparationVehiculeCreateView.as_view(), name='reparation_create'),
    path('reparations/<int:pk>/', views.ReparationVehiculeDetailView.as_view(), name='reparation_detail'),
    path('reparations/<int:pk>/modifier/', views.ReparationVehiculeUpdateView.as_view(), name='reparation_update'),
    path('reparations/<int:pk>/demarrer/', views.ReparationVehiculeDemarrerView.as_view(), name='reparation_demarrer'),
    path('reparations/<int:pk>/terminer/', views.ReparationVehiculeTerminerView.as_view(), name='reparation_terminer'),
    path('reparations/<int:pk>/supprimer/', views.ReparationVehiculeDeleteView.as_view(), name='reparation_delete'),

    # Crédits pièces garage (pièces à crédit, versements échelonnés)
    path('credits/', views.CreditGarageListView.as_view(), name='credit_garage_list'),
    path('reparations/<int:reparation_pk>/credits/ajouter/', views.CreditPieceGarageCreateView.as_view(), name='credit_create'),
    path('credits/<int:pk>/modifier/', views.CreditPieceGarageUpdateView.as_view(), name='credit_update'),
    path('credits/<int:pk>/supprimer/', views.CreditPieceGarageDeleteView.as_view(), name='credit_delete'),
    path('credits/<int:credit_pk>/versements/ajouter/', views.VersementCreditCreateView.as_view(), name='versement_create'),
    path('versements/<int:pk>/supprimer/', views.VersementCreditDeleteView.as_view(), name='versement_delete'),

    # Rapport analytique
    path('rapport/', views.RapportReparationsView.as_view(), name='rapport_reparations'),
    path('rentabilite/', views.RentabiliteVehiculeView.as_view(), name='rentabilite'),

    # Types de réparation
    path('types-reparation/', views.TypeReparationListView.as_view(), name='type_reparation_list'),
    path('types-reparation/ajax/', views.type_reparation_list_ajax, name='type_reparation_list_ajax'),
    path('types-reparation/ajouter/', views.TypeReparationCreateView.as_view(), name='type_reparation_create'),
    path('types-reparation/<int:pk>/modifier/', views.TypeReparationUpdateView.as_view(), name='type_reparation_update'),
    path('types-reparation/<int:pk>/supprimer/', views.TypeReparationDeleteView.as_view(), name='type_reparation_delete'),

    # Réparations AJAX (pagination onglet fiche véhicule)
    path('<int:pk>/reparations-ajax/', views.reparations_vehicule_ajax, name='reparations_ajax'),
    path('<int:pk>/entretien-ajax/', views.entretien_historique_ajax, name='entretien_ajax'),

    # API AJAX
    path('api/types-reparation/', views.get_types_reparation, name='api_types_reparation'),
    path('api/vehicule/<int:pk>/km/', views.get_vehicule_km, name='api_vehicule_km'),
]
