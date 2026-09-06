from django.contrib import admin
from .models import Billet, HistoriqueReport, DemandeTicketGratuit


@admin.register(HistoriqueReport)
class HistoriqueReportAdmin(admin.ModelAdmin):
    list_display = ('ancien_billet', 'ancien_voyage', 'nouveau_voyage', 'guichetier', 'date_report')
    list_filter = ('date_report',)
    search_fields = ('ancien_billet__numero', 'nouveau_billet__numero')
    ordering = ('-date_report',)
    readonly_fields = ('ancien_billet', 'nouveau_billet', 'ancien_voyage', 'nouveau_voyage',
                       'ancien_siege', 'nouveau_siege', 'guichetier', 'motif', 'date_report')


@admin.register(Billet)
class BilletAdmin(admin.ModelAdmin):
    list_display = (
        'numero', 'client_nom', 'numero_siege', 'voyage',
        'montant', 'statut', 'guichetier', 'date_creation'
    )
    list_filter = ('statut', 'voyage__gare', 'voyage__date_depart', 'guichetier')
    search_fields = ('numero', 'client_nom', 'client_telephone')
    ordering = ('-date_creation',)
    date_hierarchy = 'date_creation'

    fieldsets = (
        ('Informations du ticket', {
            'fields': ('numero', 'voyage', 'numero_siege')
        }),
        ('Client', {
            'fields': ('client_nom', 'client_telephone')
        }),
        ('Paiement', {
            'fields': ('montant', 'statut', 'date_paiement')
        }),
        ('Vente', {
            'fields': ('guichetier',)
        }),
    )

    readonly_fields = ('numero', 'date_paiement')

    def has_add_permission(self, request):
        """Les billets doivent être créés via l'interface guichet."""
        return False


@admin.register(DemandeTicketGratuit)
class DemandeTicketGratuitAdmin(admin.ModelAdmin):
    list_display = ('billet', 'statut', 'demande_par', 'traite_par', 'date_demande', 'date_traitement')
    list_filter = ('statut', 'date_demande')
    search_fields = ('billet__numero', 'billet__client_nom', 'motif')
    ordering = ('-date_demande',)
    readonly_fields = ('billet', 'demande_par', 'traite_par', 'date_demande', 'date_traitement')
