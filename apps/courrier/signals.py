def _capturer_ancien_statut_voyage_colis(sender, instance, **kwargs):
    """
    Capture le statut actuel avant sauvegarde pour détecter le passage à
    'termine'. Attribut nommé distinctement de celui posé par
    apps.vehicules.signals (_ancien_statut) pour ne pas s'écraser mutuellement
    — les deux modules écoutent indépendamment le même signal sur Voyage.
    """
    if instance.pk:
        try:
            instance._ancien_statut_colis = sender.objects.get(pk=instance.pk).statut
        except sender.DoesNotExist:
            instance._ancien_statut_colis = None
    else:
        instance._ancien_statut_colis = None


def _faire_arriver_colis(sender, instance, created, **kwargs):
    """
    Quand un voyage passe à 'termine', tous les colis 'en_transit' rattachés
    à ce voyage passent automatiquement à 'arrive' (avec calcul de la date
    limite de retrait). C'est le pendant courrier de
    apps.vehicules.signals._mettre_a_jour_kilometrage.
    """
    if created:
        return

    ancien_statut = getattr(instance, '_ancien_statut_colis', None)
    if instance.statut != 'termine' or ancien_statut == 'termine':
        return

    for colis in instance.colis.filter(statut='en_transit'):
        colis.marquer_arrive()
