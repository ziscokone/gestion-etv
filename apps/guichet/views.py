from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from core.utils import render_paginated_partial

from apps.billets.models import Billet
from apps.clients.models import Client
from apps.destinations.models import Destination
from apps.voyages.models import Voyage
from apps.guichet import impression


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Dashboard principal du guichetier (module Voyages).
    Cette vue est aussi la page d'accueil du site ("/"), donc un utilisateur
    connecté qui n'a pas le module Voyages parmi ses modules autorisés est
    redirigé vers le hub des modules plutôt que de voir ce tableau de bord
    (qui expose des données métier : recettes, billets vendus, réservations).
    """
    template_name = 'guichet/dashboard.html'

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'super_admin':
            return True
        return user.modules_autorises.filter(cle='voyages', actif=True).exists()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('hub')
        return super().handle_no_permission()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        # Transition automatique : voyages dont la date est passée encore en "programme" → "en_cours"
        Voyage.objects.filter(statut='programme', date_depart__lte=today).update(statut='en_cours')

        # Filtrer les voyages selon les droits de l'utilisateur
        if user.has_global_access:
            voyages_today = Voyage.objects.filter(date_depart=today)
            billets_today = Billet.objects.filter(
                date_creation__date=today,
                statut='paye'
            )
        else:
            voyages_today = Voyage.objects.filter(
                date_depart=today,
                gare=user.gare
            )
            billets_today = Billet.objects.filter(
                date_creation__date=today,
                guichetier=user,
                statut='paye'
            )

        context['voyages_today'] = voyages_today.count()
        context['billets_vendus_today'] = billets_today.count()
        context['montant_today'] = sum(b.montant for b in billets_today)
        context['reservations_en_attente'] = Billet.objects.filter(
            statut='reserve',
            voyage__date_depart__gte=today
        ).count() if user.has_global_access else Billet.objects.filter(
            statut='reserve',
            voyage__gare=user.gare,
            voyage__date_depart__gte=today
        ).count()

        # Prochains voyages (filtrés par gare)
        prochains_voyages = Voyage.objects.filter(
            date_depart__gte=today,
            statut__in=['programme', 'en_cours']
        )
        if not user.has_global_access and user.gare:
            prochains_voyages = prochains_voyages.filter(gare=user.gare)
        context['prochains_voyages'] = prochains_voyages.annotate(
            recette_billets=Sum('billets__montant', filter=Q(billets__statut='paye'))
        ).order_by('date_depart', 'heure_depart')[:5]

        return context


def _voyages_guichet_filtres(user, get_params):
    """Queryset des voyages (module guichet) filtrée par statut/date/ligne/période et gare de l'utilisateur."""
    today = timezone.now().date()

    # Transition automatique : voyages du jour encore "programme" → "en_cours"
    Voyage.objects.filter(statut='programme', date_depart__lte=today).update(statut='en_cours')

    statut_filter = get_params.get('statut', 'actifs')
    if statut_filter == 'termine':
        statuts = ['termine']
    elif statut_filter == 'tous':
        statuts = ['programme', 'en_cours', 'termine']
    else:  # 'actifs' par défaut
        statuts = ['programme', 'en_cours']

    date_filter = get_params.get('date')
    if date_filter:
        queryset = Voyage.objects.filter(date_depart=date_filter, statut__in=statuts)
    else:
        queryset = Voyage.objects.filter(date_depart__gte=today, statut__in=statuts)

    if not user.has_global_access:
        queryset = queryset.filter(gare=user.gare)

    ligne_filter = get_params.get('ligne')
    periode_filter = get_params.get('periode')
    if ligne_filter:
        queryset = queryset.filter(ligne_id=ligne_filter)
    if periode_filter:
        queryset = queryset.filter(periode=periode_filter)

    return queryset.order_by('date_depart', 'heure_depart')


