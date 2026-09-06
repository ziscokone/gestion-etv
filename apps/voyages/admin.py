from django.contrib import admin
from .models import Voyage


@admin.register(Voyage)
class VoyageAdmin(admin.ModelAdmin):
    list_display = (
        'date_depart', 'heure_depart', 'ligne', 'gare',
        'periode', 'vehicule', 'statut', 'cree_automatiquement'
    )
    list_filter = ('gare', 'ligne', 'statut', 'periode', 'date_depart', 'cree_automatiquement')
    search_fields = ('ligne__nom', 'gare__nom', 'vehicule__immatriculation')
    ordering = ('-date_depart', 'heure_depart')
    date_hierarchy = 'date_depart'

    fieldsets = (
        ('Trajet', {
            'fields': ('gare', 'ligne', 'destination')
        }),
        ('Horaires', {
            'fields': ('date_depart', 'heure_depart', 'periode')
        }),
        ('Véhicule et équipage', {
            'fields': ('vehicule', 'chauffeur', 'convoyeur')
        }),
        ('Statut', {
            'fields': ('statut', 'notes')
        }),
        ('Informations système', {
            'fields': ('programme', 'cree_automatiquement'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('programme', 'cree_automatiquement')
