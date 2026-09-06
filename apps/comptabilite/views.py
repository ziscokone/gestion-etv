from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from datetime import timedelta, datetime
from decimal import Decimal
from collections import defaultdict

from apps.billets.models import Billet
from apps.voyages.models import Voyage
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur, Chauffeur
from apps.comptabilite.models import TypeDepense, Depense
import json
from datetime import date


class PointJournalierView(LoginRequiredMixin, TemplateView):
    """Point journalier des ventes."""
    template_name = 'comptabilite/point_journalier.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        date_str = self.request.GET.get('date')

        if date_str:
            try:
                from datetime import datetime
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date = timezone.now().date()
        else:
            date = timezone.now().date()

        context['date_selectionnee'] = date

        # Construire le queryset billets de base
        billets_query = Billet.objects.filter(
            statut='paye',
            date_paiement__date=date
        )

        if not user.has_global_access:
            billets_query = billets_query.filter(voyage__gare=user.gare)

        # Stats globales billets
        stats = billets_query.aggregate(
            total_billets=Count('id'),
            total_montant=Sum('montant')
        )

        context['total_billets'] = stats['total_billets'] or 0
        context['total_montant'] = stats['total_montant'] or 0

        # --- Voyages du jour ---
        voyages_query = Voyage.objects.filter(
            date_depart=date,
            statut__in=['programme', 'en_cours', 'termine']
        ).select_related(
            'gare', 'ligne', 'vehicule'
        ).prefetch_related('billets', 'depenses')

        if not user.has_global_access:
            voyages_query = voyages_query.filter(gare=user.gare)

        voyages_query = voyages_query.order_by('gare__nom', 'heure_depart', 'numero_depart')

        # Construire la liste des voyages avec stats
        voyages_du_jour = []
        total_recette_bagages = Decimal('0')
        total_depenses = Decimal('0')
        total_benefice_net = Decimal('0')

        for voyage in voyages_query:
            nb_billets = voyage.billets.filter(statut='paye').count()
            recette_tickets = voyage.billets.filter(statut='paye').aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0')
            recette_bagages = voyage.recette_bagages or Decimal('0')
            depenses_voyage = sum(
                (d.montant for d in voyage.depenses.all()), Decimal('0')
            )
            benefice = (recette_tickets + recette_bagages) - depenses_voyage

            voyages_du_jour.append({
                'voyage': voyage,
                'nb_billets': nb_billets,
                'recette_tickets': recette_tickets,
                'recette_bagages': recette_bagages,
                'total_depenses': depenses_voyage,
                'benefice_net': benefice,
            })

            total_recette_bagages += recette_bagages
            total_depenses += depenses_voyage
            total_benefice_net += benefice

        context['voyages_du_jour'] = voyages_du_jour
        context['total_recette_bagages'] = total_recette_bagages
        context['total_depenses'] = total_depenses
        context['total_benefice_net'] = total_benefice_net

        # Stats par guichetier
        if user.has_global_access or user.is_chef_gare:
            guichetiers_stats = billets_query.values(
                'guichetier__nom_complet',
                'guichetier__id'
            ).annotate(
                nb_billets=Count('id'),
                montant=Sum('montant')
            ).order_by('-montant')

            context['guichetiers_stats'] = guichetiers_stats

        # Stats par gare (pour admin global)
        if user.has_global_access:
            gares_stats = billets_query.values(
                'voyage__gare__nom',
                'voyage__gare__id'
            ).annotate(
                nb_billets=Count('id'),
                montant=Sum('montant')
            ).order_by('-montant')

            context['gares_stats'] = gares_stats

        return context


