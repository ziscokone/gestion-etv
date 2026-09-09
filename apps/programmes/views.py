from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from core.mixins import GestionRequiredMixin
from .models import ProgrammeDepart
from .forms import ProgrammeDepartForm


def _programmes_filtres(user, search):
    queryset = ProgrammeDepart.objects.all()
    if not user.has_global_access and user.gare:
        queryset = queryset.filter(gare=user.gare)
    if search:
        queryset = queryset.filter(
            Q(ligne__nom__icontains=search) |
            Q(destination__ville_arrivee__icontains=search) |
            Q(gare__nom__icontains=search)
        )
    return queryset.select_related('gare', 'ligne', 'destination', 'vehicule_defaut').order_by('gare__code', 'heure_depart')


def _peut_gerer_programmes(user):
    """Même règle que core.mixins.GestionRequiredMixin."""
    return user.has_global_access or user.is_chef_gare or user.is_guichetier


class ProgrammeDepartListView(GestionRequiredMixin, ListView):
    """Liste des programmes de départ."""
    model = ProgrammeDepart
    template_name = 'programmes/programme_list.html'
    context_object_name = 'programmes'

    def get_queryset(self):
        return _programmes_filtres(self.request.user, self.request.GET.get('q'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        base = ProgrammeDepart.objects.all()
        if not self.request.user.has_global_access and self.request.user.gare:
            base = base.filter(gare=self.request.user.gare)
        context['nb_total'] = base.count()
        context['nb_actifs'] = base.filter(actif=True).count()
        context['nb_inactifs'] = base.filter(actif=False).count()
        return context


@require_http_methods(["GET"])
@login_required
def programme_list_ajax(request):
    """Filtrage en direct des programmes de départ — même contrôle d'accès que ProgrammeDepartListView."""
    if not _peut_gerer_programmes(request.user):
        return HttpResponseForbidden()
    queryset = _programmes_filtres(request.user, request.GET.get('q'))
    return render(request, 'programmes/partials/programme_table.html', {
        'programmes': queryset,
        'search_query': request.GET.get('q', ''),
    })


class ProgrammeDepartCreateView(GestionRequiredMixin, CreateView):
    """Créer un nouveau programme de départ."""
    model = ProgrammeDepart
    form_class = ProgrammeDepartForm
    template_name = 'programmes/programme_form.html'
    success_url = reverse_lazy('programmes:programme_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        # Créer automatiquement les voyages pour les 7 prochains jours
        voyages_crees = self.object.creer_voyages_semaine(jours_avance=7)
        messages.success(
            self.request,
            f'Programme de départ créé avec succès. {len(voyages_crees)} voyage(s) généré(s) automatiquement.'
        )
        return response


class ProgrammeDepartUpdateView(GestionRequiredMixin, UpdateView):
    """Modifier un programme de départ."""
    model = ProgrammeDepart
    form_class = ProgrammeDepartForm
    template_name = 'programmes/programme_form.html'
    success_url = reverse_lazy('programmes:programme_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filtrer par gare pour les chefs de gare et guichetiers
        if not user.has_global_access and user.gare:
            queryset = queryset.filter(gare=user.gare)

        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Programme de départ modifié avec succès.')
        return super().form_valid(form)


class ProgrammeDepartDeleteView(GestionRequiredMixin, DeleteView):
    """Supprimer un programme de départ."""
    model = ProgrammeDepart
    template_name = 'programmes/programme_confirm_delete.html'
    success_url = reverse_lazy('programmes:programme_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filtrer par gare pour les chefs de gare et guichetiers
        if not user.has_global_access and user.gare:
            queryset = queryset.filter(gare=user.gare)

        return queryset

    def form_valid(self, form):
        messages.success(self.request, 'Programme de départ supprimé avec succès.')
        return super().form_valid(form)


class GenererVoyagesView(GestionRequiredMixin, View):
    """Génère manuellement les voyages pour un programme."""

    def post(self, request, pk):
        programme = get_object_or_404(ProgrammeDepart, pk=pk)

        # Vérifier les permissions pour les utilisateurs de gare
        if not request.user.has_global_access and request.user.gare:
            if programme.gare != request.user.gare:
                messages.error(request, "Vous n'avez pas la permission de générer des voyages pour ce programme.")
                return redirect('programmes:programme_list')

        # Générer les voyages
        jours_avance = int(request.POST.get('jours_avance', 7))
        voyages_crees = programme.creer_voyages_semaine(jours_avance=jours_avance)

        if voyages_crees:
            messages.success(
                request,
                f'{len(voyages_crees)} voyage(s) généré(s) avec succès pour les {jours_avance} prochains jours.'
            )
        else:
            messages.info(
                request,
                'Aucun nouveau voyage à créer. Les voyages existent déjà ou le programme n\'est actif sur aucun jour.'
            )

        return redirect('programmes:programme_list')
