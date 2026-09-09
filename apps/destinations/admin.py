from django.contrib import admin
from .forms import DestinationForm
from .models import Destination


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    form = DestinationForm
    list_display = ('gare', 'ville_arrivee', 'ligne', 'montant', 'active')
    list_filter = ('gare', 'ligne', 'active')
    search_fields = ('gare__nom', 'ville_arrivee', 'ligne__nom')
    ordering = ('gare', 'ville_arrivee')

    fieldsets = (
        ('Trajet', {
            'fields': ('gare', 'ligne', 'ville_arrivee')
        }),
        ('Tarification', {
            'fields': ('montant',)
        }),
        ('Statut', {
            'fields': ('active',)
        }),
    )