class RapportPeriodeView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Rapport sur une période donnée (admin/chef de gare/guichetier)."""
    template_name = 'comptabilite/rapport_periode.html'

    def test_func(self):
        user = self.request.user
        return user.has_global_access or user.is_chef_gare or user.is_guichetier

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Dates de la période
        date_debut_str = self.request.GET.get('date_debut')
        date_fin_str = self.request.GET.get('date_fin')

        today = timezone.now().date()

        if date_debut_str:
            try:
                from datetime import datetime
                date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                date_debut = today - timedelta(days=7)
        else:
            date_debut = today - timedelta(days=7)

        if date_fin_str:
            try:
                from datetime import datetime
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
            except ValueError:
                date_fin = today
        else:
            date_fin = today

        context['date_debut'] = date_debut
        context['date_fin'] = date_fin

        # Queryset billets de base
        billets_query = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=date_debut,
            date_paiement__date__lte=date_fin
        )

        if not user.has_global_access:
            billets_query = billets_query.filter(voyage__gare=user.gare)

        # Stats globales billets
        stats = billets_query.aggregate(
            total_billets=Count('id'),
            total_montant=Sum('montant')
        )

        context['total_billets'] = stats['total_billets'] or 0
        context['total_montant'] = stats['total_montant'] or 0

        # --- Voyages de la période ---
        voyages_query = Voyage.objects.filter(
            date_depart__gte=date_debut,
            date_depart__lte=date_fin,
            statut__in=['programme', 'en_cours', 'termine']
        ).select_related(
            'gare', 'ligne', 'vehicule'
        ).prefetch_related('billets', 'depenses')

        if not user.has_global_access:
            voyages_query = voyages_query.filter(gare=user.gare)

        voyages_query = voyages_query.order_by('date_depart', 'gare__nom', 'heure_depart', 'numero_depart')

        # Construire la liste des voyages avec stats
        voyages_periode = []
        total_recette_bagages = Decimal('0')
        total_depenses = Decimal('0')
        total_benefice_net = Decimal('0')

        for voyage in voyages_query:
            nb_billets = voyage.billets.filter(statut='paye').count()
            recette_tickets = voyage.billets.filter(statut='paye').aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0')
            recette_bagages = voyage.recette_bagages or Decimal('0')
            depenses_voyage = sum(
                (d.montant for d in voyage.depenses.all()), Decimal('0')
            )
            benefice = (recette_tickets + recette_bagages) - depenses_voyage

            voyages_periode.append({
                'voyage': voyage,
                'nb_billets': nb_billets,
                'recette_tickets': recette_tickets,
                'recette_bagages': recette_bagages,
                'total_depenses': depenses_voyage,
                'benefice_net': benefice,
            })

            total_recette_bagages += recette_bagages
            total_depenses += depenses_voyage
            total_benefice_net += benefice

        # Pagination : 20 voyages par page, totaux conservés sur l'ensemble
        paginator = Paginator(voyages_periode, 20)
        page_number = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['voyages_periode_count'] = len(voyages_periode)
        context['total_recette_bagages'] = total_recette_bagages
        context['total_depenses'] = total_depenses
        context['total_benefice_net'] = total_benefice_net

        # Stats par guichetier
        if user.has_global_access or user.is_chef_gare:
            guichetiers_stats = billets_query.values(
                'guichetier__nom_complet',
                'guichetier__id'
            ).annotate(
                nb_billets=Count('id'),
                montant=Sum('montant')
            ).order_by('-montant')

            context['guichetiers_stats'] = guichetiers_stats

        # Stats par gare (pour admin global)
        if user.has_global_access:
            gares_stats = billets_query.values(
                'voyage__gare__nom',
                'voyage__gare__id'
            ).annotate(
                nb_billets=Count('id'),
                montant=Sum('montant')
            ).order_by('-montant')

            context['gares_stats'] = gares_stats

        return context


class StatistiquesView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Statistiques globales (PDG/Super Admin)."""
    template_name = 'comptabilite/statistiques.html'

    def test_func(self):
        return self.request.user.has_global_access

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        # Stats du jour
        billets_jour = Billet.objects.filter(
            statut='paye',
            date_paiement__date=today
        )
        context['jour_billets'] = billets_jour.count()
        context['jour_montant'] = billets_jour.aggregate(Sum('montant'))['montant__sum'] or 0

        # Stats de la semaine
        debut_semaine = today - timedelta(days=today.weekday())
        billets_semaine = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=debut_semaine,
            date_paiement__date__lte=today
        )
        context['semaine_billets'] = billets_semaine.count()
        context['semaine_montant'] = billets_semaine.aggregate(Sum('montant'))['montant__sum'] or 0

        # Stats du mois
        debut_mois = today.replace(day=1)
        billets_mois = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=debut_mois,
            date_paiement__date__lte=today
        )
        context['mois_billets'] = billets_mois.count()
        context['mois_montant'] = billets_mois.aggregate(Sum('montant'))['montant__sum'] or 0

        # Top 5 gares
        context['top_gares'] = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=debut_mois
        ).values(
            'voyage__gare__nom'
        ).annotate(
            total=Sum('montant')
        ).order_by('-total')[:5]

        # Top 5 lignes
        context['top_lignes'] = Billet.objects.filter(
            statut='paye',
            date_paiement__date__gte=debut_mois
        ).values(
            'voyage__ligne__nom'
        ).annotate(
            total=Sum('montant')
        ).order_by('-total')[:5]

        # Réservations en attente
        context['reservations_attente'] = Billet.objects.filter(
            statut='reserve',
            voyage__date_depart__gte=today
        ).count()

        # Voyages du jour
        context['voyages_jour'] = Voyage.objects.filter(date_depart=today).count()

        return context


