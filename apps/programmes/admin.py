from django.contrib import admin
from .models import ProgrammeDepart


@admin.register(ProgrammeDepart)
class ProgrammeDepartAdmin(admin.ModelAdmin):
    list_display = ('gare', 'ligne', 'heure_depart', 'periode', 'vehicule_defaut', 'actif')
    list_filter = ('gare', 'ligne', 'periode', 'actif')
    search_fields = ('gare__nom', 'ligne__nom')
    ordering = ('gare', 'heure_depart')

    fieldsets = (
        ('Configuration du trajet', {
            'fields': ('gare', 'ligne', 'destination')
        }),
        ('Horaires', {
            'fields': ('periode', 'heure_depart')
        }),
        ('Véhicule', {
            'fields': ('vehicule_defaut',)
        }),
        ('Planification', {
            'fields': ('jours_actifs',),
            'description': 'Sélectionnez les jours de la semaine (lun, mar, mer, jeu, ven, sam, dim)'
        }),
        ('Statut', {
            'fields': ('actif',)
        }),
    )
