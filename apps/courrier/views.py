import json
import unicodedata
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View

from core.mixins import AdminRequiredMixin

from apps.clients.models import Client
from apps.gares.models import Gare
from apps.voyages.models import Voyage

from .forms import ColisForm, RetraitColisForm, TypeColisForm
from .mixins import CourrierAccessRequiredMixin
from .models import Colis, HistoriqueStatutColis, TypeColis
from .utils import generer_bordereau_pdf


def _normaliser_ville(nom):
    """
    Majuscules, sans accents — les villes sont saisies à la main (Ligne et
    Gare sont deux formulaires indépendants), donc 'BOUAKÉ' et 'BOUAKE'
    doivent être reconnus comme la même ville. __iexact seul ne suffit pas :
    il est insensible à la casse mais pas aux accents.
    """
    if not nom:
        return ''
    sans_accents = unicodedata.normalize('NFKD', nom).encode('ascii', 'ignore').decode('ascii')
    return sans_accents.strip().upper()


def _gares_pour_voyage(voyage):
    """
    Gares actives de la compagnie dont la ville correspond à la ville
    d'arrivée du voyage. Voyage n'a pas de FK "gare d'arrivée" (seulement
    ligne.ville_arrivee, en texte libre) — un colis ne peut être livré que
    là où la compagnie a effectivement une gare (du personnel).
    """
    if not voyage.ligne_id:
        return Gare.objects.none()
    cible = _normaliser_ville(voyage.ligne.ville_arrivee)
    ids_correspondants = [
        gare.pk for gare in Gare.objects.filter(active=True)
        if _normaliser_ville(gare.ville) == cible
    ]
    return Gare.objects.filter(pk__in=ids_correspondants)


# ==================== COLIS ====================

def _colis_filtres(user, statut, search):
    """
    Queryset de colis filtrée par gare de l'utilisateur, statut et recherche
    libre — partagée entre ColisListView (page classique) et colis_list_ajax
    (filtrage en direct pendant la saisie), pour ne jamais faire diverger
    les deux.
    """
    queryset = Colis.objects.select_related(
        'gare_origine', 'gare_destination', 'type_colis', 'voyage', 'guichetier_enregistrement'
    )
    if not user.has_global_access and user.gare_id:
        # La liste n'appartient qu'à la gare qui a enregistré le colis — la gare de
        # destination ne le voit qu'une fois chargé sur un voyage, via la recherche
        # de retrait (RetraitColisView), pas dans cette liste. Voir ColisDetailView
        # pour la même règle appliquée à la fiche détail.
        queryset = queryset.filter(gare_origine_id=user.gare_id)
    if statut:
        queryset = queryset.filter(statut=statut)
    if search:
        queryset = queryset.filter(
            Q(code_colis__icontains=search) |
            Q(expediteur_nom__icontains=search) | Q(expediteur_telephone__icontains=search) |
            Q(destinataire_nom__icontains=search) | Q(destinataire_telephone__icontains=search)
        )
    return queryset.order_by('-date_creation')


