from django.urls import path

from . import views

app_name = 'clients'

urlpatterns = [
    path('', views.ClientListView.as_view(), name='client_list'),
    path('ajax/', views.client_list_ajax, name='client_list_ajax'),
    path('<uuid:public_id>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('api/rechercher/', views.rechercher_client, name='rechercher_client'),
    path('api/suggerer/', views.suggerer_clients, name='suggerer_clients'),
]
