from django.contrib import admin
from .models import ModeleVehicule, Vehicule, TypeReparation, ReparationVehicule, LigneIntervention


@admin.register(TypeReparation)
class TypeReparationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'is_vidange', 'intervalle_km_defaut', 'actif')
    list_filter = ('is_vidange', 'actif')
    search_fields = ('nom',)
    ordering = ('nom',)


@admin.register(ModeleVehicule)
class ModeleVehiculeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'marque', 'capacite')
    list_filter = ('marque',)
    search_fields = ('nom', 'marque')
    ordering = ('marque', 'nom')

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'marque', 'capacite', 'description')
        }),
        ('Configuration des sièges', {
            'fields': ('disposition_sieges',),
            'classes': ('collapse',),
            'description': 'Configuration JSON de la disposition des sièges'
        }),
    )


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ('immatriculation', 'modele', 'annee_mise_service', 'actif', 'type_carburant')
    list_filter = ('modele', 'actif', 'annee_mise_service', 'type_carburant', 'type_boite')
    search_fields = ('immatriculation', 'modele__nom', 'numero_chassis')
    ordering = ('immatriculation',)

    fieldsets = (
        ('Informations générales', {
            'fields': ('immatriculation', 'modele', 'compagnie', 'actif')
        }),
        ('Caractéristiques techniques', {
            'fields': ('numero_chassis', 'annee_fabrication', 'date_mise_circulation', 'type_carburant', 'type_boite')
        }),
        ('Documents & conformité légale', {
            'fields': ('compagnie_assurance', 'date_expiration_assurance', 'date_expiration_visite_technique',
                      'date_expiration_carte_grise', 'date_expiration_licence_transport')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


class LigneInterventionInline(admin.TabularInline):
    model = LigneIntervention
    extra = 1
    fields = ('type_reparation', 'description', 'montant', 'kilometrage', 'intervalle_km', 'huile_utilisee')


@admin.register(ReparationVehicule)
class ReparationVehiculeAdmin(admin.ModelAdmin):
    list_display = ('vehicule', 'date_reparation', 'garage_prestataire', 'statut', 'montant_total')
    list_filter = ('statut', 'date_reparation')
    search_fields = ('vehicule__immatriculation', 'garage_prestataire', 'notes')
    ordering = ('-date_reparation',)
    date_hierarchy = 'date_reparation'
    inlines = [LigneInterventionInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('vehicule', 'date_reparation', 'garage_prestataire', 'statut')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
