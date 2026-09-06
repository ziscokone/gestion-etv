from django.urls import path
from . import views

app_name = 'voyages'

urlpatterns = [
    path('', views.VoyageListView.as_view(), name='voyage_list'),
    path('ajax/', views.voyage_list_ajax, name='voyage_list_ajax'),
    path('<uuid:public_id>/', views.VoyageDetailView.as_view(), name='voyage_detail'),
    path('<uuid:public_id>/bordereau/', views.VoyageBordereauView.as_view(), name='voyage_bordereau'),
    path('<uuid:public_id>/liste-passagers/', views.VoyageListePassagersView.as_view(), name='voyage_liste_passagers'),
    path('<uuid:public_id>/recap-destination/', views.VoyageRecapDestinationView.as_view(), name='voyage_recap_destination'),
    path('ajouter/', views.VoyageCreateView.as_view(), name='voyage_create'),
    path('<uuid:public_id>/modifier/', views.VoyageUpdateView.as_view(), name='voyage_update'),
    path('<uuid:public_id>/supprimer/', views.VoyageDeleteView.as_view(), name='voyage_delete'),
    # Routes AJAX pour la gestion des agents
    path('<uuid:pk>/agents/', views.get_voyage_agents, name='voyage_get_agents'),
    path('<uuid:pk>/agents/save/', views.save_voyage_agents, name='voyage_save_agents'),
    # Routes AJAX pour la gestion des dépenses
    path('<uuid:pk>/depenses/', views.get_voyage_depenses, name='voyage_get_depenses'),
    path('<uuid:pk>/depenses/add/', views.add_voyage_depenses, name='voyage_add_depenses'),
    path('depenses/<int:depense_id>/creer-reparation/', views.creer_reparation_depuis_depense, name='depense_creer_reparation'),
    # Routes AJAX pour la gestion de la recette bagages
    path('<uuid:pk>/bagages/', views.get_voyage_bagages, name='voyage_get_bagages'),
    path('<uuid:pk>/bagages/save/', views.save_voyage_bagages, name='voyage_save_bagages'),
    # Route AJAX pour terminer un voyage
    path('<uuid:pk>/terminer/', views.terminer_voyage, name='voyage_terminer'),
    # Impression des réassignations de sièges
    path('<uuid:pk>/reassignations/imprimer/', views.print_reassignations, name='voyage_print_reassignations'),
    # Routes AJAX pour la gestion du report de billets
    path('billets/<uuid:billet_id>/report/voyages/', views.get_voyages_report, name='get_voyages_report'),
    path('billets/<uuid:billet_id>/report/', views.reporter_billet, name='reporter_billet'),
    path('voyages/<uuid:voyage_id>/disposition/', views.get_disposition_voyage, name='get_disposition_voyage'),
    # Dashboard des reports
    path('dashboard/reports/', views.DashboardReportsView.as_view(), name='dashboard_reports'),
    # Gestion des remboursements
    path('billets/<uuid:billet_id>/remboursement/demander/', views.demander_remboursement, name='demander_remboursement'),
    path('remboursements/<int:demande_id>/traiter/', views.traiter_remboursement, name='traiter_remboursement'),
    path('remboursements/', views.ListeRemboursementsView.as_view(), name='liste_remboursements'),

    # Tickets gratuits
    path('<uuid:voyage_id>/ticket-gratuit/creer/', views.creer_ticket_gratuit, name='creer_ticket_gratuit'),
    path('ticket-gratuit/<int:demande_id>/traiter/', views.traiter_ticket_gratuit, name='traiter_ticket_gratuit'),
    path('rapports/tickets-gratuits/', views.RapportTicketsGratuitView.as_view(), name='rapport_tickets_gratuit'),
]
