from django.contrib import admin

from .models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('gare', 'direction', 'statut', 'nb_enregistrements', 'date_creation')
    list_filter = ('direction', 'statut', 'gare')
    readonly_fields = ('gare', 'direction', 'statut', 'nb_enregistrements', 'detail', 'date_creation')
    ordering = ('-date_creation',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
