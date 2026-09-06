from django.urls import path
from . import views

app_name = 'gares'

urlpatterns = [
    path('', views.GareListView.as_view(), name='gare_list'),
    path('ajouter/', views.GareCreateView.as_view(), name='gare_create'),
    path('<int:pk>/modifier/', views.GareUpdateView.as_view(), name='gare_update'),
    path('<int:pk>/supprimer/', views.GareDeleteView.as_view(), name='gare_delete'),
    path('imprimante/', views.ImprimanteConfigView.as_view(), name='imprimante_config'),
]