class VoyageListView(LoginRequiredMixin, ListView):
    """Liste des voyages disponibles."""
    model = Voyage
    template_name = 'guichet/voyage_list.html'
    context_object_name = 'voyages'
    paginate_by = 20

    def get_queryset(self):
        return _voyages_guichet_filtres(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Lignes disponibles pour le filtre
        if user.has_global_access:
            from apps.lignes.models import Ligne
            context['lignes'] = Ligne.objects.filter(active=True)
        else:
            context['lignes'] = user.gare.destinations.values_list(
                'ligne', flat=True
            ).distinct() if user.gare else []

        # Ajouter le filtre de statut actuel au contexte
        context['statut_filter'] = self.request.GET.get('statut', 'actifs')

        return context


@require_http_methods(["GET"])
@login_required
def voyage_list_ajax(request):
    """Filtrage en direct de la liste des voyages (recherche automatique)."""
    queryset = _voyages_guichet_filtres(request.user, request.GET)
    return render_paginated_partial(
        request, queryset, 'guichet/partials/voyage_table.html',
        list_context_name='voyages',
    )


class VenteView(LoginRequiredMixin, DetailView):
    """Interface de vente de billets pour un voyage."""
    model = Voyage
    template_name = 'guichet/vente.html'
    context_object_name = 'voyage'
    slug_field = 'public_id'
    slug_url_kwarg = 'public_id'

    def get_queryset(self):
        """Filtrer les voyages par gare pour les utilisateurs non-global."""
        queryset = super().get_queryset()
        user = self.request.user
        if not user.has_global_access and user.gare:
            queryset = queryset.filter(gare=user.gare)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voyage = self.object

        context['disposition_sieges'] = voyage.get_disposition_sieges_avec_statut()
        context['sieges_disponibles'] = voyage.get_sieges_disponibles()
        context['nb_disponibles'] = len(context['sieges_disponibles'])
        context['reservations'] = voyage.billets.filter(statut='reserve')

        # Récupérer les destinations disponibles pour cette ligne
        context['destinations'] = Destination.objects.filter(
            ligne=voyage.ligne,
            gare=voyage.gare,
            active=True
        ).order_by('montant')

        return context


@ratelimit(key='user', rate='60/m', method='POST', block=True)
@login_required
def creer_billet(request, voyage_id):
    """Crée un ou plusieurs billets."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

    voyage = get_object_or_404(Voyage, public_id=voyage_id)
    user = request.user

    # Vérifier les droits d'accès
    if not user.has_global_access and voyage.gare != user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'})

    if voyage.statut == 'termine':
        return JsonResponse({
            'success': False,
            'error': 'Ce voyage est terminé, impossible de vendre ou réserver un billet'
        })

    client_nom = request.POST.get('client_nom', '').strip()
    client_telephone = request.POST.get('client_telephone', '').strip()
    destination_id = request.POST.get('destination_id')
    mode_vente = request.POST.get('mode_vente', 'unitaire')
    payer = request.POST.get('payer', 'true') == 'true'
    moyen_paiement = request.POST.get('moyen_paiement', 'cash')

    if not client_nom or not client_telephone:
        return JsonResponse({
            'success': False,
            'error': 'Le nom et le téléphone du client sont obligatoires'
        })

    # Récupérer la destination (obligatoire)
    if not destination_id:
        return JsonResponse({
            'success': False,
            'error': 'La destination est obligatoire'
        })

    try:
        destination = Destination.objects.get(pk=destination_id, ligne=voyage.ligne)
    except Destination.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Destination invalide'
        })

    # La fiche client doit exister AVANT de créer les billets : le programme
    # de fidélité a besoin de l'historique du client. La catégorie (particulier
    # / société) n'est appliquée qu'à la création, jamais réécrasée ensuite
    # (elle se modifie depuis la fiche client).
    categorie = request.POST.get('client_categorie')
    if categorie not in ('particulier', 'societe'):
        categorie = 'particulier'
    client_obj, _ = Client.objects.get_or_create(
        telephone=client_telephone,
        defaults={'nom_complet': client_nom, 'categorie': categorie}
    )

    # Liste ordonnée des sièges à vendre (unitaire = 1 siège, plage = intervalle).
    try:
        if mode_vente == 'plage':
            siege_debut = int(request.POST.get('siege_debut', 0))
            siege_fin = int(request.POST.get('siege_fin', 0))
            if not siege_debut or not siege_fin:
                return JsonResponse({'success': False, 'error': 'Plage de sièges non spécifiée'})
            if siege_debut > siege_fin:
                siege_debut, siege_fin = siege_fin, siege_debut
            sieges = list(range(siege_debut, siege_fin + 1))
        else:
            numero_siege = int(request.POST.get('numero_siege', 0))
            if not numero_siege:
                return JsonResponse({'success': False, 'error': 'Numéro de siège non spécifié'})
            sieges = [numero_siege]
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Sièges invalides'})

    try:
        if payer:
            # Vente payée → applique automatiquement le programme de fidélité :
            # les billets tombant sur un palier sortent à 0 FCFA (statut 'fidelite').
            billets_crees = Billet.creer_billets_avec_fidelite(
                voyage=voyage,
                client=client_obj,
                client_nom=client_nom,
                client_telephone=client_telephone,
                sieges=sieges,
                guichetier=user,
                destination=destination,
                moyen_paiement=moyen_paiement,
            )
        else:
            # Réservation non payée → pas de fidélité (elle se déclenchera au paiement).
            billets_crees = []
            for numero_siege in sieges:
                try:
                    billets_crees.append(Billet.creer_billet(
                        voyage=voyage,
                        client_nom=client_nom,
                        client_telephone=client_telephone,
                        numero_siege=numero_siege,
                        guichetier=user,
                        destination=destination,
                        payer=False,
                        moyen_paiement=moyen_paiement,
                    ))
                except ValidationError:
                    continue  # siège déjà pris entre-temps

        if not billets_crees:
            return JsonResponse({
                'success': False,
                'error': 'Aucun billet créé. Les sièges sont peut-être déjà pris.'
            })

        # Lier au client les billets qui ne le sont pas encore (branche réservation).
        Billet.objects.filter(
            pk__in=[b.pk for b in billets_crees], client__isnull=True
        ).update(client=client_obj)

        billets_data = [billet.get_info_impression() for billet in billets_crees]
        nb_offerts = sum(1 for b in billets_crees if b.statut == 'fidelite')
        message = f'{len(billets_crees)} billet(s) créé(s)'
        if nb_offerts:
            message += f" — dont {nb_offerts} offert(s) (fidélité)"

        return JsonResponse({
            'success': True,
            'message': message,
            'nb_offerts': nb_offerts,
            'billets': billets_data,
        })

    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Une erreur est survenue. Veuillez réessayer.'
        }, status=500)


@ratelimit(key='user', rate='60/m', method='POST', block=True)
@login_required
def payer_reservation(request, billet_id):
    """Convertit une réservation en paiement."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    billet = get_object_or_404(Billet, public_id=billet_id)
    user = request.user

    # Vérifier les droits d'accès
    if not user.has_global_access and billet.voyage.gare != user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)

    if billet.statut == 'paye':
        return JsonResponse({
            'success': False,
            'error': 'Ce billet est déjà payé'
        })

    if billet.voyage.statut == 'termine':
        return JsonResponse({
            'success': False,
            'error': 'Ce voyage est terminé, impossible de payer cette réservation'
        })

    # Récupérer le moyen de paiement (par défaut cash)
    moyen_paiement = request.POST.get('moyen_paiement', 'cash')
    billet.payer(moyen_paiement=moyen_paiement)

    return JsonResponse({
        'success': True,
        'message': 'Paiement enregistré',
        'billet': billet.get_info_impression()
    })


