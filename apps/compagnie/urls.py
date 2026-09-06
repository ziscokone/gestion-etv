from django.urls import path
from . import views

app_name = 'compagnie'

urlpatterns = [
    path('parametres/', views.CompagnieConfigView.as_view(), name='parametres'),
]
