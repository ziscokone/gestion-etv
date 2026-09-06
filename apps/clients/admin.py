from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom_complet', 'telephone', 'date_creation']
    search_fields = ['nom_complet', 'telephone']
    readonly_fields = ['date_creation', 'date_modification']
