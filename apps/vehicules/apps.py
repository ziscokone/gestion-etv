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
