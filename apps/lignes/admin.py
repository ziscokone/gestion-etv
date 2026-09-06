from django.contrib import admin
from .models import Ligne


@admin.register(Ligne)
class LigneAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville_depart', 'ville_arrivee', 'distance_km', 'active')
    list_filter = ('active', 'ville_depart', 'ville_arrivee')
    search_fields = ('nom', 'ville_depart', 'ville_arrivee')
    ordering = ('nom',)

    fieldsets = (
        ('Informations de la ligne', {
            'fields': ('nom', 'ville_depart', 'ville_arrivee', 'compagnie')
        }),
        ('Détails du trajet', {
            'fields': ('distance_km', 'duree_estimee')
        }),
        ('Statut', {
            'fields': ('active',)
        }),
    )
