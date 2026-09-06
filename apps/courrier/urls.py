from django.urls import path

from . import views

app_name = 'courrier'

urlpatterns = [
    path('', views.CourrierDashboardView.as_view(), name='dashboard'),
    path('liste/', views.ColisListView.as_view(), name='colis_list'),
    path('ajax/', views.colis_list_ajax, name='colis_list_ajax'),
    path('enregistrer/', views.ColisCreateView.as_view(), name='colis_create'),
    path('retrait/', views.RetraitColisView.as_view(), name='retrait'),
    path('retrait/ajax/', views.retrait_recherche_ajax, name='retrait_ajax'),
    path('retrait/historique/', views.RetraitHistoriqueListView.as_view(), name='retrait_historique'),

    path('chargement/', views.ChargementListeVoyagesView.as_view(), name='chargement_liste'),
    path('chargement/<uuid:public_id>/', views.ChargementVoyageView.as_view(), name='chargement_voyage'),
    path('chargement/<uuid:public_id>/bordereau.pdf', views.bordereau_pdf, name='bordereau_pdf'),

    path('reception/', views.ReceptionColisView.as_view(), name='reception_liste'),

    path('types/', views.TypeColisListView.as_view(), name='type_colis_list'),
    path('types/ajouter/', views.TypeColisCreateView.as_view(), name='type_colis_create'),
    path('types/<int:pk>/modifier/', views.TypeColisUpdateView.as_view(), name='type_colis_update'),
    path('types/<int:pk>/supprimer/', views.TypeColisDeleteView.as_view(), name='type_colis_delete'),

    path('<uuid:public_id>/', views.ColisDetailView.as_view(), name='colis_detail'),
    path('<uuid:public_id>/annuler/', views.ColisAnnulerView.as_view(), name='colis_annuler'),
]
