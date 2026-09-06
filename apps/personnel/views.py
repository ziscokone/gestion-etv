from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.views import View
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, Http404
import os
from core.mixins import AdminRequiredMixin
from core.utils import render_paginated_partial
from .models import Utilisateur, Chauffeur, Convoyeur, Module, DocumentChauffeur, TypeDocumentChauffeur
from .forms import UtilisateurForm, ChauffeurForm, ConvoyeurForm
from apps.compagnie.models import Compagnie
import json
from datetime import date


# Vues pour les utilisateurs
def _utilisateurs_base_queryset(user):
    queryset = Utilisateur.objects.all()
    if not user.has_global_access:
        queryset = queryset.filter(gare=user.gare) if user.gare else queryset.none()
    return queryset


def _utilisateurs_filtres(user, search, role):
    queryset = _utilisateurs_base_queryset(user)
    if search:
        queryset = queryset.filter(
            Q(nom_complet__icontains=search) |
            Q(username__icontains=search) |
            Q(telephone__icontains=search)
        )
    if role and role != 'tous':
        queryset = queryset.filter(role=role)
    return queryset.select_related('gare').order_by('nom_complet')


def _peut_voir_utilisateurs(user):
    """Accès global ou chef de gare — un guichetier n'a pas à consulter l'annuaire du personnel."""
    return user.has_global_access or user.is_chef_gare


class UtilisateurListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Liste des utilisateurs.
    Réservée aux rôles de gestion (accès global ou chef de gare) : un guichetier
    n'a pas à consulter l'annuaire du personnel. Un chef de gare ne voit que le
    personnel de sa propre gare.
    """
    model = Utilisateur
    template_name = 'personnel/utilisateur_list.html'
    context_object_name = 'utilisateurs'

    def test_func(self):
        return _peut_voir_utilisateurs(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Vous n'avez pas les droits nécessaires pour accéder à cette page.")
        return super().handle_no_permission()

    def get_queryset(self):
        return _utilisateurs_filtres(self.request.user, self.request.GET.get('q'), self.request.GET.get('role', 'tous'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = _utilisateurs_base_queryset(self.request.user)
        context['search_query'] = self.request.GET.get('q', '')
        context['role_filtre']  = self.request.GET.get('role', 'tous')
        context['nb_total']     = base_qs.count()
        context['nb_actifs']    = base_qs.filter(actif=True).count()
        context['nb_inactifs']  = base_qs.filter(actif=False).count()
        return context


@require_http_methods(["GET"])
@login_required
def utilisateur_list_ajax(request):
    """Filtrage en direct de la liste des utilisateurs — même contrôle d'accès que UtilisateurListView."""
    if not _peut_voir_utilisateurs(request.user):
        return HttpResponseForbidden()
    queryset = _utilisateurs_filtres(request.user, request.GET.get('q'), request.GET.get('role', 'tous'))
    return render(request, 'personnel/partials/utilisateur_table.html', {
        'utilisateurs': queryset,
        'search_query': request.GET.get('q', ''),
        'role_filtre': request.GET.get('role', 'tous'),
    })


class UtilisateurCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouvel utilisateur."""
    model = Utilisateur
    form_class = UtilisateurForm
    template_name = 'personnel/utilisateur_form.html'
    success_url = reverse_lazy('personnel:utilisateur_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Utilisateur créé avec succès.')
        return super().form_valid(form)


class UtilisateurUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un utilisateur."""
    model = Utilisateur
    form_class = UtilisateurForm
    template_name = 'personnel/utilisateur_form.html'
    success_url = reverse_lazy('personnel:utilisateur_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Utilisateur modifié avec succès.')
        return super().form_valid(form)


