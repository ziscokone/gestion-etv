from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver


def _capturer_ancien_statut_voyage(sender, instance, **kwargs):
    """Capture le statut actuel avant sauvegarde pour détecter le passage à 'terminé'."""
    if instance.pk:
        try:
            instance._ancien_statut = sender.objects.get(pk=instance.pk).statut
        except sender.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


def _mettre_a_jour_kilometrage(sender, instance, created, **kwargs):
    """
    Quand un voyage passe à 'terminé', ajoute la distance de la ligne
    au compteur kilométrique du véhicule.
    """
    if created:
        return

    ancien_statut = getattr(instance, '_ancien_statut', None)
    if instance.statut != 'termine' or ancien_statut == 'termine':
        return

    vehicule = instance.vehicule
    distance = getattr(instance.ligne, 'distance_km', None) if instance.ligne else None

    if vehicule and distance:
        vehicule.kilometrage_actuel = (vehicule.kilometrage_actuel or 0) + distance
        vehicule.save(update_fields=['kilometrage_actuel'])
