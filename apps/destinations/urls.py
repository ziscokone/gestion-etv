from django.urls import path
from . import views

app_name = 'destinations'

urlpatterns = [
    path('', views.DestinationListView.as_view(), name='destination_list'),
    path('ajax/', views.destination_list_ajax, name='destination_list_ajax'),
    path('ajouter/', views.DestinationCreateView.as_view(), name='destination_create'),
    path('exporter/', views.DestinationExportView.as_view(), name='destination_export'),
    path('importer/', views.DestinationImportView.as_view(), name='destination_import'),
    path('<int:pk>/modifier/', views.DestinationUpdateView.as_view(), name='destination_update'),
    path('<int:pk>/supprimer/', views.DestinationDeleteView.as_view(), name='destination_delete'),
]