@login_required
def vendre_a_autre_client(request, billet_id):
    """Réassigne une réservation à un autre client et la marque comme payée."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

    billet = get_object_or_404(Billet, public_id=billet_id)
    user = request.user

    if not user.has_global_access and billet.voyage.gare != user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'})

    if billet.statut == 'paye':
        return JsonResponse({'success': False, 'error': 'Ce billet est déjà payé'})

    if billet.voyage.statut == 'termine':
        return JsonResponse({
            'success': False,
            'error': 'Ce voyage est terminé, impossible de vendre ce billet'
        })

    client_nom = request.POST.get('client_nom', '').strip()
    client_telephone = request.POST.get('client_telephone', '').strip()
    destination_id = request.POST.get('destination_id')
    moyen_paiement = request.POST.get('moyen_paiement', 'cash')

    if not client_nom or not client_telephone:
        return JsonResponse({'success': False, 'error': 'Le nom et le téléphone sont obligatoires'})

    if not destination_id:
        return JsonResponse({'success': False, 'error': 'La destination est obligatoire'})

    try:
        destination = Destination.objects.get(pk=destination_id, ligne=billet.voyage.ligne)
    except Destination.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Destination invalide'})

    # Mettre à jour le billet en place
    billet.client_nom = client_nom
    billet.client_telephone = client_telephone
    billet.destination = destination
    billet.montant = destination.montant
    billet.statut = 'paye'
    billet.moyen_paiement = moyen_paiement
    billet.date_paiement = timezone.now()
    billet.guichetier = user
    billet.save(update_fields=[
        'client_nom', 'client_telephone', 'destination', 'montant',
        'statut', 'moyen_paiement', 'date_paiement', 'guichetier', 'date_modification'
    ])

    # Associer ou créer la fiche client
    client_obj, _ = Client.objects.get_or_create(
        telephone=client_telephone,
        defaults={'nom_complet': client_nom}
    )
    billet.client = client_obj
    billet.save(update_fields=['client'])

    return JsonResponse({
        'success': True,
        'message': 'Billet vendu au nouveau client',
        'billet': billet.get_info_impression()
    })


@login_required
def get_sieges_status(request, voyage_id):
    """Retourne le statut actuel des sièges (pour mise à jour AJAX)."""
    voyage = get_object_or_404(Voyage, public_id=voyage_id)

    if not request.user.has_global_access and voyage.gare != request.user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)

    disposition = voyage.get_disposition_sieges_avec_statut()

    return JsonResponse({
        'success': True,
        'disposition': disposition,
        'stats': {
            'disponibles': voyage.get_nb_places_disponibles(),
            'reserves': voyage.get_nb_places_reservees(),
            'payes': voyage.get_nb_places_vendues()
        }
    })


def _reservations_filtrees(user, search):
    """Queryset des réservations en attente, filtrée par gare et recherche libre."""
    today = timezone.now().date()
    queryset = Billet.objects.filter(statut='reserve', voyage__date_depart__gte=today)
    if not user.has_global_access:
        queryset = queryset.filter(voyage__gare=user.gare)
    if search:
        queryset = queryset.filter(
            Q(client_nom__icontains=search) |
            Q(client_telephone__icontains=search) |
            Q(numero__icontains=search)
        )
    return queryset.order_by('voyage__date_depart', 'voyage__heure_depart')


class ReservationsListView(LoginRequiredMixin, ListView):
    """Liste des réservations en attente de paiement."""
    model = Billet
    template_name = 'guichet/reservations.html'
    context_object_name = 'reservations'
    paginate_by = 20

    def get_queryset(self):
        return _reservations_filtrees(self.request.user, self.request.GET.get('search'))


@require_http_methods(["GET"])
@login_required
def reservations_ajax(request):
    """Filtrage en direct des réservations en attente (recherche automatique)."""
    queryset = _reservations_filtrees(request.user, request.GET.get('search'))
    return render_paginated_partial(
        request, queryset, 'guichet/partials/reservations_table.html',
        list_context_name='reservations',
    )


@login_required
def get_billet_info(request, billet_id):
    """Retourne les informations d'un billet pour réimpression."""
    billet = get_object_or_404(Billet, public_id=billet_id)
    user = request.user

    # Vérifier les droits d'accès
    if not user.has_global_access and billet.voyage.gare != user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'})

    return JsonResponse({
        'success': True,
        'billet': billet.get_info_impression()
    })


