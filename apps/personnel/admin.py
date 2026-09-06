from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Chauffeur, Convoyeur, TypeDocumentChauffeur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('username', 'nom_complet', 'role', 'gare', 'actif')
    list_filter = ('role', 'gare', 'actif')
    search_fields = ('username', 'nom_complet', 'telephone')
    ordering = ('nom_complet',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {
            'fields': ('nom_complet', 'telephone', 'email')
        }),
        ('Affectation', {
            'fields': ('role', 'gare')
        }),
        ('Permissions', {
            'fields': ('is_active', 'actif', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Dates importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'nom_complet', 'password1', 'password2', 'role', 'gare'),
        }),
    )


@admin.register(Chauffeur)
class ChauffeurAdmin(admin.ModelAdmin):
    list_display = ('nom_complet', 'telephone', 'numero_permis', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom_complet', 'telephone', 'numero_permis')
    ordering = ('nom_complet',)


@admin.register(Convoyeur)
class ConvoyeurAdmin(admin.ModelAdmin):
    list_display = ('nom_complet', 'telephone', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom_complet', 'telephone')
    ordering = ('nom_complet',)


@admin.register(TypeDocumentChauffeur)
class TypeDocumentChauffeurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom',)
    ordering = ('nom',)
