from django.contrib import admin
from .models import Compagnie


@admin.register(Compagnie)
class CompagnieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'nom_pdg', 'telephone', 'email')
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'logo', 'nom_pdg')
        }),
        ('Contact', {
            'fields': ('adresse', 'telephone', 'email')
        }),
        ('Configuration', {
            'fields': ('utiliser_souche', 'message_bas_ticket'),
            'description': 'Paramètres d\'impression des billets'
        }),
    )

    def has_add_permission(self, request):
        """Empêche la création de plusieurs compagnies."""
        if Compagnie.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression de la compagnie."""
        return False
