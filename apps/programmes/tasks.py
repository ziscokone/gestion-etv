from django.utils import timezone


def creer_voyages_automatiques():
    """
    Crée automatiquement les voyages sur les 7 prochains jours
    à partir des programmes actifs.
    """
    from apps.programmes.models import ProgrammeDepart

    total_crees = ProgrammeDepart.creer_tous_voyages(jours_avance=7)
    return f"{total_crees} voyage(s) créé(s) le {timezone.now().strftime('%d/%m/%Y %H:%M')}"


def nettoyer_voyages_passes():
    """
    Marque les voyages passés comme terminés.
    """
    from apps.voyages.models import Voyage

    now = timezone.now()
    today = now.date()

    count = Voyage.objects.filter(
        statut='programme',
        date_depart__lt=today
    ).update(statut='termine')

    return f"{count} voyage(s) marqué(s) comme terminé(s)"
