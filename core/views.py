import math
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count

from core.mixins import AdminRequiredMixin
from django.views.generic import TemplateView


@login_required
def hub(request):
    from apps.personnel.models import Module
    user = request.user
    if user.is_superuser or user.role == 'super_admin':
        modules = Module.objects.filter(actif=True)
    else:
        modules = user.modules_autorises.filter(actif=True)
    return render(request, 'hub.html', {'modules': modules})


# ── Tableau de bord exécutif ────────────────────────────────────────────────
# Couleurs par gare (tendance / composition / donut) — palette catégorielle
# fixe pour que la même gare garde toujours la même teinte d'un rafraîchissement
# à l'autre (index stable sur une liste triée, pas une couleur aléatoire).
# Mêmes couleurs que le tableau de bord du module Voyages (kpi-blue/green/
# orange/indigo) — palette volontairement restreinte, pas de teintes en plus.
PALETTE = ['#1e3260', '#27ae60', '#E67E22', '#4338ca']
COULEUR_AUTRES = '#9ca3af'

# Géométrie du graphique de tendance (SVG, viewBox 0 0 720 200)
CHART_X0, CHART_X1 = 20, 700
CHART_Y_TOP, CHART_Y_BASE = 20, 170
JOURS_ABBR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']


def _calculer_dashboard_executif():
    """
    Chiffres clés temps réel pour le tableau de bord exécutif (PDG / Manager /
    Comptable). Fonction partagée entre le rendu initial de la page et le
    point de rafraîchissement AJAX, pour ne jamais faire diverger les deux.
    """
    from apps.voyages.models import Voyage
    from apps.billets.models import Billet, DemandeRemboursement, DemandeTicketGratuit
    from apps.comptabilite.models import Depense
    from apps.vehicules.models import Vehicule, CreditPieceGarage, ReparationVehicule
    from apps.personnel.models import Chauffeur, Utilisateur
    from apps.clients.models import Client
    from apps.gares.models import Gare
    from apps.compagnie.models import Compagnie

    today = timezone.localdate()
    hier = today - timedelta(days=1)

    voyages_today_qs = Voyage.objects.filter(date_depart=today)
    nb_voyages_today = voyages_today_qs.count()
    nb_gares_actives_today = voyages_today_qs.values('gare_id').distinct().count()

    billets_payes_today_qs = Billet.objects.filter(date_creation__date=today, statut='paye')
    nb_billets_today = billets_payes_today_qs.count()
    montant_billets_today = billets_payes_today_qs.aggregate(t=Sum('montant'))['t'] or Decimal('0')
    recette_bagages_today = voyages_today_qs.aggregate(t=Sum('recette_bagages'))['t'] or Decimal('0')
    recettes_today = montant_billets_today + recette_bagages_today

    montant_billets_hier = (
        Billet.objects.filter(date_creation__date=hier, statut='paye')
        .aggregate(t=Sum('montant'))['t'] or Decimal('0')
    )
    delta_recette_jour = (
        round(float((recettes_today - montant_billets_hier) / montant_billets_hier * 100), 1)
        if montant_billets_hier else None
    )

    depenses_today = (
        Depense.objects.filter(date_creation__date=today)
        .aggregate(t=Sum('montant'))['t'] or Decimal('0')
    )
    benefice_today = recettes_today - depenses_today

    debut_mois = today.replace(day=1)
    depenses_mois = (
        Depense.objects.filter(date_creation__date__gte=debut_mois, date_creation__date__lte=today)
        .aggregate(t=Sum('montant'))['t'] or Decimal('0')
    )
    mois_prec = debut_mois - timedelta(days=1)
    depenses_mois_dernier = (
        Depense.objects.filter(
            date_creation__year=mois_prec.year, date_creation__month=mois_prec.month
        ).aggregate(t=Sum('montant'))['t'] or Decimal('0')
    )
    delta_depense_mois = (
        round(float((depenses_mois - depenses_mois_dernier) / depenses_mois_dernier * 100), 1)
        if depenses_mois_dernier else None
    )

    # ── Tendance des recettes sur 7 jours (aire + ligne SVG) ───────────
    debut_periode = today - timedelta(days=6)
    debut_periode_precedente = debut_periode - timedelta(days=7)
    fin_periode_precedente = debut_periode - timedelta(days=1)

    totaux_par_jour = {}
    for ligne in Billet.objects.filter(
        date_creation__date__gte=debut_periode, date_creation__date__lte=today, statut='paye'
    ).values('date_creation__date').annotate(total=Sum('montant')):
        totaux_par_jour[ligne['date_creation__date']] = ligne['total']

    tendance = []
    for i in range(7):
        jour = debut_periode + timedelta(days=i)
        tendance.append({
            'jour': jour,
            'label': JOURS_ABBR[jour.weekday()],
            'montant': totaux_par_jour.get(jour, Decimal('0')),
            'est_aujourdhui': jour == today,
        })
    recettes_periode = sum(j['montant'] for j in tendance)

    valeur_max = max((float(j['montant']) for j in tendance), default=0) or 1
    plage = valeur_max * 1.15
    largeur_pas = (CHART_X1 - CHART_X0) / 6
    for i, j in enumerate(tendance):
        y_val = CHART_Y_BASE - (float(j['montant']) / plage) * (CHART_Y_BASE - CHART_Y_TOP)
        j['x'] = f"{CHART_X0 + i * largeur_pas:.1f}"
        j['y'] = f"{y_val:.1f}"
        j['y_label'] = f"{y_val - 17:.1f}"
    points_ligne = ' '.join(f"{j['x']},{j['y']}" for j in tendance)
    aire_chemin = (
        f"M{tendance[0]['x']},{CHART_Y_BASE} "
        + ' '.join(f"L{j['x']},{j['y']}" for j in tendance)
        + f" L{tendance[-1]['x']},{CHART_Y_BASE} Z"
    )

    recettes_periode_precedente = (
        Billet.objects.filter(
            date_creation__date__gte=debut_periode_precedente,
            date_creation__date__lte=fin_periode_precedente,
            statut='paye',
        ).aggregate(t=Sum('montant'))['t'] or Decimal('0')
    )
    evolution_recettes_pct = (
        round(float((recettes_periode - recettes_periode_precedente) / recettes_periode_precedente * 100), 1)
        if recettes_periode_precedente else None
    )

    nb_voyages_annules_periode = Voyage.objects.filter(
        date_depart__gte=debut_periode, date_depart__lte=today, statut='annule'
    ).count()

    # ── Composition des recettes du jour, par gare ─────────────────────
    gares_ordonnees = list(Gare.objects.all().order_by('nom'))
    composition_jour = []
    for i, gare in enumerate(gares_ordonnees):
        montant = billets_payes_today_qs.filter(voyage__gare=gare).aggregate(t=Sum('montant'))['t'] or Decimal('0')
        if montant:
            composition_jour.append({
                'libelle': gare.nom, 'montant': montant,
                'couleur': PALETTE[i % len(PALETTE)],
            })
    for part in composition_jour:
        part['pourcentage'] = round(float(part['montant']) * 100 / float(recettes_today), 1) if recettes_today else 0

    # ── Flotte ──────────────────────────────────────────────────────
    nb_vehicules_actifs = Vehicule.objects.filter(actif=True).count()
    nb_vehicules_en_reparation = Vehicule.objects.filter(
        actif=True, reparations__statut__in=['en_attente', 'en_cours']
    ).distinct().count()
    nb_vehicules_disponibles = nb_vehicules_actifs - nb_vehicules_en_reparation
    taux_disponibilite_flotte = (
        round(nb_vehicules_disponibles / nb_vehicules_actifs * 100, 1) if nb_vehicules_actifs else None
    )
    pct_dispo = round(nb_vehicules_disponibles * 100 / nb_vehicules_actifs, 1) if nb_vehicules_actifs else 0
    pct_reparation = round(nb_vehicules_en_reparation * 100 / nb_vehicules_actifs, 1) if nb_vehicules_actifs else 0

    encours_credit_garage = sum(
        (c.reste_a_payer for c in CreditPieceGarage.objects.filter(statut='en_cours')),
        Decimal('0'),
    )

    # ── Personnel ───────────────────────────────────────────────────
    nb_chauffeurs_actifs = Chauffeur.objects.filter(actif=True).count()
    nb_guichetiers_actifs = Utilisateur.objects.filter(role='guichetier', actif=True).count()
    gares_avec_chef_ids = Utilisateur.objects.filter(
        role='chef_gare', actif=True, gare__isnull=False
    ).values_list('gare_id', flat=True)
    nb_gares_sans_chef = Gare.objects.exclude(id__in=gares_avec_chef_ids).count()

    # ── À traiter (listes réelles, pas seulement des compteurs) ────────
    remboursements_qs = (
        DemandeRemboursement.objects.select_related('billet__client', 'billet__voyage__gare')
        .filter(statut='en_attente').order_by('-date_demande')
    )
    nb_remboursements_attente = remboursements_qs.count()

    gratuits_qs = (
        DemandeTicketGratuit.objects.select_related('billet__client', 'billet__voyage__gare')
        .filter(statut='en_attente').order_by('-date_demande')
    )
    nb_gratuits_attente = gratuits_qs.count()

    compagnie_obj = Compagnie.get_instance()
    documents_actifs = compagnie_obj.get_documents_alertes_actifs() if compagnie_obj else []
    docs_a_traiter = []
    if documents_actifs:
        for v in Vehicule.objects.filter(actif=True):
            for doc in documents_actifs:
                date_exp = getattr(v, doc['champ_date'])
                if date_exp:
                    delta = (date_exp - today).days
                    if delta <= doc['seuil_alerte']:
                        docs_a_traiter.append({
                            'vehicule': v.display_immat, 'label': doc['label'],
                            'jours': delta, 'expire': delta < 0,
                        })
    docs_a_traiter.sort(key=lambda d: d['jours'])
    nb_docs_expires = sum(1 for d in docs_a_traiter if d['expire'])
    nb_docs_bientot = len(docs_a_traiter) - nb_docs_expires

    # ── Activité récente (fil combiné) ─────────────────────────────────
    activites = []
    for b in billets_payes_today_qs.select_related('client', 'voyage__gare').order_by('-date_creation')[:6]:
        activites.append({
            'date': b.date_creation, 'couleur': '#27ae60',
            'texte': f"{b.client_nom} — billet payé ({b.voyage.gare.nom if b.voyage.gare else '—'})",
            'montant': b.montant,
        })
    for d in Depense.objects.select_related('type_depense', 'voyage__gare').filter(date_creation__date=today).order_by('-date_creation')[:6]:
        activites.append({
            'date': d.date_creation, 'couleur': '#E67E22',
            'texte': f"Dépense — {d.type_depense.nom if d.type_depense else 'Dépense'}",
            'montant': d.montant,
        })
    for r in ReparationVehicule.objects.select_related('vehicule').filter(date_creation__date=today).order_by('-date_creation')[:4]:
        activites.append({
            'date': r.date_creation, 'couleur': '#4338ca',
            'texte': f"Entrée au garage — {r.vehicule.display_immat}",
        })
    for c in Client.objects.filter(date_creation__date=today).order_by('-date_creation')[:4]:
        activites.append({
            'date': c.date_creation, 'couleur': '#1e3260',
            'texte': f"Nouveau client — {c.nom_complet}",
        })
    activites.sort(key=lambda a: a['date'], reverse=True)
    activites = activites[:8]

    # ── Top gares — 7 derniers jours (classement + donut) ──────────────
    top_gares_qs = list(
        Voyage.objects.filter(date_depart__gte=debut_periode, date_depart__lte=today)
        .values('gare__nom').annotate(nb=Count('id')).order_by('-nb')
    )
    total_departs_periode = sum(g['nb'] for g in top_gares_qs) or 1
    for i, g in enumerate(top_gares_qs):
        g['couleur'] = PALETTE[i % len(PALETTE)]
        g['initiales'] = ''.join(w[0] for w in g['gare__nom'].split()[:2]).upper()
        g['pourcentage'] = round(g['nb'] * 100 / total_departs_periode, 1)

    rayon = 54
    circonference = 2 * math.pi * rayon
    cumul_len = 0.0
    donut_parts = []
    for g in top_gares_qs[:6]:
        longueur = circonference * g['nb'] / total_departs_periode
        donut_parts.append({
            'nom': g['gare__nom'], 'nb': g['nb'], 'couleur': g['couleur'], 'pourcentage': g['pourcentage'],
            'dash_len': f"{max(longueur - 2, 0):.2f}",
            'dash_offset': f"{-cumul_len:.2f}",
        })
        cumul_len += longueur

    # ── Clients ─────────────────────────────────────────────────────
    nb_nouveaux_clients_mois = Client.objects.filter(date_creation__date__gte=debut_mois).count()

    nb_clients_proches_fidelite = 0
    if compagnie_obj and compagnie_obj.fidelite_active and compagnie_obj.fidelite_seuil_voyages:
        seuil = compagnie_obj.fidelite_seuil_voyages
        qs = Billet.objects.filter(statut='paye', client__categorie='particulier')
        if compagnie_obj.fidelite_active_depuis:
            qs = qs.filter(date_paiement__gte=compagnie_obj.fidelite_active_depuis)
        nb_clients_proches_fidelite = (
            qs.values('client_id').annotate(nb=Count('id')).filter(nb=seuil - 1).count()
        ) if seuil > 1 else 0

    return {
        'heure_calcul': timezone.localtime(),
        'today': today,
        'hero': {
            'nb_voyages': nb_voyages_today,
            'nb_billets': nb_billets_today,
            'nb_gares_actives': nb_gares_actives_today,
            'recettes': recettes_today,
            'depenses': depenses_today,
            'benefice': benefice_today,
        },
        'kpi': {
            'recettes_jour': recettes_today,
            'delta_recette_jour': delta_recette_jour,
            'nb_billets_jour': nb_billets_today,
            'nb_voyages_jour': nb_voyages_today,
            'benefice_jour': benefice_today,
            'depenses_mois': depenses_mois,
            'delta_depense_mois': delta_depense_mois,
            'nb_vehicules_reparation': nb_vehicules_en_reparation,
            'taux_disponibilite': taux_disponibilite_flotte,
            'nb_alertes_docs': len(docs_a_traiter),
        },
        'tendance': tendance,
        'recettes_periode': recettes_periode,
        'points_ligne': points_ligne,
        'aire_chemin': aire_chemin,
        'chart_y_base': CHART_Y_BASE,
        'dernier_point': tendance[-1],
        'evolution_recettes_pct': evolution_recettes_pct,
        'nb_voyages_annules_periode': nb_voyages_annules_periode,
        'composition_jour': composition_jour,
        'flotte': {
            'nb_actifs': nb_vehicules_actifs,
            'nb_disponibles': nb_vehicules_disponibles,
            'nb_en_reparation': nb_vehicules_en_reparation,
            'pct_dispo': pct_dispo,
            'pct_reparation': pct_reparation,
            'encours_credit_garage': encours_credit_garage,
        },
        'personnel': {
            'nb_chauffeurs': nb_chauffeurs_actifs,
            'nb_guichetiers': nb_guichetiers_actifs,
            'nb_gares_sans_chef': nb_gares_sans_chef,
        },
        'a_traiter': {
            'remboursements': list(remboursements_qs[:5]),
            'nb_remboursements': nb_remboursements_attente,
            'gratuits': list(gratuits_qs[:5]),
            'nb_gratuits': nb_gratuits_attente,
            'docs': docs_a_traiter[:5],
            'nb_docs_expires': nb_docs_expires,
            'nb_docs_bientot': nb_docs_bientot,
        },
        'activites': activites,
        'top_gares': top_gares_qs[:6],
        'donut': {'parts': donut_parts, 'circonference': f"{circonference:.2f}", 'rayon': rayon},
        'clients': {
            'nb_nouveaux_mois': nb_nouveaux_clients_mois,
            'nb_proches_fidelite': nb_clients_proches_fidelite,
        },
    }


