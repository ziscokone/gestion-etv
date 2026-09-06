from django.urls import path
from . import views

app_name = 'programmes'

urlpatterns = [
    path('', views.ProgrammeDepartListView.as_view(), name='programme_list'),
    path('ajax/', views.programme_list_ajax, name='programme_list_ajax'),
    path('ajouter/', views.ProgrammeDepartCreateView.as_view(), name='programme_create'),
    path('<int:pk>/modifier/', views.ProgrammeDepartUpdateView.as_view(), name='programme_update'),
    path('<int:pk>/supprimer/', views.ProgrammeDepartDeleteView.as_view(), name='programme_delete'),
    path('<int:pk>/generer-voyages/', views.GenererVoyagesView.as_view(), name='generer_voyages'),
]
