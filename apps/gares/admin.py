from django.contrib import admin
from .models import Gare, GareSyncToken


@admin.register(Gare)
class GareAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'ville', 'telephone', 'active')
    list_filter = ('active', 'ville')
    search_fields = ('nom', 'code', 'ville')
    ordering = ('nom',)

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'code', 'ville', 'compagnie')
        }),
        ('Contact', {
            'fields': ('adresse', 'telephone')
        }),
        ('Statut', {
            'fields': ('active',)
        }),
    )


@admin.register(GareSyncToken)
class GareSyncTokenAdmin(admin.ModelAdmin):
    """
    Le jeton en clair n'est jamais stocké ni affiché ici : il n'est visible qu'une
    seule fois, à sa génération via `python manage.py create_gare_token <code>`.
    Cet écran sert uniquement à consulter/révoquer un jeton existant.
    """
    list_display = ('gare', 'actif', 'date_creation', 'derniere_utilisation')
    list_filter = ('actif',)
    readonly_fields = ('gare', 'date_creation', 'derniere_utilisation')
    fields = ('gare', 'actif', 'date_creation', 'derniere_utilisation')

    def has_add_permission(self, request):
        return False
