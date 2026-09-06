from django.contrib import admin
from django.utils.html import format_html
from .models import TypeDepense, Depense


@admin.register(TypeDepense)
class TypeDepenseAdmin(admin.ModelAdmin):
    """Interface d'administration pour les types de dépenses."""

    list_display = ['nom', 'code', 'description_obligatoire', 'actif', 'ordre', 'compagnie', 'nb_depenses']
    list_filter = ['actif', 'description_obligatoire', 'compagnie']
    search_fields = ['nom', 'code']
    ordering = ['ordre', 'nom']

    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'nom', 'compagnie')
        }),
        ('Configuration', {
            'fields': ('description_obligatoire', 'actif', 'ordre')
        }),
    )

    def nb_depenses(self, obj):
        """Affiche le nombre de dépenses utilisant ce type."""
        count = obj.depenses.count()
        if count > 0:
            return format_html(
                '<span style="color: #27ae60; font-weight: bold;">{} dépense{}</span>',
                count,
                's' if count > 1 else ''
            )
        return format_html('<span style="color: #95a5a6;">0 dépense</span>')
    nb_depenses.short_description = "Nombre d'utilisations"

    def delete_model(self, request, obj):
        """Gère la suppression avec validation."""
        try:
            obj.delete()
        except Exception as e:
            self.message_user(request, str(e), level='ERROR')

    def delete_queryset(self, request, queryset):
        """Gère la suppression en masse avec validation."""
        for obj in queryset:
            try:
                obj.delete()
            except Exception as e:
                self.message_user(request, f"Erreur pour '{obj.nom}': {str(e)}", level='ERROR')


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    """Interface d'administration pour les dépenses."""

    list_display = ['voyage', 'type_depense', 'montant_format', 'description_courte', 'guichetier', 'date_creation']
    list_filter = ['type_depense', 'voyage__gare', 'date_creation']
    search_fields = ['description', 'voyage__ligne__nom']
    date_hierarchy = 'date_creation'
    ordering = ['-date_creation']

    fieldsets = (
        ('Voyage', {
            'fields': ('voyage',)
        }),
        ('Dépense', {
            'fields': ('type_depense', 'montant', 'description')
        }),
        ('Traçabilité', {
            'fields': ('guichetier',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['guichetier']

    def montant_format(self, obj):
        """Affiche le montant formaté."""
        return format_html(
            '<span style="font-weight: bold; color: #e74c3c;">{:,.0f} FCFA</span>',
            obj.montant
        )
    montant_format.short_description = "Montant"

    def description_courte(self, obj):
        """Affiche une description tronquée."""
        if obj.description:
            if len(obj.description) > 50:
                return obj.description[:50] + '...'
            return obj.description
        return format_html('<em style="color: #95a5a6;">Aucune description</em>')
    description_courte.short_description = "Description"

    def save_model(self, request, obj, form, change):
        """Enregistre le guichetier lors de la création."""
        if not change:  # Si c'est une nouvelle dépense
            obj.guichetier = request.user
        super().save_model(request, obj, form, change)
