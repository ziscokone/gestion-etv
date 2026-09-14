from django.apps import AppConfig


class VehiculesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vehicules'
    verbose_name = 'Véhicules'

    def ready(self):
        from apps.voyages.models import Voyage
        from django.db.models.signals import pre_save, post_save
        from .signals import _capturer_ancien_statut_voyage, _mettre_a_jour_kilometrage
        pre_save.connect(_capturer_ancien_statut_voyage, sender=Voyage)
        post_save.connect(_mettre_a_jour_kilometrage, sender=Voyage)

        # Historique des crédits pièces garage : qui a créé/modifié quoi, et quand
        # (panneau affiché sur la page de modification du crédit). Liste blanche
        # volontaire : seuls les champs métier sont suivis (pas l'id, les FK qui
        # ne changent jamais, ou les dates déjà affichées via cree_par/date_creation).
        from auditlog.registry import auditlog
        from .models import CreditPieceGarage, VersementCredit
        auditlog.register(CreditPieceGarage, include_fields=[
            'fournisseur', 'libelle', 'montant_total', 'date_achat', 'statut', 'notes',
        ])
        auditlog.register(VersementCredit, include_fields=[
            'date_versement', 'montant', 'moyen_paiement',
            'numero_beneficiaire', 'reference_transaction', 'note',
        ])
