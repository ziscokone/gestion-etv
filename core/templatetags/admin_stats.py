from django import template
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import timedelta

register = template.Library()


@register.simple_tag
def get_dashboard_stats():
    try:
        from apps.billets.models import Billet
        from apps.voyages.models import Voyage
        from apps.vehicules.models import Vehicule
        from apps.personnel.models import Utilisateur, Chauffeur, Convoyeur

        today = timezone.localdate()
        first_day_of_month = today.replace(day=1)
        in_30_days = today + timedelta(days=30)

        # ── Billets & Recettes ────────────────────────────────────────────
        billets_jour_qs = Billet.objects.filter(statut='paye', date_paiement__date=today)
        billets_mois_qs = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=first_day_of_month,
            date_paiement__date__lte=today,
        )
        recettes_jour = billets_jour_qs.aggregate(t=Sum('montant'))['t'] or 0
        recettes_mois = billets_mois_qs.aggregate(t=Sum('montant'))['t'] or 0

        # ── Voyages du jour ───────────────────────────────────────────────
        voyages_qs = Voyage.objects.filter(date_depart=today)
        voyages_programme = voyages_qs.filter(statut='programme').count()
        voyages_en_cours = voyages_qs.filter(statut='en_cours').count()
        voyages_termine = voyages_qs.filter(statut='termine').count()
        voyages_annule = voyages_qs.filter(statut='annule').count()
        voyages_total = voyages_qs.count()

        # ── Véhicules & Alertes ───────────────────────────────────────────
        vehicules_actifs_qs = Vehicule.objects.filter(actif=True)
        docs_expires_qs = vehicules_actifs_qs.filter(
            Q(date_expiration_assurance__lt=today) |
            Q(date_expiration_visite_technique__lt=today) |
            Q(date_expiration_carte_grise__lt=today) |
            Q(date_expiration_licence_transport__lt=today)
        ).distinct()
        docs_bientot_qs = vehicules_actifs_qs.exclude(
            pk__in=docs_expires_qs
        ).filter(
            Q(date_expiration_assurance__range=(today, in_30_days)) |
            Q(date_expiration_visite_technique__range=(today, in_30_days)) |
            Q(date_expiration_carte_grise__range=(today, in_30_days)) |
            Q(date_expiration_licence_transport__range=(today, in_30_days))
        ).distinct()

        # Détail des alertes par véhicule (pour l'affichage)
        alertes_detail = []
        for v in docs_expires_qs.select_related('modele')[:6]:
            problemes = []
            if v.date_expiration_assurance and v.date_expiration_assurance < today:
                problemes.append(f"Assurance expirée le {v.date_expiration_assurance.strftime('%d/%m/%Y')}")
            if v.date_expiration_visite_technique and v.date_expiration_visite_technique < today:
                problemes.append(f"Visite technique expirée le {v.date_expiration_visite_technique.strftime('%d/%m/%Y')}")
            if v.date_expiration_carte_grise and v.date_expiration_carte_grise < today:
                problemes.append(f"Carte grise expirée le {v.date_expiration_carte_grise.strftime('%d/%m/%Y')}")
            if v.date_expiration_licence_transport and v.date_expiration_licence_transport < today:
                problemes.append(f"Licence expirée le {v.date_expiration_licence_transport.strftime('%d/%m/%Y')}")
            alertes_detail.append({'vehicule': v.immatriculation, 'problemes': problemes, 'niveau': 'danger'})

        for v in docs_bientot_qs.select_related('modele')[:4]:
            problemes = []
            if v.date_expiration_assurance and today <= v.date_expiration_assurance <= in_30_days:
                problemes.append(f"Assurance expire le {v.date_expiration_assurance.strftime('%d/%m/%Y')}")
            if v.date_expiration_visite_technique and today <= v.date_expiration_visite_technique <= in_30_days:
                problemes.append(f"Visite technique expire le {v.date_expiration_visite_technique.strftime('%d/%m/%Y')}")
            if v.date_expiration_carte_grise and today <= v.date_expiration_carte_grise <= in_30_days:
                problemes.append(f"Carte grise expire le {v.date_expiration_carte_grise.strftime('%d/%m/%Y')}")
            if v.date_expiration_licence_transport and today <= v.date_expiration_licence_transport <= in_30_days:
                problemes.append(f"Licence expire le {v.date_expiration_licence_transport.strftime('%d/%m/%Y')}")
            alertes_detail.append({'vehicule': v.immatriculation, 'problemes': problemes, 'niveau': 'warning'})

        # ── Personnel ─────────────────────────────────────────────────────
        utilisateurs_actifs = Utilisateur.objects.filter(actif=True, is_active=True).count()
        chauffeurs_actifs = Chauffeur.objects.filter(actif=True).count()
        convoyeurs_actifs = Convoyeur.objects.filter(actif=True).count()

        return {
            'billets_jour': billets_jour_qs.count(),
            'recettes_jour': int(recettes_jour),
            'billets_mois': billets_mois_qs.count(),
            'recettes_mois': int(recettes_mois),
            'voyages_total': voyages_total,
            'voyages_programme': voyages_programme,
            'voyages_en_cours': voyages_en_cours,
            'voyages_termine': voyages_termine,
            'voyages_annule': voyages_annule,
            'vehicules_total': vehicules_actifs_qs.count(),
            'docs_expires': docs_expires_qs.count(),
            'docs_bientot': docs_bientot_qs.count(),
            'alertes_detail': alertes_detail,
            'utilisateurs_actifs': utilisateurs_actifs,
            'chauffeurs_actifs': chauffeurs_actifs,
            'convoyeurs_actifs': convoyeurs_actifs,
            'today': today,
        }
    except Exception:
        return {}
