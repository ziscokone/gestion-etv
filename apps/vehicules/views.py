from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from core.mixins import AdminRequiredMixin, GestionRequiredMixin, SuperAdminRequiredMixin
from core.utils import render_paginated_partial

logger = logging.getLogger(__name__)
from .models import ModeleVehicule, Vehicule, ReparationVehicule, LigneIntervention, TypeReparation
from .forms import (ModeleVehiculeForm, VehiculeForm, ReparationVehiculeForm,
                    LigneInterventionForm, LigneInterventionFormSet, TypeReparationForm,
                    get_vidange_type_ids, get_km_type_ids, get_suivi_km_type_ids)
from apps.compagnie.models import Compagnie


# Vues pour les modèles de véhicules
def _modeles_filtres(search):
    queryset = ModeleVehicule.objects.annotate(nb_vehicules=Count('vehicules'))
    if search:
        queryset = queryset.filter(
            Q(nom__icontains=search) |
            Q(marque__icontains=search)
        )
    return queryset.order_by('marque', 'nom')


class ModeleVehiculeListView(LoginRequiredMixin, ListView):
    """Liste des modèles de véhicules."""
    model = ModeleVehicule
    template_name = 'vehicules/modele_list.html'
    context_object_name = 'modeles'

    def get_queryset(self):
        return _modeles_filtres(self.request.GET.get('q'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['nb_total'] = ModeleVehicule.objects.count()
        context['nb_marques'] = ModeleVehicule.objects.values('marque').distinct().count()
        return context


@require_http_methods(["GET"])
@login_required
def modele_list_ajax(request):
    """Filtrage en direct des modèles de véhicules (recherche automatique)."""
    queryset = _modeles_filtres(request.GET.get('q'))
    return render(request, 'vehicules/partials/modele_table.html', {
        'modeles': queryset,
        'search_query': request.GET.get('q', ''),
    })


class ModeleVehiculeCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouveau modèle de véhicule."""
    model = ModeleVehicule
    form_class = ModeleVehiculeForm
    template_name = 'vehicules/modele_form.html'
    success_url = reverse_lazy('vehicules:modele_list')

    def form_valid(self, form):
        messages.success(self.request, 'Modèle de véhicule créé avec succès.')
        return super().form_valid(form)


class ModeleVehiculeUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un modèle de véhicule."""
    model = ModeleVehicule
    form_class = ModeleVehiculeForm
    template_name = 'vehicules/modele_form.html'
    success_url = reverse_lazy('vehicules:modele_list')

    def form_valid(self, form):
        messages.success(self.request, 'Modèle de véhicule modifié avec succès.')
        return super().form_valid(form)


class ModeleVehiculeDeleteView(AdminRequiredMixin, DeleteView):
    """Supprimer un modèle de véhicule."""
    model = ModeleVehicule
    template_name = 'vehicules/modele_confirm_delete.html'
    success_url = reverse_lazy('vehicules:modele_list')

    def form_valid(self, form):
        messages.success(self.request, 'Modèle de véhicule supprimé avec succès.')
        return super().form_valid(form)


# Vues pour les véhicules
def _vehicules_filtres(search, statut):
    queryset = Vehicule.objects.select_related('modele')
    if search:
        queryset = queryset.filter(
            Q(immatriculation__icontains=search) |
            Q(modele__nom__icontains=search) |
            Q(modele__marque__icontains=search)
        )
    if statut == 'actif':
        queryset = queryset.filter(actif=True)
    elif statut == 'inactif':
        queryset = queryset.filter(actif=False)
    elif statut == 'en_reparation':
        queryset = queryset.filter(
            reparations__statut__in=['en_attente', 'en_cours']
        ).distinct()
    return queryset.order_by('-actif', 'immatriculation')


@require_http_methods(["GET"])
@login_required
def vehicule_list_ajax(request):
    """Filtrage en direct de la liste des véhicules (recherche automatique)."""
    queryset = _vehicules_filtres(request.GET.get('q', ''), request.GET.get('statut', 'tous'))
    return render_paginated_partial(
        request, queryset, 'vehicules/partials/vehicule_table.html',
        list_context_name='vehicules', page_size=15, total_context_name='nb_resultats_filtres',
        extra_context={'search_query': request.GET.get('q', ''), 'statut_filtre': request.GET.get('statut', 'tous')},
    )


class VehiculeListView(LoginRequiredMixin, ListView):
    """Liste des véhicules."""
    model = Vehicule
    template_name = 'vehicules/vehicule_list.html'
    context_object_name = 'vehicules'
    paginate_by = 15

    def get_queryset(self):
        return _vehicules_filtres(self.request.GET.get('q', ''), self.request.GET.get('statut', 'tous'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_vehicules = Vehicule.objects.all()
        context['search_query'] = self.request.GET.get('q', '')
        context['statut_filtre'] = self.request.GET.get('statut', 'tous')
        context['nb_total'] = all_vehicules.count()
        context['nb_actifs'] = all_vehicules.filter(actif=True).count()
        context['nb_inactifs'] = all_vehicules.filter(actif=False).count()
        context['nb_en_reparation'] = all_vehicules.filter(
            reparations__statut__in=['en_attente', 'en_cours']
        ).distinct().count()
        context['nb_resultats_filtres'] = context['paginator'].count

        # ── Alertes documents (seuils configurables par la compagnie) ─────
        today = timezone.localdate()
        labels_courts = {
            'date_expiration_assurance': 'Assurance',
            'date_expiration_visite_technique': 'Visite tech.',
            'date_expiration_carte_grise': 'Carte grise',
            'date_expiration_licence_transport': 'Licence',
        }
        documents_actifs = Compagnie.get_instance().get_documents_alertes_actifs()

        alertes_docs = []
        for v in Vehicule.objects.filter(actif=True).select_related('modele').order_by('immatriculation'):
            docs_alertes = []
            for doc in documents_actifs:
                date_exp = getattr(v, doc['champ_date'])
                if date_exp:
                    delta = (date_exp - today).days
                    if delta <= doc['seuil_alerte']:
                        if delta < 0:
                            niveau = 'danger'
                        elif delta <= doc['seuil_urgent']:
                            niveau = 'orange'
                        else:
                            niveau = 'warning'
                        docs_alertes.append({
                            'label': labels_courts[doc['champ_date']],
                            'niveau': niveau,
                            'delta': delta,
                            'abs_delta': abs(delta),
                        })
            if docs_alertes:
                levels = [d['niveau'] for d in docs_alertes]
                worst = 'danger' if 'danger' in levels else ('orange' if 'orange' in levels else 'warning')
                alertes_docs.append({'vehicule': v, 'docs': docs_alertes, 'worst': worst})

        context['alertes_docs'] = alertes_docs
        context['nb_docs_expiries'] = sum(1 for a in alertes_docs for d in a['docs'] if d['niveau'] == 'danger')
        context['nb_docs_bientot'] = sum(1 for a in alertes_docs for d in a['docs'] if d['niveau'] in ('orange', 'warning'))
        return context


class VehiculeCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouveau véhicule."""
    model = Vehicule
    form_class = VehiculeForm
    template_name = 'vehicules/vehicule_form.html'
    success_url = reverse_lazy('vehicules:vehicule_list')

    def form_valid(self, form):
        # Assigner automatiquement la compagnie
        compagnie = Compagnie.get_instance()
        if not compagnie:
            messages.error(self.request, 'Aucune compagnie n\'est configurée. Veuillez d\'abord créer une compagnie.')
            return self.form_invalid(form)
        form.instance.compagnie = compagnie
        messages.success(self.request, 'Véhicule créé avec succès.')
        return super().form_valid(form)


class VehiculeUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un véhicule."""
    model = Vehicule
    form_class = VehiculeForm
    template_name = 'vehicules/vehicule_form.html'
    success_url = reverse_lazy('vehicules:vehicule_list')

    def form_valid(self, form):
        messages.success(self.request, 'Véhicule modifié avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicule = self.object
        km_actuel = vehicule.kilometrage_actuel or 0

        # Récupère tous les types avec suivi kilométrique
        types_suivi = TypeReparation.objects.filter(actif=True).exclude(
            necessite_kilometrage=False, intervalle_km_defaut__isnull=True
        )

        suivi_entretien = []
        for type_rep in types_suivi:
            # Dernière ligne d'intervention de ce type pour ce véhicule
            derniere = LigneIntervention.objects.filter(
                reparation__vehicule=vehicule,
                type_reparation=type_rep,
                kilometrage__isnull=False,
            ).order_by('-reparation__date_reparation').first()

            intervalle = None
            km_prochaine = None
            km_restants = None

            if derniere:
                intervalle = derniere.intervalle_km or type_rep.intervalle_km_defaut
                if intervalle:
                    km_prochaine = derniere.kilometrage + intervalle
                    km_restants = km_prochaine - km_actuel

            suivi_entretien.append({
                'type': type_rep,
                'derniere': derniere,
                'intervalle': intervalle,
                'km_prochaine': km_prochaine,
                'km_restants': km_restants,
            })

        context['suivi_entretien'] = suivi_entretien
        context['nb_alertes_entretien'] = sum(
            1 for s in suivi_entretien
            if s['km_restants'] is not None and s['km_restants'] <= 1000
        )

        # Nombre de réparations pour le badge onglet
        context['nb'] = vehicule.reparations.count()
        return context


class VehiculeDeleteView(SuperAdminRequiredMixin, DeleteView):
    """
    Désactive un véhicule (soft-delete).
    On ne supprime jamais physiquement un véhicule : il peut être référencé
    par des voyages, réparations et billets passés. On le marque inactif.
    """
    model = Vehicule
    template_name = 'vehicules/vehicule_confirm_delete.html'
    success_url = reverse_lazy('vehicules:vehicule_list')

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.actif = False
        self.object.save(update_fields=['actif'])
        messages.success(self.request, 'Véhicule désactivé avec succès.')
        return HttpResponseRedirect(success_url)


# Vues pour les réparations
def _reparations_filtrees(get_params):
    queryset = ReparationVehicule.objects.all()

    vehicule_id = get_params.get('vehicule')
    if vehicule_id:
        queryset = queryset.filter(vehicule_id=vehicule_id)

    type_reparation = get_params.get('type')
    if type_reparation:
        queryset = queryset.filter(lignes__type_reparation_id=type_reparation).distinct()

    statut = get_params.get('statut')
    if statut:
        queryset = queryset.filter(statut=statut)

    date_debut = get_params.get('date_debut')
    date_fin = get_params.get('date_fin')
    if date_debut:
        queryset = queryset.filter(date_reparation__gte=date_debut)
    if date_fin:
        queryset = queryset.filter(date_reparation__lte=date_fin)

    return queryset.select_related('vehicule', 'vehicule__modele').prefetch_related(
        'lignes__type_reparation'
    ).order_by('-date_reparation')


class ReparationVehiculeListView(LoginRequiredMixin, ListView):
    """Liste de toutes les réparations."""
    model = ReparationVehicule
    template_name = 'vehicules/reparation_list.html'
    context_object_name = 'reparations'
    paginate_by = 15

    def get_queryset(self):
        return _reparations_filtrees(self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicules'] = Vehicule.objects.all().order_by('immatriculation')
        context['types_reparation'] = TypeReparation.objects.filter(actif=True)
        context['statuts'] = ReparationVehicule.STATUT_CHOICES

        all_reps = ReparationVehicule.objects.all()
        context['nb_total']    = all_reps.count()
        context['nb_attente']  = all_reps.filter(statut='en_attente').count()
        context['nb_en_cours'] = all_reps.filter(statut='en_cours').count()
        context['nb_termines'] = all_reps.filter(statut='terminee').count()

        queryset = self.get_queryset()
        context['cout_total_periode'] = LigneIntervention.objects.filter(
            reparation__in=queryset
        ).aggregate(total=Sum('montant'))['total'] or 0

        context['vehicule_filtre']    = self.request.GET.get('vehicule', '')
        context['type_filtre']        = self.request.GET.get('type', '')
        context['statut_filtre']      = self.request.GET.get('statut', '')
        context['date_debut_filtre']  = self.request.GET.get('date_debut', '')
        context['date_fin_filtre']    = self.request.GET.get('date_fin', '')

        return context


@require_http_methods(["GET"])
@login_required
def reparation_list_ajax(request):
    """Filtrage en direct de la liste des réparations (recherche automatique)."""
    queryset = _reparations_filtrees(request.GET)
    return render_paginated_partial(
        request, queryset, 'vehicules/partials/reparation_table.html',
        list_context_name='reparations', page_size=15,
        extra_context={
            'vehicule_filtre': request.GET.get('vehicule', ''),
            'type_filtre': request.GET.get('type', ''),
            'statut_filtre': request.GET.get('statut', ''),
            'date_debut_filtre': request.GET.get('date_debut', ''),
            'date_fin_filtre': request.GET.get('date_fin', ''),
        },
    )


class ReparationVehiculeCreateView(GestionRequiredMixin, CreateView):
    """Créer une nouvelle entrée au garage (avec ses lignes d'intervention)."""
    model = ReparationVehicule
    form_class = ReparationVehiculeForm
    template_name = 'vehicules/reparation_form.html'

    def get_initial(self):
        initial = super().get_initial()
        vehicule_id = self.request.GET.get('vehicule')
        if vehicule_id:
            initial['vehicule'] = vehicule_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = LigneInterventionFormSet(self.request.POST, prefix='lignes')
        else:
            context['formset'] = LigneInterventionFormSet(prefix='lignes')
        context['vidange_type_ids'] = get_vidange_type_ids()
        context['km_type_ids'] = get_km_type_ids()
        context['suivi_km_type_ids'] = get_suivi_km_type_ids()
        context['types_reparation_json'] = self._get_types_json()
        return context

    def _get_types_json(self):
        import json
        types = TypeReparation.objects.filter(actif=True).values(
            'id', 'nom', 'necessite_kilometrage', 'is_vidange', 'intervalle_km_defaut'
        )
        return json.dumps(list(types))

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, 'Réparation enregistrée avec succès.')
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        if self.request.GET.get('from_vehicule'):
            return reverse_lazy('vehicules:vehicule_update', kwargs={'pk': self.object.vehicule.pk})
        return reverse_lazy('vehicules:reparation_list')


class ReparationVehiculeDetailView(LoginRequiredMixin, DetailView):
    """Détails d'une réparation."""
    model = ReparationVehicule
    template_name = 'vehicules/reparation_detail.html'
    context_object_name = 'reparation'


class ReparationVehiculeUpdateView(GestionRequiredMixin, UpdateView):
    """Modifier une entrée au garage."""
    model = ReparationVehicule
    form_class = ReparationVehiculeForm
    template_name = 'vehicules/reparation_form.html'

    def dispatch(self, request, *args, **kwargs):
        reparation = get_object_or_404(ReparationVehicule, pk=kwargs['pk'])
        if reparation.statut == 'terminee':
            messages.error(request, "Cette réparation est terminée et ne peut plus être modifiée.")
            return redirect('vehicules:reparation_detail', pk=reparation.pk)
        return super().dispatch(request, *args, **kwargs)

    def _get_types_json(self):
        import json
        types = TypeReparation.objects.filter(actif=True).values(
            'id', 'nom', 'necessite_kilometrage', 'is_vidange', 'intervalle_km_defaut'
        )
        return json.dumps(list(types))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = LigneInterventionFormSet(
                self.request.POST, instance=self.object, prefix='lignes'
            )
        else:
            context['formset'] = LigneInterventionFormSet(
                instance=self.object, prefix='lignes'
            )
        context['vidange_type_ids'] = get_vidange_type_ids()
        context['km_type_ids'] = get_km_type_ids()
        context['suivi_km_type_ids'] = get_suivi_km_type_ids()
        context['types_reparation_json'] = self._get_types_json()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, 'Réparation modifiée avec succès.')
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy('vehicules:reparation_detail', kwargs={'pk': self.object.pk})


class ReparationVehiculeDemarrerView(GestionRequiredMixin, View):
    """Passe une réparation de 'en_attente' à 'en_cours'."""

    def post(self, request, pk):
        reparation = get_object_or_404(ReparationVehicule, pk=pk)
        if reparation.statut == 'en_attente':
            reparation.statut = 'en_cours'
            reparation.save(update_fields=['statut', 'date_modification'])
            messages.success(request, 'La réparation est maintenant en cours.')
        return redirect('vehicules:reparation_list')


class ReparationVehiculeTerminerView(GestionRequiredMixin, View):
    """Passe une réparation de 'en_cours' à 'terminée'."""

    def post(self, request, pk):
        reparation = get_object_or_404(ReparationVehicule, pk=pk)
        if reparation.statut == 'en_cours':
            reparation.statut = 'terminee'
            reparation.save(update_fields=['statut', 'date_modification'])
            messages.success(request, 'La réparation a été marquée comme terminée.')
        return redirect('vehicules:reparation_list')


class ReparationVehiculeDeleteView(SuperAdminRequiredMixin, DeleteView):
    """Supprimer une réparation — uniquement si statut 'en_attente'."""
    model = ReparationVehicule
    template_name = 'vehicules/reparation_confirm_delete.html'
    success_url = reverse_lazy('vehicules:reparation_list')

    def dispatch(self, request, *args, **kwargs):
        reparation = get_object_or_404(ReparationVehicule, pk=kwargs['pk'])
        if reparation.statut != 'en_attente':
            messages.error(request, "Seules les réparations en attente peuvent être supprimées.")
            return redirect('vehicules:reparation_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Réparation supprimée avec succès.')
        return super().form_valid(form)


# Vue pour le rapport analytique
class RapportReparationsView(GestionRequiredMixin, TemplateView):
    """Rapport analytique des réparations véhicules."""
    template_name = 'vehicules/rapport_reparations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Récupérer les filtres de date
            date_debut = self.request.GET.get('date_debut')
            date_fin = self.request.GET.get('date_fin')

            # Par défaut, les 12 derniers mois
            if not date_debut:
                date_debut = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            if not date_fin:
                date_fin = datetime.now().strftime('%Y-%m-%d')

            context['date_debut'] = date_debut
            context['date_fin'] = date_fin

            # Requête filtrée — on travaille sur les lignes d'intervention
            lignes = LigneIntervention.objects.filter(
                reparation__date_reparation__gte=date_debut,
                reparation__date_reparation__lte=date_fin
            )
            reparations = ReparationVehicule.objects.filter(
                date_reparation__gte=date_debut,
                date_reparation__lte=date_fin
            )

            # Statistiques globales
            context['cout_total'] = lignes.aggregate(total=Sum('montant'))['total'] or 0
            context['nb_reparations'] = reparations.count()
            context['nb_vehicules'] = reparations.values('vehicule').distinct().count()

            # Statistiques par véhicule
            vehicules_stats = []
            for vehicule in Vehicule.objects.select_related('modele').all():
                lignes_vehicule = lignes.filter(reparation__vehicule=vehicule)
                cout_total = lignes_vehicule.aggregate(total=Sum('montant'))['total'] or 0
                nb_reparations = reparations.filter(vehicule=vehicule).count()

                if nb_reparations > 0:
                    cout_moyen = cout_total / nb_reparations

                    # Déterminer le niveau d'alerte
                    if cout_total > 2000000:
                        niveau_alerte = 'critique'
                    elif cout_total > 1000000:
                        niveau_alerte = 'surveillance'
                    else:
                        niveau_alerte = 'normal'

                    vehicules_stats.append({
                        'vehicule': vehicule,
                        'cout_total': cout_total,
                        'nb_reparations': nb_reparations,
                        'cout_moyen': cout_moyen,
                        'niveau_alerte': niveau_alerte
                    })

            # Trier par coût total décroissant
            vehicules_stats.sort(key=lambda x: x['cout_total'], reverse=True)
            context['vehicules_stats'] = vehicules_stats

            # Répartition par type de réparation
            types_stats = []
            cout_total_types = context['cout_total']
            for type_rep in TypeReparation.objects.filter(actif=True):
                cout = lignes.filter(type_reparation=type_rep).aggregate(total=Sum('montant'))['total'] or 0
                if cout > 0:
                    pourcentage = (cout / cout_total_types * 100) if cout_total_types > 0 else 0
                    types_stats.append({
                        'label': type_rep.nom,
                        'cout': cout,
                        'pourcentage': pourcentage
                    })

            context['types_stats'] = types_stats
            context['types_stats_json'] = json.dumps([
                {'label': t['label'], 'cout': float(t['cout']), 'pourcentage': float(round(t['pourcentage'], 1))}
                for t in types_stats
            ])

            # Véhicules critiques (> 2M)
            context['vehicules_critiques'] = [v for v in vehicules_stats if v['niveau_alerte'] == 'critique']

            # JSON pour le graphique véhicules
            context['vehicules_stats_json'] = json.dumps([
                {
                    'label': v['vehicule'].display_immat,
                    'cout': float(v['cout_total']),
                    'niveau': v['niveau_alerte']
                }
                for v in vehicules_stats[:10]
            ])

            # Coût moyen par véhicule
            context['cout_moyen_vehicule'] = (
                int(context['cout_total'] / context['nb_vehicules'])
                if context['nb_vehicules'] > 0 else 0
            )

            # Matrice heatmap : véhicule × type de réparation
            types_actifs = TypeReparation.objects.filter(actif=True).order_by('nom')
            types_noms = [t.nom for t in types_actifs]
            context['types_actifs_noms'] = types_noms
            context['types_actifs_noms_json'] = json.dumps(types_noms)

            matrice = []
            for v_stat in vehicules_stats:
                vehicule = v_stat['vehicule']
                lignes_veh = lignes.filter(reparation__vehicule=vehicule)
                costs = {}
                for type_rep in types_actifs:
                    montant = lignes_veh.filter(type_reparation=type_rep).aggregate(
                        total=Sum('montant')
                    )['total'] or 0
                    costs[type_rep.nom] = float(montant)
                matrice.append({
                    'label': vehicule.display_immat,
                    'costs': costs,
                    'total': float(v_stat['cout_total']),
                    'niveau': v_stat['niveau_alerte'],
                })
            context['matrice_json'] = json.dumps(matrice)

        except Exception as e:
            logger.error(f"Erreur dans RapportReparationsView: {e}", exc_info=True)
            context.setdefault('date_debut', datetime.now().strftime('%Y-%m-%d'))
            context.setdefault('date_fin', datetime.now().strftime('%Y-%m-%d'))
            context.setdefault('cout_total', 0)
            context.setdefault('nb_reparations', 0)
            context.setdefault('nb_vehicules', 0)
            context.setdefault('vehicules_stats', [])
            context.setdefault('types_stats', [])
            context.setdefault('types_stats_json', '[]')
            context.setdefault('vehicules_stats_json', '[]')
            context.setdefault('vehicules_critiques', [])
            context.setdefault('cout_moyen_vehicule', 0)
            context.setdefault('types_actifs_noms', [])
            context.setdefault('types_actifs_noms_json', '[]')
            context.setdefault('matrice_json', '[]')

        return context


# Vues pour les types de réparation
def _types_reparation_filtres(search):
    queryset = TypeReparation.objects.all()
    if search:
        queryset = queryset.filter(
            Q(nom__icontains=search) |
            Q(description__icontains=search)
        )
    return queryset.order_by('nom')


class TypeReparationListView(LoginRequiredMixin, ListView):
    """Liste des types de réparation."""
    model = TypeReparation
    template_name = 'vehicules/type_reparation_list.html'
    context_object_name = 'types_reparation'

    def get_queryset(self):
        return _types_reparation_filtres(self.request.GET.get('q'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


@require_http_methods(["GET"])
@login_required
def type_reparation_list_ajax(request):
    """Filtrage en direct des types de réparation (recherche automatique)."""
    queryset = _types_reparation_filtres(request.GET.get('q'))
    return render(request, 'vehicules/partials/type_reparation_table.html', {'types_reparation': queryset})


class TypeReparationCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouveau type de réparation."""
    model = TypeReparation
    form_class = TypeReparationForm
    template_name = 'vehicules/type_reparation_form.html'
    success_url = reverse_lazy('vehicules:type_reparation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Type de réparation créé avec succès.')
        return super().form_valid(form)


class TypeReparationUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un type de réparation."""
    model = TypeReparation
    form_class = TypeReparationForm
    template_name = 'vehicules/type_reparation_form.html'
    success_url = reverse_lazy('vehicules:type_reparation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Type de réparation modifié avec succès.')
        return super().form_valid(form)


class TypeReparationDeleteView(AdminRequiredMixin, DeleteView):
    """Supprimer un type de réparation."""
    model = TypeReparation
    template_name = 'vehicules/type_reparation_confirm_delete.html'
    success_url = reverse_lazy('vehicules:type_reparation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Type de réparation supprimé avec succès.')
        return super().form_valid(form)



# ==================== RENTABILITÉ VÉHICULE ====================

class RentabiliteVehiculeView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Rapport de rentabilité d'un véhicule sur une période donnée."""
    template_name = 'vehicules/rentabilite.html'

    def test_func(self):
        """Accessible uniquement par PDG, Super Admin et Manager."""
        return self.request.user.role in ['pdg', 'super_admin', 'manager']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Paramètres de filtrage
        vehicule_id = self.request.GET.get('vehicule')
        date_debut_str = self.request.GET.get('date_debut')
        date_fin_str = self.request.GET.get('date_fin')

        today = timezone.now().date()

        # Parse des dates
        if date_debut_str:
            try:
                date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                date_debut = today.replace(day=1)
        else:
            date_debut = today.replace(day=1)

        if date_fin_str:
            try:
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
            except ValueError:
                date_fin = today
        else:
            date_fin = today

        if date_fin < date_debut:
            date_fin = date_debut

        context['date_debut'] = date_debut
        context['date_fin'] = date_fin

        # Liste des véhicules pour le filtre
        context['vehicules'] = Vehicule.objects.select_related('modele').order_by('immatriculation')

        # Véhicule sélectionné
        vehicule_selectionne = None
        if vehicule_id:
            try:
                vehicule_selectionne = Vehicule.objects.select_related('modele').get(id=vehicule_id)
            except Vehicule.DoesNotExist:
                pass
        context['vehicule_selectionne'] = vehicule_selectionne

        if not vehicule_selectionne:
            context['donnees_rapport'] = []
            return context

        # Voyages du véhicule sur la période
        from apps.voyages.models import Voyage
        voyages_query = Voyage.objects.filter(
            vehicule=vehicule_selectionne,
            date_depart__gte=date_debut,
            date_depart__lte=date_fin,
            statut__in=['programme', 'en_cours', 'termine']
        ).select_related('gare', 'ligne').prefetch_related(
            'billets', 'depenses', 'depenses__type_depense'
        ).order_by('date_depart', 'heure_depart', 'numero_depart')

        # Construire les données du rapport
        donnees_rapport = []
        types_depenses_presents = set()
        total_nb_passagers = 0
        total_recette_billets = Decimal('0')
        total_recette_bagages = Decimal('0')
        total_depenses = Decimal('0')

        for voyage in voyages_query:
            nb_passagers = voyage.billets.filter(statut='paye').count()
            recette_billets = voyage.billets.filter(statut='paye').aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0')
            recette_bagages = voyage.recette_bagages or Decimal('0')

            # Dépenses par type
            depenses_par_type = {}
            total_depenses_voyage = Decimal('0')

            for depense in voyage.depenses.all():
                type_nom = depense.type_depense.nom
                if type_nom not in depenses_par_type:
                    depenses_par_type[type_nom] = Decimal('0')
                depenses_par_type[type_nom] += depense.montant
                total_depenses_voyage += depense.montant
                types_depenses_presents.add(type_nom)

            benefice_net = (recette_billets + recette_bagages) - total_depenses_voyage

            donnees_rapport.append({
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
            })

            total_nb_passagers += nb_passagers
            total_recette_billets += recette_billets
            total_recette_bagages += recette_bagages
            total_depenses += total_depenses_voyage

        context['donnees_rapport'] = donnees_rapport
        context['types_depenses_presents'] = sorted(list(types_depenses_presents))

        # Réparations du véhicule sur la période
        total_reparations = LigneIntervention.objects.filter(
            reparation__vehicule=vehicule_selectionne,
            reparation__date_reparation__gte=date_debut,
            reparation__date_reparation__lte=date_fin
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0')

        # Colonnes dynamiques
        colonnes = ['Date', 'Gare', 'Ligne', 'N° Départ', 'Nb Pass.', 'Recette Billets', 'Recette Bagages']
        colonnes.extend(sorted(list(types_depenses_presents)))
        colonnes.extend(['Total Dépenses', 'Recette Net'])
        context['colonnes'] = colonnes

        # Totaux par colonne
        totaux = {
            'nb_passagers': total_nb_passagers,
            'recette_billets': total_recette_billets,
            'recette_bagages': total_recette_bagages,
            'total_depenses': total_depenses,
            'benefice_net': (total_recette_billets + total_recette_bagages) - total_depenses,
        }
        for type_dep_nom in types_depenses_presents:
            totaux[type_dep_nom] = sum(
                d['depenses'].get(type_dep_nom, Decimal('0'))
                for d in donnees_rapport
            )
        context['totaux'] = totaux

        # Cartes récapitulatives
        context['nb_voyages'] = len(donnees_rapport)
        context['total_recette_billets'] = total_recette_billets
        context['total_recette_bagages'] = total_recette_bagages
        context['total_depenses'] = total_depenses
        context['total_reparations'] = total_reparations
        context['benefice_net_global'] = (total_recette_billets + total_recette_bagages) - total_depenses - total_reparations

        return context


# ==================== REPARATIONS AJAX ====================

@require_http_methods(["GET"])
def reparations_vehicule_ajax(request, pk):
    """Retourne le partial des réparations paginé (10/page) avec filtre optionnel par statut."""
    from django.contrib.auth.decorators import login_required
    if not request.user.is_authenticated:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    vehicule = get_object_or_404(Vehicule, pk=pk)
    statut_filtre = request.GET.get('statut', '')
    page_num = request.GET.get('page', 1)

    qs = vehicule.reparations.prefetch_related('lignes__type_reparation').order_by('-date_reparation')
    if statut_filtre:
        qs = qs.filter(statut=statut_filtre)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(page_num)

    nb_tous      = vehicule.reparations.count()
    nb_terminee  = vehicule.reparations.filter(statut='terminee').count()
    nb_en_cours  = vehicule.reparations.filter(statut='en_cours').count()
    nb_en_attente = vehicule.reparations.filter(statut='en_attente').count()

    return render(request, 'vehicules/partials/reparations_historique.html', {
        'vehicule': vehicule,
        'reparations': page_obj,
        'page_obj': page_obj,
        'statut_filtre': statut_filtre,
        'nb_tous': nb_tous,
        'nb_terminee': nb_terminee,
        'nb_en_cours': nb_en_cours,
        'nb_en_attente': nb_en_attente,
    })


@require_http_methods(["GET"])
def entretien_historique_ajax(request, pk):
    """Retourne le tableau historique des entretiens kilométriques, paginé (10/page)."""
    if not request.user.is_authenticated:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    vehicule = get_object_or_404(Vehicule, pk=pk)
    page_num = request.GET.get('page', 1)

    lignes = LigneIntervention.objects.filter(
        reparation__vehicule=vehicule,
        kilometrage__isnull=False,
    ).filter(
        Q(type_reparation__necessite_kilometrage=True) |
        Q(type_reparation__intervalle_km_defaut__isnull=False)
    ).select_related(
        'type_reparation', 'reparation'
    ).order_by('-reparation__date_reparation')

    paginator = Paginator(lignes, 10)
    page_obj = paginator.get_page(page_num)

    return render(request, 'vehicules/partials/entretien_historique_table.html', {
        'vehicule': vehicule,
        'page_obj': page_obj,
    })


# ==================== API AJAX ====================

@require_http_methods(["GET"])
def get_vehicule_km(request, pk):
    """Retourne le kilométrage actuel d'un véhicule (pré-remplissage du formulaire garage)."""
    if not request.user.is_authenticated:
        return HttpResponseForbidden()
    try:
        vehicule = get_object_or_404(Vehicule, pk=pk)
        return JsonResponse({'success': True, 'kilometrage_actuel': vehicule.kilometrage_actuel or 0})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["GET"])
def get_types_reparation(request):
    """
    Vue AJAX pour récupérer la liste des types de réparation actifs.
    Utilisé par le modal de création de réparation depuis une dépense.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden()
    try:
        types = TypeReparation.objects.filter(actif=True).order_by('nom')
        
        types_data = [
            {
                'id': t.id,
                'nom': t.nom,
                'description': t.description or '',
                'necessite_kilometrage': t.necessite_kilometrage,
                'is_vidange': t.is_vidange,
                'intervalle_km_defaut': t.intervalle_km_defaut,
            }
            for t in types
        ]
        
        return JsonResponse({
            'success': True,
            'types': types_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
