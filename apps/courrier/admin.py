from django.contrib import admin

from .models import Colis, HistoriqueStatutColis, TypeColis


@admin.register(TypeColis)
class TypeColisAdmin(admin.ModelAdmin):
    list_display = ('nom', 'tarif_indicatif', 'ordre', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom',)
    ordering = ('ordre', 'nom')


class HistoriqueStatutColisInline(admin.TabularInline):
    model = HistoriqueStatutColis
    extra = 0
    fields = ('ancien_statut', 'nouveau_statut', 'agent', 'gare', 'date')
    readonly_fields = ('date',)


@admin.register(Colis)
class ColisAdmin(admin.ModelAdmin):
    list_display = (
        'code_colis', 'gare_origine', 'gare_destination', 'statut',
        'expediteur_nom', 'destinataire_nom', 'montant', 'guichetier_enregistrement', 'date_creation',
    )
    list_filter = ('statut', 'gare_origine', 'gare_destination', 'type_colis')
    search_fields = ('code_colis', 'expediteur_nom', 'expediteur_telephone', 'destinataire_nom', 'destinataire_telephone')
    ordering = ('-date_creation',)
    date_hierarchy = 'date_creation'
    inlines = [HistoriqueStatutColisInline]
    readonly_fields = ('public_id', 'code_colis', 'code_retrait')


@admin.register(HistoriqueStatutColis)
class HistoriqueStatutColisAdmin(admin.ModelAdmin):
    list_display = ('colis', 'ancien_statut', 'nouveau_statut', 'agent', 'gare', 'date')
    list_filter = ('nouveau_statut',)
    search_fields = ('colis__code_colis',)
    ordering = ('-date',)