class CourrierDashboardView(CourrierAccessRequiredMixin, TemplateView):
    """
    Tableau de bord du module Courrier — page d'accueil du module (le hub y
    renvoie désormais au lieu de la liste des colis, voir migration
    0005_dashboard_module_courrier). KPIs du jour et évolution sur 7 jours,
    filtrés par gare comme le reste du module : gare d'origine pour ce que
    la gare enregistre/charge, gare de destination pour ce qu'elle
    réceptionne/retire — accès global pour pdg/super_admin/manager.
    """
    template_name = 'courrier/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        scoped_gare = None if user.has_global_access else user.gare_id

        colis_origine = Colis.objects.all()
        if scoped_gare:
            colis_origine = colis_origine.filter(gare_origine_id=scoped_gare)

        colis_destination = Colis.objects.all()
        if scoped_gare:
            colis_destination = colis_destination.filter(gare_destination_id=scoped_gare)

        # ── KPIs du jour ────────────────────────────────────────────
        context['colis_enregistres_today'] = colis_origine.filter(date_creation__date=today).count()
        context['colis_charges_today'] = colis_origine.filter(date_chargement__date=today).count()
        context['montant_today'] = colis_origine.exclude(statut='annule').filter(
            paye=True, date_paiement__date=today
        ).aggregate(total=Sum('montant'))['total'] or 0

        voyages_today = Voyage.objects.filter(date_depart=today)
        if scoped_gare:
            voyages_today = voyages_today.filter(gare_id=scoped_gare)
        context['voyages_today'] = voyages_today.count()

        # ── Actions rapides : en attente d'action côté opérationnel ──
        context['en_attente_chargement'] = colis_origine.filter(statut='enregistre').count()
        context['a_receptionner'] = colis_destination.filter(statut__in=['en_transit', 'arrive']).count()
        context['prets_retrait'] = colis_destination.filter(statut='receptionne').count()

        # ── Évolution sur 7 jours (aujourd'hui inclus) ───────────────
        date_debut = today - timedelta(days=6)
        jours = [date_debut + timedelta(days=i) for i in range(7)]

        par_jour_enreg = colis_origine.filter(date_creation__date__gte=date_debut).annotate(
            jour=TruncDate('date_creation')
        ).values('jour').annotate(n=Count('id')).order_by('jour')
        par_jour_charg = colis_origine.filter(date_chargement__date__gte=date_debut).annotate(
            jour=TruncDate('date_chargement')
        ).values('jour').annotate(n=Count('id')).order_by('jour')
        par_jour_montant = colis_origine.exclude(statut='annule').filter(
            paye=True, date_paiement__date__gte=date_debut
        ).annotate(jour=TruncDate('date_paiement')).values('jour').annotate(total=Sum('montant')).order_by('jour')

        map_enreg = {r['jour']: r['n'] for r in par_jour_enreg}
        map_charg = {r['jour']: r['n'] for r in par_jour_charg}
        map_montant = {r['jour']: float(r['total'] or 0) for r in par_jour_montant}

        context['evolution_labels'] = json.dumps([j.strftime('%d/%m') for j in jours])
        context['evolution_enregistres'] = json.dumps([map_enreg.get(j, 0) for j in jours])
        context['evolution_charges'] = json.dumps([map_charg.get(j, 0) for j in jours])
        context['evolution_montant'] = json.dumps([map_montant.get(j, 0) for j in jours])

        return context


