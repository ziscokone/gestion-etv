from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'personnel'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='personnel/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Utilisateurs
    path('utilisateurs/', views.UtilisateurListView.as_view(), name='utilisateur_list'),
    path('utilisateurs/ajax/', views.utilisateur_list_ajax, name='utilisateur_list_ajax'),
    path('utilisateurs/ajouter/', views.UtilisateurCreateView.as_view(), name='utilisateur_create'),
    path('utilisateurs/<int:pk>/modifier/', views.UtilisateurUpdateView.as_view(), name='utilisateur_update'),
    path('utilisateurs/<int:pk>/supprimer/', views.UtilisateurDeleteView.as_view(), name='utilisateur_delete'),
    path('utilisateurs/<int:pk>/modules/', views.ModulesUtilisateurView.as_view(), name='utilisateur_modules'),

    # Chauffeurs
    path('chauffeurs/', views.ChauffeurListView.as_view(), name='chauffeur_list'),
    path('chauffeurs/ajax/', views.chauffeur_list_ajax, name='chauffeur_list_ajax'),
    path('chauffeurs/ajouter/', views.ChauffeurCreateView.as_view(), name='chauffeur_create'),
    path('chauffeurs/<int:pk>/', views.ChauffeurDetailView.as_view(), name='chauffeur_detail'),
    path('chauffeurs/<int:pk>/modifier/', views.ChauffeurUpdateView.as_view(), name='chauffeur_update'),
    path('chauffeurs/<int:pk>/supprimer/', views.ChauffeurDeleteView.as_view(), name='chauffeur_delete'),
    path('chauffeurs/<int:chauffeur_id>/documents/upload/', views.upload_document_chauffeur, name='upload_document_chauffeur'),
    path('documents/<int:doc_id>/telecharger/', views.telecharger_document_chauffeur, name='telecharger_document_chauffeur'),
    path('documents/<int:doc_id>/supprimer/', views.supprimer_document_chauffeur, name='supprimer_document_chauffeur'),

    # Types de document chauffeur
    path('types-document/', views.TypeDocumentChauffeurListView.as_view(), name='type_document_list'),
    path('types-document/ajax/', views.type_document_list_ajax, name='type_document_list_ajax'),
    path('types-document/ajouter/', views.TypeDocumentChauffeurCreateView.as_view(), name='type_document_create'),
    path('types-document/<int:pk>/modifier/', views.TypeDocumentChauffeurUpdateView.as_view(), name='type_document_update'),
    path('types-document/<int:pk>/supprimer/', views.TypeDocumentChauffeurDeleteView.as_view(), name='type_document_delete'),

    # Convoyeurs
    path('convoyeurs/', views.ConvoyeurListView.as_view(), name='convoyeur_list'),
    path('convoyeurs/ajax/', views.convoyeur_list_ajax, name='convoyeur_list_ajax'),
    path('convoyeurs/ajouter/', views.ConvoyeurCreateView.as_view(), name='convoyeur_create'),
    path('convoyeurs/<int:pk>/modifier/', views.ConvoyeurUpdateView.as_view(), name='convoyeur_update'),
    path('convoyeurs/<int:pk>/supprimer/', views.ConvoyeurDeleteView.as_view(), name='convoyeur_delete'),
]