class DashboardExecutifView(AdminRequiredMixin, TemplateView):
    """Tableau de bord exécutif temps réel — PDG / Super Admin / Manager / Comptable."""
    template_name = 'dashboard_executif.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['d'] = _calculer_dashboard_executif()
        return context


def dashboard_executif_data(request):
    """Point de rafraîchissement AJAX (JSON) — uniquement les compteurs qui
    changent vite ; les graphiques (tendance, donut) se rafraîchissent au
    prochain chargement complet de la page pour rester simples."""
    if not request.user.is_authenticated or not request.user.has_global_access:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    d = _calculer_dashboard_executif()

    def dec(v):
        return str(v) if isinstance(v, Decimal) else v

    return JsonResponse({
        'success': True,
        'heure_calcul': d['heure_calcul'].strftime('%H:%M:%S'),
        'hero': {k: dec(v) for k, v in d['hero'].items()},
        'kpi': {k: dec(v) for k, v in d['kpi'].items()},
        'flotte': {k: dec(v) for k, v in d['flotte'].items()},
        'personnel': d['personnel'],
        'a_traiter': {
            'nb_remboursements': d['a_traiter']['nb_remboursements'],
            'nb_gratuits': d['a_traiter']['nb_gratuits'],
            'nb_docs_expires': d['a_traiter']['nb_docs_expires'],
            'nb_docs_bientot': d['a_traiter']['nb_docs_bientot'],
        },
        'clients': d['clients'],
    })