@ratelimit(key='user', rate='60/m', method='POST', block=True)
@login_required
def imprimer_billets(request):
    """
    Imprime physiquement un ou plusieurs billets sur l'imprimante thermique
    du poste, à partir de leurs public_id. Les données d'impression sont
    re-dérivées côté serveur (jamais confiance dans un JSON envoyé par le
    client pour un document financier).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

    public_ids = request.POST.getlist('public_id')
    duplicata = request.POST.get('duplicata') == 'true'
    user = request.user

    if not public_ids:
        return JsonResponse({'success': False, 'error': 'Aucun billet à imprimer'})

    billets_par_id = {
        str(billet.public_id): billet
        for billet in Billet.objects.filter(public_id__in=public_ids)
    }

    billets = []
    for public_id in public_ids:
        billet = billets_par_id.get(public_id)
        if billet is None:
            return JsonResponse({'success': False, 'error': 'Billet introuvable'})
        if not user.has_global_access and billet.voyage.gare != user.gare:
            return JsonResponse({'success': False, 'error': 'Accès non autorisé'})
        billets.append(billet)

    try:
        billets_info = [billet.get_info_impression() for billet in billets]
        impression.imprimer_billets(billets_info, duplicata=duplicata)
    except impression.ErreurImpression as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Une erreur est survenue. Veuillez réessayer.'
        }, status=500)

    return JsonResponse({'success': True})


@login_required
def get_destinations_voyage(request, billet_id):
    """Retourne les destinations disponibles pour le voyage d'un billet."""
    billet = get_object_or_404(Billet, public_id=billet_id)
    user = request.user

    if not user.has_global_access and billet.voyage.gare != user.gare:
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'})

    destinations = Destination.objects.filter(
        ligne=billet.voyage.ligne,
        gare=billet.voyage.gare,
        active=True
    ).order_by('montant')

    return JsonResponse({
        'success': True,
        'destinations': [
            {'id': d.pk, 'ville': d.ville_arrivee, 'montant': str(d.montant)}
            for d in destinations
        ]
    })