class ColisListView(LoginRequiredMixin, ListView):
    """Liste des colis, filtrable par statut et recherche libre."""
    model = Colis
    template_name = 'courrier/colis_list.html'
    context_object_name = 'colis_liste'
    paginate_by = 20

    def get_queryset(self):
        return _colis_filtres(
            self.request.user,
            self.request.GET.get('statut'),
            self.request.GET.get('q'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuts'] = Colis.STATUT_CHOICES
        context['statut_filtre'] = self.request.GET.get('statut', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['nb_total'] = self.get_queryset().count()
        return context


@require_http_methods(["GET"])
@login_required
def colis_list_ajax(request):
    """
    Filtrage en direct de la liste des colis (recherche/statut) sans
    rechargement de page — appelé pendant la saisie, voir colis_list.html.
    Retourne le même partial que ColisListView pour rester identique en tout
    point à un rechargement classique.
    """
    queryset = _colis_filtres(request.user, request.GET.get('statut'), request.GET.get('q'))
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    response = render(request, 'courrier/partials/colis_table.html', {
        'colis_liste': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'statut_filtre': request.GET.get('statut', ''),
        'search_query': request.GET.get('q', ''),
    })
    response['X-Nb-Total'] = str(paginator.count)
    return response


class ColisCreateView(CourrierAccessRequiredMixin, CreateView):
    """Enregistrement d'un nouveau colis."""
    model = Colis
    form_class = ColisForm
    template_name = 'courrier/colis_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['types_colis'] = TypeColis.objects.filter(actif=True)
        return context

    def form_valid(self, form):
        user = self.request.user
        colis = form.save(commit=False)

        if not user.has_global_access and user.gare_id:
            colis.gare_origine = user.gare

        expediteur, _ = Client.objects.get_or_create(
            telephone=form.cleaned_data['expediteur_telephone'],
            defaults={'nom_complet': form.cleaned_data['expediteur_nom']}
        )
        destinataire, _ = Client.objects.get_or_create(
            telephone=form.cleaned_data['destinataire_telephone'],
            defaults={'nom_complet': form.cleaned_data['destinataire_nom']}
        )
        colis.expediteur = expediteur
        colis.destinataire = destinataire
        colis.guichetier_enregistrement = user
        colis.statut = 'enregistre'

        # Le port est toujours payé par l'expéditeur, encaissé immédiatement à l'enregistrement.
        colis.qui_paie = 'expediteur'
        colis.paye = True
        colis.date_paiement = timezone.now()

        colis.save()

        HistoriqueStatutColis.objects.create(
            colis=colis, ancien_statut='', nouveau_statut='enregistre',
            agent=user, gare=colis.gare_origine,
        )

        messages.success(self.request, f"Colis {colis.code_colis} enregistré avec succès.")
        self.object = colis
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('courrier:colis_detail', kwargs={'public_id': self.object.public_id})


def _peut_voir_colis(user, colis):
    """
    Règle d'accès à la fiche d'un colis : la gare d'origine y a toujours accès
    (dès l'enregistrement) ; la gare de destination seulement une fois le
    colis chargé sur un voyage (statut différent de 'enregistre') — avant
    ça, ce colis n'existe pas pour elle. Toute autre gare n'y a jamais accès.
    """
    if user.has_global_access:
        return True
    if not user.gare_id:
        return False
    if colis.gare_origine_id == user.gare_id:
        return True
    if colis.gare_destination_id == user.gare_id and colis.statut != 'enregistre':
        return True
    return False


class ColisDetailView(LoginRequiredMixin, DetailView):
    model = Colis
    template_name = 'courrier/colis_detail.html'
    context_object_name = 'colis'
    slug_field = 'public_id'
    slug_url_kwarg = 'public_id'

    def get_object(self, queryset=None):
        colis = super().get_object(queryset)
        if not _peut_voir_colis(self.request.user, colis):
            raise PermissionDenied("Vous n'avez pas accès à ce colis.")
        return colis

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['historique'] = self.object.historique.select_related('agent', 'gare').all()
        user = self.request.user
        context['peut_annuler_colis'] = (
            self.object.statut == 'enregistre' and (user.is_superuser or user.role == 'super_admin')
        )
        return context


class ColisAnnulerView(CourrierAccessRequiredMixin, View):
    """
    Annule un colis — uniquement tant qu'il n'a pas encore été chargé, et
    réservé au rôle super_admin (restriction demandée par l'utilisateur :
    l'annulation n'est plus une action de guichet courant, même pour la
    gare d'origine).
    """

    def post(self, request, public_id):
        colis = get_object_or_404(Colis, public_id=public_id)
        user = request.user
        if not (user.is_superuser or user.role == 'super_admin'):
            raise PermissionDenied("Seul un super administrateur peut annuler un colis.")
        if colis.statut == 'enregistre':
            colis.annuler(agent=request.user, note=request.POST.get('motif', ''))
            messages.success(request, f"Colis {colis.code_colis} annulé.")
        else:
            messages.error(request, "Seul un colis encore « Enregistré » (non chargé) peut être annulé.")
        return redirect('courrier:colis_detail', public_id=colis.public_id)


# ==================== CHARGEMENT EN LOT ====================

class ChargementListeVoyagesView(CourrierAccessRequiredMixin, ListView):
    """Liste des départs à venir de la gare, avec le nombre de colis en attente pour chacun."""
    model = Voyage
    template_name = 'courrier/chargement_liste.html'
    context_object_name = 'voyages'

    def get_queryset(self):
        user = self.request.user
        queryset = Voyage.objects.filter(
            statut__in=['programme', 'en_cours'],
            date_depart__gte=timezone.now().date(),
        ).select_related('ligne', 'gare')
        if not user.has_global_access and user.gare_id:
            queryset = queryset.filter(gare_id=user.gare_id)
        return queryset.order_by('date_depart', 'heure_depart')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voyages_info = []
        for voyage in context['voyages']:
            gares_dest = _gares_pour_voyage(voyage)
            nb_colis = Colis.objects.filter(
                statut='enregistre', gare_origine=voyage.gare, gare_destination__in=gares_dest
            ).count() if gares_dest.exists() else 0
            voyages_info.append({
                'voyage': voyage,
                'nb_colis': nb_colis,
                'destination_reconnue': gares_dest.exists(),
            })
        context['voyages_info'] = voyages_info
        return context


class ChargementVoyageView(CourrierAccessRequiredMixin, View):
    """Écran de chargement : sélection en lot des colis à rattacher à un voyage précis."""

    def _get_voyage(self, request, public_id):
        voyage = get_object_or_404(
            Voyage.objects.select_related('gare', 'ligne', 'vehicule', 'chauffeur'),
            public_id=public_id
        )
        user = request.user
        if not user.has_global_access and voyage.gare_id != user.gare_id:
            raise PermissionDenied("Ce voyage n'appartient pas à votre gare.")
        return voyage

    def get(self, request, public_id):
        voyage = self._get_voyage(request, public_id)
        gares_dest = _gares_pour_voyage(voyage)
        if gares_dest.exists():
            colis_en_attente = Colis.objects.filter(
                statut='enregistre', gare_origine=voyage.gare, gare_destination__in=gares_dest
            ).select_related('gare_destination', 'type_colis').order_by('date_creation')
        else:
            colis_en_attente = Colis.objects.none()

        colis_charges = Colis.objects.filter(voyage=voyage).exclude(
            statut='enregistre'
        ).select_related('gare_destination', 'type_colis').order_by('-date_chargement')

        paginator = Paginator(colis_en_attente, 20)
        page_obj = paginator.get_page(request.GET.get('page', 1))

        return render(request, 'courrier/chargement_voyage.html', {
            'voyage': voyage,
            'destination_reconnue': gares_dest.exists(),
            'colis_en_attente': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'colis_charges': colis_charges,
        })

    def post(self, request, public_id):
        voyage = self._get_voyage(request, public_id)

        if voyage.date_depart < timezone.now().date():
            messages.error(request, "Ce voyage est déjà passé, impossible d'y charger un colis.")
            return redirect('courrier:chargement_voyage', public_id=voyage.public_id)

        gares_dest = _gares_pour_voyage(voyage)
        colis_ids = request.POST.getlist('colis_id')

        if not colis_ids:
            messages.error(request, "Aucun colis sélectionné.")
            return redirect('courrier:chargement_voyage', public_id=voyage.public_id)

        colis_valides = Colis.objects.filter(
            public_id__in=colis_ids, statut='enregistre',
            gare_origine=voyage.gare, gare_destination__in=gares_dest
        )
        nb = 0
        for colis in colis_valides:
            colis.marquer_en_transit(voyage, request.user)
            nb += 1

        if nb:
            messages.success(request, f"{nb} colis chargé(s) sur ce voyage. Le bordereau est disponible ci-dessous.")
        else:
            messages.error(request, "Aucun des colis sélectionnés n'a pu être chargé (déjà traité entre-temps ?).")
        return redirect('courrier:chargement_voyage', public_id=voyage.public_id)


@login_required
def bordereau_pdf(request, public_id):
    """Bordereau de chargement colis d'un voyage, en PDF — accessible à tout moment après coup."""
    voyage = get_object_or_404(
        Voyage.objects.select_related('gare', 'ligne', 'vehicule', 'chauffeur'),
        public_id=public_id
    )
    user = request.user
    if not user.has_global_access and voyage.gare_id != user.gare_id:
        return HttpResponseForbidden()

    colis_qs = voyage.colis.exclude(statut='enregistre').select_related(
        'gare_destination', 'type_colis'
    ).order_by('gare_destination__nom', 'code_colis')

    return generer_bordereau_pdf(voyage, colis_qs)


# ==================== RÉCEPTION ====================

class ReceptionColisView(CourrierAccessRequiredMixin, View):
    """
    Écran de réception : la gare de destination confirme, colis par colis,
    qu'elle a physiquement en main ce qui lui a été envoyé — dès 'en_transit'
    (pas besoin d'attendre que le voyage soit marqué "Terminé" par la gare
    d'origine, une action séparée pas toujours faite en pratique) ou 'arrive'.
    Tant que ce n'est pas fait, le retrait reste bloqué — voir
    RetraitColisView et Colis.marquer_receptionne().
    """

    def get(self, request):
        user = request.user
        queryset = Colis.objects.filter(statut__in=['en_transit', 'arrive']).select_related(
            'gare_origine', 'type_colis', 'voyage'
        ).order_by('date_creation')
        if not user.has_global_access and user.gare_id:
            queryset = queryset.filter(gare_destination_id=user.gare_id)

        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(request.GET.get('page', 1))

        return render(request, 'courrier/reception.html', {
            'colis_a_receptionner': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
        })

    def post(self, request):
        user = request.user
        colis_ids = request.POST.getlist('colis_id')

        if not colis_ids:
            messages.error(request, "Aucun colis sélectionné.")
            return redirect('courrier:reception_liste')

        colis_valides = Colis.objects.filter(public_id__in=colis_ids, statut__in=['en_transit', 'arrive'])
        if not user.has_global_access and user.gare_id:
            colis_valides = colis_valides.filter(gare_destination_id=user.gare_id)

        nb = 0
        for colis in colis_valides:
            colis.marquer_receptionne(user)
            nb += 1

        if nb:
            messages.success(request, f"{nb} colis réceptionné(s) — le retrait est maintenant possible.")
        else:
            messages.error(request, "Aucun des colis sélectionnés n'a pu être réceptionné (déjà traité entre-temps ?).")
        return redirect('courrier:reception_liste')


# ==================== RETRAIT ====================

def _rechercher_colis_retrait(user, query):
    """
    Recherche partagée entre RetraitColisView (page classique) et
    retrait_recherche_ajax (recherche en direct) — ouverte dès 'en_transit',
    c'est le seul moyen pour la gare de destination de "voir" un colis qui la
    concerne avant son arrivée (il n'apparaît jamais dans sa liste, voir
    _colis_filtres). Retourne (colis, message_erreur).
    """
    if not query:
        return None, None
    candidats = Colis.objects.filter(statut__in=['en_transit', 'arrive', 'receptionne']).filter(
        Q(code_colis__iexact=query) | Q(destinataire_telephone__icontains=query)
    )
    if not user.has_global_access and user.gare_id:
        candidats = candidats.filter(gare_destination_id=user.gare_id)
    colis = candidats.first()
    if not colis:
        return None, "Aucun colis en transit, arrivé ou réceptionné ne correspond à cette recherche."
    return colis, None


def _form_retrait_pour(colis):
    """Formulaire de retrait, pré-rempli avec le destinataire et le code de retrait du colis — seulement si prêt à être retiré."""
    if not colis or colis.statut != 'receptionne':
        return None
    return RetraitColisForm(initial={
        'code_retrait': colis.code_retrait,
        'retirant_nom': colis.destinataire_nom,
        'retirant_telephone': colis.destinataire_telephone,
    })


class RetraitColisView(CourrierAccessRequiredMixin, View):
    """
    Recherche puis confirmation de retrait d'un colis. Le retrait effectif
    (formulaire + POST) reste réservé aux colis 'receptionne' : 'arrive' seul
    ne suffit pas, il faut d'abord passer par l'écran de réception
    (ReceptionColisView).
    """

    def get(self, request):
        query = request.GET.get('q', '').strip()
        colis, erreur = _rechercher_colis_retrait(request.user, query)
        return render(request, 'courrier/retrait.html', {
            'query': query,
            'colis': colis,
            'erreur_recherche': erreur,
            'form': _form_retrait_pour(colis),
        })

    def post(self, request):
        colis = get_object_or_404(Colis, public_id=request.POST.get('colis_id'), statut='receptionne')
        user = request.user
        if not user.has_global_access and colis.gare_destination_id != user.gare_id:
            return HttpResponseForbidden()

        form = RetraitColisForm(request.POST)
        if not form.is_valid():
            return render(request, 'courrier/retrait.html', {'colis': colis, 'form': form, 'query': colis.code_colis})

        if form.cleaned_data['code_retrait'].strip() != colis.code_retrait:
            form.add_error('code_retrait', "Code de retrait incorrect.")
            return render(request, 'courrier/retrait.html', {'colis': colis, 'form': form, 'query': colis.code_colis})

        retirant_telephone = form.cleaned_data['retirant_telephone'].strip()
        retirant_nom = form.cleaned_data['retirant_nom'].strip()
        numero_cni = form.cleaned_data['piece_identite'].strip()

        retirant, _ = Client.objects.get_or_create(
            telephone=retirant_telephone,
            defaults={'nom_complet': retirant_nom, 'numero_cni': numero_cni}
        )
        champs_a_jour = []
        if retirant.nom_complet != retirant_nom:
            retirant.nom_complet = retirant_nom
            champs_a_jour.append('nom_complet')
        if numero_cni and retirant.numero_cni != numero_cni:
            retirant.numero_cni = numero_cni
            champs_a_jour.append('numero_cni')
        if champs_a_jour:
            retirant.save(update_fields=champs_a_jour)

        colis.marquer_retire(
            agent=user,
            piece_identite=numero_cni,
            retirant=retirant,
            retirant_nom=retirant_nom,
            retirant_telephone=retirant_telephone,
        )
        messages.success(request, f"Colis {colis.code_colis} remis à {retirant_nom}.")
        return redirect('courrier:colis_detail', public_id=colis.public_id)


class RetraitHistoriqueListView(CourrierAccessRequiredMixin, ListView):
    """
    Historique des colis retirés (les plus récents en premier), avec qui les
    a retirés — sous-menu "Historique Retrait" à côté de l'écran de retrait
    lui-même. Même scope par gare que le retrait (gare_destination) et même
    pagination que ColisListView (20 par page).
    """
    model = Colis
    template_name = 'courrier/retrait_historique.html'
    context_object_name = 'colis_liste'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Colis.objects.filter(statut='retire').select_related(
            'gare_origine', 'gare_destination', 'retirant', 'guichetier_retrait'
        )
        if not user.has_global_access and user.gare_id:
            queryset = queryset.filter(gare_destination_id=user.gare_id)
        return queryset.order_by('-date_retrait')


@require_http_methods(["GET"])
@login_required
def retrait_recherche_ajax(request):
    """
    Recherche en direct (sans clic sur le bouton) sur l'écran de retrait —
    pendant la saisie, voir retrait.html. Retourne le même partial que
    RetraitColisView.get() pour rester identique en tout point à un
    rechargement classique.
    """
    query = request.GET.get('q', '').strip()
    colis, erreur = _rechercher_colis_retrait(request.user, query)
    return render(request, 'courrier/partials/retrait_resultat.html', {
        'query': query,
        'colis': colis,
        'erreur_recherche': erreur,
        'form': _form_retrait_pour(colis),
    })


# ==================== CATALOGUE TYPES DE COLIS ====================

class TypeColisListView(LoginRequiredMixin, ListView):
    model = TypeColis
    template_name = 'courrier/type_colis_list.html'
    context_object_name = 'types_colis'

    def get_queryset(self):
        return super().get_queryset().order_by('ordre', 'nom')


class TypeColisCreateView(AdminRequiredMixin, CreateView):
    model = TypeColis
    form_class = TypeColisForm
    template_name = 'courrier/type_colis_form.html'
    success_url = reverse_lazy('courrier:type_colis_list')

    def form_valid(self, form):
        from apps.compagnie.models import Compagnie
        form.instance.compagnie = Compagnie.get_instance()
        messages.success(self.request, 'Type de colis créé avec succès.')
        return super().form_valid(form)


class TypeColisUpdateView(AdminRequiredMixin, UpdateView):
    model = TypeColis
    form_class = TypeColisForm
    template_name = 'courrier/type_colis_form.html'
    success_url = reverse_lazy('courrier:type_colis_list')

    def form_valid(self, form):
        messages.success(self.request, 'Type de colis modifié avec succès.')
        return super().form_valid(form)


class TypeColisDeleteView(AdminRequiredMixin, DeleteView):
    model = TypeColis
    template_name = 'courrier/type_colis_confirm_delete.html'
    success_url = reverse_lazy('courrier:type_colis_list')

    def dispatch(self, request, *args, **kwargs):
        type_colis = get_object_or_404(TypeColis, pk=kwargs['pk'])
        if not type_colis.peut_etre_supprime():
            messages.error(request, "Ce type est utilisé par des colis existants et ne peut pas être supprimé.")
            return redirect('courrier:type_colis_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Type de colis supprimé avec succès.')
        return super().form_valid(form)