class UtilisateurDeleteView(AdminRequiredMixin, DeleteView):
    """Supprimer un utilisateur — réservé au super_admin uniquement."""
    model = Utilisateur
    template_name = 'personnel/utilisateur_confirm_delete.html'
    success_url = reverse_lazy('personnel:utilisateur_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role == 'super_admin'):
            messages.error(request, "Seul le super administrateur peut supprimer un utilisateur.")
            return redirect('personnel:utilisateur_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Utilisateur supprimé avec succès.')
        return super().form_valid(form)


class ModulesUtilisateurView(LoginRequiredMixin, View):
    """Gestion des modules autorisés pour un utilisateur. Réservé au super_admin."""

    def _check_permission(self, request):
        if not (request.user.is_superuser or request.user.role == 'super_admin'):
            raise PermissionDenied

    def get(self, request, pk):
        self._check_permission(request)
        cible = get_object_or_404(Utilisateur, pk=pk)
        tous_modules = Module.objects.filter(actif=True).order_by('ordre')
        modules_actifs = set(cible.modules_autorises.values_list('pk', flat=True))
        return render(request, 'personnel/utilisateur_modules.html', {
            'cible': cible,
            'tous_modules': tous_modules,
            'modules_actifs': modules_actifs,
        })

    def post(self, request, pk):
        self._check_permission(request)
        cible = get_object_or_404(Utilisateur, pk=pk)
        selected_ids = request.POST.getlist('modules')
        cible.modules_autorises.set(Module.objects.filter(pk__in=selected_ids))
        messages.success(request, f'Accès aux modules mis à jour pour {cible.nom_complet}.')
        return redirect('personnel:utilisateur_list')


# Vues pour les chauffeurs
def _chauffeurs_filtres(search, statut):
    from django.db.models import Count
    queryset = Chauffeur.objects.annotate(nb_voyages=Count('voyages'))
    if search:
        queryset = queryset.filter(
            Q(nom_complet__icontains=search) |
            Q(numero_permis__icontains=search) |
            Q(telephone__icontains=search)
        )
    if statut == 'actifs':
        queryset = queryset.filter(actif=True)
    elif statut == 'inactifs':
        queryset = queryset.filter(actif=False)
    return queryset.order_by('nom_complet')


class ChauffeurListView(LoginRequiredMixin, ListView):
    """Liste des chauffeurs."""
    model = Chauffeur
    template_name = 'personnel/chauffeur_list.html'
    context_object_name = 'chauffeurs'
    paginate_by = 15

    def get_queryset(self):
        return _chauffeurs_filtres(self.request.GET.get('q'), self.request.GET.get('statut', 'tous'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['statut_filtre'] = self.request.GET.get('statut', 'tous')
        context['nb_total']    = Chauffeur.objects.count()
        context['nb_actifs']   = Chauffeur.objects.filter(actif=True).count()
        context['nb_inactifs'] = Chauffeur.objects.filter(actif=False).count()
        context['nb_resultats_filtres'] = context['paginator'].count
        return context


@require_http_methods(["GET"])
@login_required
def chauffeur_list_ajax(request):
    """Filtrage en direct de la liste des chauffeurs (recherche automatique)."""
    queryset = _chauffeurs_filtres(request.GET.get('q'), request.GET.get('statut', 'tous'))
    return render_paginated_partial(
        request, queryset, 'personnel/partials/chauffeur_table.html',
        list_context_name='chauffeurs', page_size=15, total_context_name='nb_resultats_filtres',
        extra_context={'search_query': request.GET.get('q', ''), 'statut_filtre': request.GET.get('statut', 'tous')},
    )


class ChauffeurCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouveau chauffeur."""
    model = Chauffeur
    form_class = ChauffeurForm
    template_name = 'personnel/chauffeur_form.html'
    success_url = reverse_lazy('personnel:chauffeur_list')

    def form_valid(self, form):
        form.instance.compagnie = Compagnie.get_instance()
        messages.success(self.request, 'Chauffeur créé avec succès.')
        return super().form_valid(form)


class ChauffeurUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un chauffeur."""
    model = Chauffeur
    form_class = ChauffeurForm
    template_name = 'personnel/chauffeur_form.html'
    success_url = reverse_lazy('personnel:chauffeur_list')

    def form_valid(self, form):
        messages.success(self.request, 'Chauffeur modifié avec succès.')
        return super().form_valid(form)


class ChauffeurDeleteView(AdminRequiredMixin, DeleteView):
    """Supprimer un chauffeur."""
    model = Chauffeur
    template_name = 'personnel/chauffeur_confirm_delete.html'
    success_url = reverse_lazy('personnel:chauffeur_list')

    def form_valid(self, form):
        messages.success(self.request, 'Chauffeur supprimé avec succès.')
        return super().form_valid(form)


class ChauffeurDetailView(LoginRequiredMixin, DetailView):
    """Fiche détail d'un chauffeur avec son activité voyages."""
    model = Chauffeur
    template_name = 'personnel/chauffeur_detail.html'
    context_object_name = 'chauffeur'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chauffeur = self.object
        today = date.today()

        # Filtres période (défaut : année en cours)
        date_debut = self.request.GET.get('date_debut') or date(today.year, 1, 1).strftime('%Y-%m-%d')
        date_fin   = self.request.GET.get('date_fin')   or today.strftime('%Y-%m-%d')
        context['date_debut'] = date_debut
        context['date_fin']   = date_fin

        # Tous les voyages du chauffeur
        tous_voyages = chauffeur.voyages.all()

        # Voyages sur la période filtrée
        voyages_periode = tous_voyages.filter(
            date_depart__gte=date_debut,
            date_depart__lte=date_fin
        ).select_related('gare', 'ligne', 'vehicule').order_by('-date_depart', '-heure_depart')

        context['nb_voyages_periode'] = voyages_periode.count()
        context['nb_total']           = tous_voyages.count()
        context['nb_termines']        = voyages_periode.filter(statut='termine').count()
        context['nb_annules']         = voyages_periode.filter(statut='annule').count()

        from django.core.paginator import Paginator
        paginator = Paginator(voyages_periode, 10)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))
        context['voyages']       = page_obj
        context['page_obj']      = page_obj
        context['is_paginated']  = page_obj.has_other_pages()

        # Voyages ce mois
        debut_mois = today.replace(day=1)
        context['nb_ce_mois'] = tous_voyages.filter(date_depart__gte=debut_mois).count()

        # Dernier voyage
        context['dernier_voyage'] = tous_voyages.order_by('-date_depart').first()

        # Graphique : voyages par mois sur les 12 derniers mois
        mois_labels = []
        mois_data   = []
        for i in range(11, -1, -1):
            month = today.month - i
            year  = today.year
            while month <= 0:
                month += 12
                year  -= 1
            debut = date(year, month, 1)
            fin   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            count = tous_voyages.filter(date_depart__gte=debut, date_depart__lt=fin).count()
            mois_labels.append(debut.strftime('%b %Y'))
            mois_data.append(count)

        context['chart_labels_json'] = json.dumps(mois_labels)
        context['chart_data_json']   = json.dumps(mois_data)
        context['documents'] = chauffeur.documents.select_related('type_document').all()
        context['types_document'] = TypeDocumentChauffeur.objects.filter(actif=True)
        return context


def upload_document_chauffeur(request, chauffeur_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    try:
        chauffeur = get_object_or_404(Chauffeur, pk=chauffeur_id)
        fichier = request.FILES.get('fichier')
        type_doc_id = request.POST.get('type_document')
        nom = request.POST.get('nom', '').strip()
        date_expiration = request.POST.get('date_expiration') or None

        if not fichier:
            return JsonResponse({'success': False, 'error': 'Aucun fichier fourni'}, status=400)
        if not type_doc_id:
            return JsonResponse({'success': False, 'error': 'Type de document requis'}, status=400)

        type_doc = get_object_or_404(TypeDocumentChauffeur, pk=type_doc_id, actif=True)

        ext = os.path.splitext(fichier.name)[1].lower()
        if ext not in ['.pdf', '.jpg', '.jpeg', '.png']:
            return JsonResponse({'success': False, 'error': 'Format non accepté (PDF, JPG, PNG uniquement)'}, status=400)

        if fichier.size > 10 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'Fichier trop volumineux (max 10 Mo)'}, status=400)

        DocumentChauffeur.objects.create(
            chauffeur=chauffeur,
            type_document=type_doc,
            nom=nom or fichier.name,
            fichier=fichier,
            date_expiration=date_expiration if date_expiration else None,
            ajoute_par=request.user,
        )

        return JsonResponse({'success': True})

    except Exception:
        return JsonResponse({'success': False, 'error': 'Une erreur est survenue.'}, status=500)


