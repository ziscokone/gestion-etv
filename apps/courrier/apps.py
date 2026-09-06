from django.apps import AppConfig


class CourrierConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courrier'
    verbose_name = 'Courrier'

    def ready(self):
        from apps.voyages.models import Voyage
        from django.db.models.signals import pre_save, post_save
        from .signals import _capturer_ancien_statut_voyage_colis, _faire_arriver_colis
        pre_save.connect(_capturer_ancien_statut_voyage_colis, sender=Voyage)
        post_save.connect(_faire_arriver_colis, sender=Voyage)
