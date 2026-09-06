from django.urls import path
from . import views

app_name = 'lignes'

urlpatterns = [
    path('', views.LigneListView.as_view(), name='ligne_list'),
    path('ajouter/', views.LigneCreateView.as_view(), name='ligne_create'),
    path('<int:pk>/modifier/', views.LigneUpdateView.as_view(), name='ligne_update'),
    path('<int:pk>/supprimer/', views.LigneDeleteView.as_view(), name='ligne_delete'),
]