class RapportParGareView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Rapport détaillé par gare avec dépenses et bénéfices."""
    template_name = 'comptabilite/rapport_par_gare.html'

    def test_func(self):
        """Accessible uniquement par PDG, Super Admin et Manager."""
        user = self.request.user
        return user.role in ['pdg', 'super_admin', 'manager']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Paramètres de filtrage
        gare_id = self.request.GET.get('gare')
        ligne_id = self.request.GET.get('ligne')
        date_debut_str = self.request.GET.get('date_debut')
        date_fin_str = self.request.GET.get('date_fin')

        today = timezone.now().date()

        # Parse des dates
        if date_debut_str:
            try:
                date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                date_debut = today
        else:
            date_debut = today

        if date_fin_str:
            try:
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
            except ValueError:
                date_fin = today
        else:
            date_fin = today

        # Validation: date_fin >= date_debut
        if date_fin < date_debut:
            date_fin = date_debut

        context['date_debut'] = date_debut
        context['date_fin'] = date_fin

        # Gares disponibles
        context['gares'] = Gare.objects.filter(active=True).order_by('nom')

        # Gare sélectionnée
        gare_selectionnee = None
        if gare_id and gare_id != 'toutes':
            try:
                gare_selectionnee = Gare.objects.get(id=gare_id, active=True)
            except Gare.DoesNotExist:
                pass
        context['gare_selectionnee'] = gare_selectionnee

        # Lignes disponibles (filtrées par gare si nécessaire)
        if gare_selectionnee:
            lignes_disponibles = Ligne.objects.filter(gare=gare_selectionnee, active=True).order_by('nom')
        else:
            lignes_disponibles = Ligne.objects.filter(active=True).order_by('nom')
        context['lignes'] = lignes_disponibles

        # Ligne sélectionnée
        ligne_selectionnee = None
        if ligne_id and ligne_id != 'toutes':
            try:
                ligne_selectionnee = Ligne.objects.get(id=ligne_id, active=True)
            except Ligne.DoesNotExist:
                pass
        context['ligne_selectionnee'] = ligne_selectionnee

        # Construction du queryset de base
        voyages_query = Voyage.objects.filter(
            date_depart__gte=date_debut,
            date_depart__lte=date_fin,
            statut__in=['programme', 'en_cours', 'termine']
        ).select_related('gare', 'ligne').prefetch_related('billets', 'depenses', 'depenses__type_depense')

        # Filtrage par gare
        if gare_selectionnee:
            voyages_query = voyages_query.filter(gare=gare_selectionnee)

        # Filtrage par ligne
        if ligne_selectionnee:
            voyages_query = voyages_query.filter(ligne=ligne_selectionnee)

        # Tri
        voyages_query = voyages_query.order_by('date_depart', 'gare__nom', 'ligne__nom', 'numero_depart')

        # Récupérer la compagnie (singleton)
        from apps.compagnie.models import Compagnie
        compagnie = Compagnie.get_instance()

        # Construire les données du rapport
        donnees_rapport = []
        types_depenses_presents = set()
        total_charge = Decimal('0')
        total_versement = Decimal('0')

        for voyage in voyages_query:
            # Recettes
            nb_passagers = voyage.billets.filter(statut='paye').count()
            recette_billets = voyage.billets.filter(statut='paye').aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0')
            recette_bagages = voyage.recette_bagages or Decimal('0')

            # Dépenses par type - Optimisé : on récupère toutes les dépenses du voyage en une fois
            depenses_par_type = {}
            total_depenses_voyage = Decimal('0')

            # Récupérer toutes les dépenses du voyage (déjà prefetchées)
            for depense in voyage.depenses.all():
                type_nom = depense.type_depense.nom

                # Initialiser le type s'il n'existe pas encore
                if type_nom not in depenses_par_type:
                    depenses_par_type[type_nom] = Decimal('0')

                # Ajouter le montant
                depenses_par_type[type_nom] += depense.montant
                total_depenses_voyage += depense.montant

                # Marquer ce type comme présent
                types_depenses_presents.add(type_nom)

            # Bénéfice net
            benefice_net = (recette_billets + recette_bagages) - total_depenses_voyage

            # Totaux
            total_charge += total_depenses_voyage
            total_versement += benefice_net

            # Construire la ligne de données
            ligne_data = {
                'voyage': voyage,
                'date': voyage.date_depart,
                'gare': voyage.gare.nom,
                'ligne': voyage.ligne.nom,
                'numero_depart': voyage.numero_depart,
                'nb_passagers': nb_passagers,
                'recette_billets': recette_billets,
                'recette_bagages': recette_bagages,
                'depenses': depenses_par_type,
                'total_depenses': total_depenses_voyage,
                'benefice_net': benefice_net,
            }

            donnees_rapport.append(ligne_data)

        context['donnees_rapport'] = donnees_rapport
        context['types_depenses_presents'] = sorted(list(types_depenses_presents))
        context['total_charge'] = total_charge
        context['total_versement'] = total_versement

        # Déterminer les colonnes à afficher
        colonnes = []
        if date_debut != date_fin:
            colonnes.append('Date')
        if not gare_selectionnee:
            colonnes.append('Gare')
        if not ligne_selectionnee:
            colonnes.append('Ligne')

        colonnes.extend(['Num Départ', 'Nb Pass.', 'Recette Billets', 'Recette Bagages'])
        colonnes.extend(sorted(list(types_depenses_presents)))
        colonnes.extend(['Total Dépenses', 'Recette Net'])

        context['colonnes'] = colonnes

        # Calculer les totaux par colonne
        totaux = {
            'nb_passagers': sum(d['nb_passagers'] for d in donnees_rapport),
            'recette_billets': sum(d['recette_billets'] for d in donnees_rapport),
            'recette_bagages': sum(d['recette_bagages'] for d in donnees_rapport),
            'total_depenses': sum(d['total_depenses'] for d in donnees_rapport),
            'benefice_net': sum(d['benefice_net'] for d in donnees_rapport),
        }

        # Totaux par type de dépense
        for type_dep_nom in types_depenses_presents:
            totaux[type_dep_nom] = sum(
                d['depenses'].get(type_dep_nom, Decimal('0'))
                for d in donnees_rapport
            )

        context['totaux'] = totaux

        return context

    def get(self, request, *args, **kwargs):
        """Gère l'export PDF."""
        format_export = request.GET.get('export')

        if format_export == 'pdf':
            # Récupérer les données
            context = self.get_context_data()

            # Préparer les filtres pour l'export
            filtres = {
                'gare_nom': context['gare_selectionnee'].nom if context['gare_selectionnee'] else 'Toutes les gares',
                'ligne_nom': context['ligne_selectionnee'].nom if context['ligne_selectionnee'] else 'Toutes les lignes',
                'date_debut': context['date_debut'],
                'date_fin': context['date_fin'],
                'total_charge': context['total_charge'],
                'total_versement': context['total_versement'],
                'types_depenses': context['types_depenses_presents'],
                'colonnes': context['colonnes'],
            }

            # Préparer les données pour l'export
            donnees_export = []
            for ligne_data in context['donnees_rapport']:
                row = {}
                for col_name in context['colonnes']:
                    if col_name == 'Date':
                        row[col_name] = ligne_data['date'].strftime('%d/%m/%Y')
                    elif col_name == 'Gare':
                        row[col_name] = ligne_data['gare']
                    elif col_name == 'Ligne':
                        row[col_name] = ligne_data['ligne']
                    elif col_name == 'Num Départ':
                        row[col_name] = ligne_data['numero_depart']
                    elif col_name == 'Nb Pass.':
                        row[col_name] = ligne_data['nb_passagers']
                    elif col_name == 'Recette Billets':
                        row[col_name] = ligne_data['recette_billets']
                    elif col_name == 'Recette Bagages':
                        row[col_name] = ligne_data['recette_bagages']
                    elif col_name == 'Total Dépenses':
                        row[col_name] = ligne_data['total_depenses']
                    elif col_name == 'Recette Net':
                        row[col_name] = ligne_data['benefice_net']
                    elif col_name in context['types_depenses_presents']:
                        row[col_name] = ligne_data['depenses'].get(col_name, Decimal('0'))
                    else:
                        row[col_name] = ''

                donnees_export.append(row)

            # Export PDF
            from apps.comptabilite.utils import export_rapport_gare_pdf
            return export_rapport_gare_pdf(donnees_export, filtres)

        # Affichage normal
        return super().get(request, *args, **kwargs)