def telecharger_document_chauffeur(request, doc_id):
    if not request.user.is_authenticated:
        raise Http404
    doc = get_object_or_404(DocumentChauffeur, pk=doc_id)
    if not doc.fichier:
        raise Http404
    try:
        response = FileResponse(doc.fichier.open('rb'), as_attachment=True, filename=os.path.basename(doc.fichier.name))
        return response
    except FileNotFoundError:
        raise Http404


def supprimer_document_chauffeur(request, doc_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Action réservée au super administrateur'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    doc = get_object_or_404(DocumentChauffeur, pk=doc_id)
    chauffeur_id = doc.chauffeur_id
    # Supprimer le fichier physique
    if doc.fichier and os.path.isfile(doc.fichier.path):
        os.remove(doc.fichier.path)
    doc.delete()
    return JsonResponse({'success': True, 'chauffeur_id': chauffeur_id})


# Vues pour les types de document chauffeur
def _types_document_filtres(search):
    queryset = TypeDocumentChauffeur.objects.all()
    if search:
        queryset = queryset.filter(nom__icontains=search)
    return queryset.order_by('nom')


class TypeDocumentChauffeurListView(LoginRequiredMixin, ListView):
    model = TypeDocumentChauffeur
    template_name = 'personnel/type_document_list.html'
    context_object_name = 'types_document'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé au super administrateur.")
            return redirect('personnel:chauffeur_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return _types_document_filtres(self.request.GET.get('q'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


@require_http_methods(["GET"])
@login_required
def type_document_list_ajax(request):
    """Filtrage en direct des types de document chauffeur — réservé au super administrateur."""
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    queryset = _types_document_filtres(request.GET.get('q'))
    return render(request, 'personnel/partials/type_document_table.html', {'types_document': queryset})


class TypeDocumentChauffeurCreateView(LoginRequiredMixin, CreateView):
    model = TypeDocumentChauffeur
    fields = ['nom', 'actif']
    template_name = 'personnel/type_document_form.html'
    success_url = reverse_lazy('personnel:type_document_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé au super administrateur.")
            return redirect('personnel:chauffeur_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Type de document créé avec succès.')
        return super().form_valid(form)


class TypeDocumentChauffeurUpdateView(LoginRequiredMixin, UpdateView):
    model = TypeDocumentChauffeur
    fields = ['nom', 'actif']
    template_name = 'personnel/type_document_form.html'
    success_url = reverse_lazy('personnel:type_document_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé au super administrateur.")
            return redirect('personnel:chauffeur_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Type de document modifié avec succès.')
        return super().form_valid(form)


class TypeDocumentChauffeurDeleteView(LoginRequiredMixin, DeleteView):
    model = TypeDocumentChauffeur
    template_name = 'personnel/type_document_confirm_delete.html'
    success_url = reverse_lazy('personnel:type_document_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé au super administrateur.")
            return redirect('personnel:chauffeur_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Type de document supprimé.')
        return super().form_valid(form)


# Vues pour les convoyeurs
def _convoyeurs_filtres(search):
    queryset = Convoyeur.objects.all()
    if search:
        queryset = queryset.filter(
            Q(nom_complet__icontains=search) |
            Q(telephone__icontains=search)
        )
    return queryset.order_by('nom_complet')


class ConvoyeurListView(LoginRequiredMixin, ListView):
    """Liste des convoyeurs."""
    model = Convoyeur
    template_name = 'personnel/convoyeur_list.html'
    context_object_name = 'convoyeurs'

    def get_queryset(self):
        return _convoyeurs_filtres(self.request.GET.get('q'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


@require_http_methods(["GET"])
@login_required
def convoyeur_list_ajax(request):
    """Filtrage en direct de la liste des convoyeurs (recherche automatique)."""
    queryset = _convoyeurs_filtres(request.GET.get('q'))
    return render(request, 'personnel/partials/convoyeur_table.html', {
        'convoyeurs': queryset,
        'search_query': request.GET.get('q', ''),
    })


class ConvoyeurCreateView(AdminRequiredMixin, CreateView):
    """Créer un nouveau convoyeur."""
    model = Convoyeur
    form_class = ConvoyeurForm
    template_name = 'personnel/convoyeur_form.html'
    success_url = reverse_lazy('personnel:convoyeur_list')

    def form_valid(self, form):
        form.instance.compagnie = Compagnie.get_instance()
        messages.success(self.request, 'Convoyeur créé avec succès.')
        return super().form_valid(form)


class ConvoyeurUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier un convoyeur."""
    model = Convoyeur
    form_class = ConvoyeurForm
    template_name = 'personnel/convoyeur_form.html'
    success_url = reverse_lazy('personnel:convoyeur_list')

    def form_valid(self, form):
        messages.success(self.request, 'Convoyeur modifié avec succès.')
        return super().form_valid(form)


class ConvoyeurDeleteView(AdminRequiredMixin, DeleteView):
    """Supprimer un convoyeur."""
    model = Convoyeur
    template_name = 'personnel/convoyeur_confirm_delete.html'
    success_url = reverse_lazy('personnel:convoyeur_list')

    def form_valid(self, form):
        messages.success(self.request, 'Convoyeur supprimé avec succès.')
        return super().form_valid(form)