class PerformanceChauffeurView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Rapport de performance des chauffeurs — comparaison par nombre de voyages."""
    template_name = 'comptabilite/performance_chauffeurs.html'

    def test_func(self):
        return self.request.user.role in ['pdg', 'super_admin', 'manager']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        date_debut = self.request.GET.get('date_debut') or date(today.year, 1, 1).strftime('%Y-%m-%d')
        date_fin   = self.request.GET.get('date_fin')   or today.strftime('%Y-%m-%d')
        context['date_debut'] = date_debut
        context['date_fin']   = date_fin

        # Chauffeurs actifs avec leur nombre de voyages sur la période
        chauffeurs = Chauffeur.objects.filter(actif=True).annotate(
            nb_voyages=Count(
                'voyages',
                filter=Q(
                    voyages__date_depart__gte=date_debut,
                    voyages__date_depart__lte=date_fin,
                )
            )
        ).order_by('-nb_voyages')

        context['chauffeurs'] = chauffeurs

        # KPIs globaux
        total_voyages = sum(c.nb_voyages for c in chauffeurs)
        nb_actifs     = chauffeurs.count()
        nb_avec_voyage = chauffeurs.filter(nb_voyages__gt=0).count()
        meilleur      = chauffeurs.first()

        context['total_voyages']    = total_voyages
        context['nb_chauffeurs']    = nb_actifs
        context['nb_avec_voyage']   = nb_avec_voyage
        context['meilleur']         = meilleur

        # JSON pour le graphique (uniquement ceux avec au moins 1 voyage)
        chauffeurs_actifs = [c for c in chauffeurs if c.nb_voyages > 0]
        context['chart_labels_json'] = json.dumps([c.nom_complet for c in chauffeurs_actifs])
        context['chart_data_json']   = json.dumps([c.nb_voyages for c in chauffeurs_actifs])

        # Pagination du tableau "Classement détaillé" (10/page) — le graphique
        # ci-dessus reste basé sur la liste complète, seul le tableau est paginé.
        paginator = Paginator(chauffeurs, 10)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))
        context['paginator'] = paginator
        context['page_obj'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['chauffeurs_page'] = page_obj

        # Hauteur du graphique : ~40px par chauffeur, avec un plancher pour
        # qu'une barre unique ne s'étire pas sur toute la hauteur. Le conteneur
        # parent (dans le template) est scrollable au-delà de 460px, donc pas
        # de plafond ici : le graphique grandit avec le nombre de chauffeurs.
        context['chart_height_px'] = max(nb_avec_voyage * 40, 140)

        return context


class BilanMensuelView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Bilan mensuel par gare : voyages, billets, recettes, dépenses, bénéfice net."""
    template_name = 'comptabilite/bilan_mensuel.html'

    def test_func(self):
        return self.request.user.role in ['pdg', 'super_admin', 'manager']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Liste de tous les mois ayant des voyages, du plus récent au plus ancien
        mois_disponibles = (
            Voyage.objects
            .dates('date_depart', 'month', order='DESC')
        )
        context['mois_disponibles'] = mois_disponibles

        # Mois sélectionné (paramètre ?mois=2026-03)
        mois_str = self.request.GET.get('mois')
        mois_selectionne = None

        if mois_str:
            try:
                mois_selectionne = datetime.strptime(mois_str, '%Y-%m').date()
            except ValueError:
                pass

        if not mois_selectionne:
            premier = list(mois_disponibles[:1])
            if premier:
                mois_selectionne = premier[0]

        if not mois_selectionne:
            return context

        annee = mois_selectionne.year
        mois  = mois_selectionne.month

        context['mois_selectionne'] = mois_selectionne

        # Gares ayant des voyages ce mois
        gares = Gare.objects.filter(
            voyages__date_depart__year=annee,
            voyages__date_depart__month=mois
        ).distinct().order_by('nom')

        # Filtre réparation (réutilisé pour chaque gare)
        filtre_reparation = (
            Q(type_depense__code='reparation') |
            Q(type_depense__nom__icontains='réparation') |
            Q(type_depense__nom__icontains='reparation')
        )

        bilan_gares = []
        totaux = {
            'nb_voyages': 0,
            'nb_billets_payes': 0,
            'nb_billets_reportes': 0,
            'recettes_billets': Decimal('0'),
            'recettes_bagages': Decimal('0'),
            'recettes_totales': Decimal('0'),
            'depenses_exploitation': Decimal('0'),
            'depenses_reparations': Decimal('0'),
            'total_depenses': Decimal('0'),
            'benefice_net': Decimal('0'),
        }

        for gare in gares:
            voyage_ids = list(
                Voyage.objects.filter(
                    gare=gare,
                    date_depart__year=annee,
                    date_depart__month=mois
                ).values_list('id', flat=True)
            )

            billets_gare   = Billet.objects.filter(voyage_id__in=voyage_ids)
            depenses_gare  = Depense.objects.filter(voyage_id__in=voyage_ids)
            voyages_gare_qs = Voyage.objects.filter(id__in=voyage_ids)

            nb_voyages          = len(voyage_ids)
            nb_billets_payes    = billets_gare.filter(statut='paye').count()
            nb_billets_reportes = billets_gare.filter(statut='reporte').count()

            recettes_billets = (
                billets_gare.filter(statut='paye')
                .aggregate(t=Sum('montant'))['t'] or Decimal('0')
            )
            recettes_bagages = (
                voyages_gare_qs
                .aggregate(t=Sum('recette_bagages'))['t'] or Decimal('0')
            )
            recettes_totales = recettes_billets + recettes_bagages

            depenses_reparations = (
                depenses_gare.filter(filtre_reparation)
                .aggregate(t=Sum('montant'))['t'] or Decimal('0')
            )
            depenses_exploitation = (
                depenses_gare.exclude(filtre_reparation)
                .aggregate(t=Sum('montant'))['t'] or Decimal('0')
            )
            total_depenses = depenses_exploitation + depenses_reparations
            benefice_net   = recettes_totales - total_depenses

            bilan_gares.append({
                'gare': gare,
                'nb_voyages': nb_voyages,
                'nb_billets_payes': nb_billets_payes,
                'nb_billets_reportes': nb_billets_reportes,
                'recettes_billets': recettes_billets,
                'recettes_bagages': recettes_bagages,
                'recettes_totales': recettes_totales,
                'depenses_exploitation': depenses_exploitation,
                'depenses_reparations': depenses_reparations,
                'total_depenses': total_depenses,
                'benefice_net': benefice_net,
            })

            totaux['nb_voyages']           += nb_voyages
            totaux['nb_billets_payes']     += nb_billets_payes
            totaux['nb_billets_reportes']  += nb_billets_reportes
            totaux['recettes_billets']     += recettes_billets
            totaux['recettes_bagages']     += recettes_bagages
            totaux['recettes_totales']     += recettes_totales
            totaux['depenses_exploitation']+= depenses_exploitation
            totaux['depenses_reparations'] += depenses_reparations
            totaux['total_depenses']       += total_depenses
            totaux['benefice_net']         += benefice_net

        context['bilan_gares'] = bilan_gares
        context['totaux']      = totaux
        return context
