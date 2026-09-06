from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect

from core.mixins import SuperAdminRequiredMixin
from .models import Ligne
from .forms import LigneForm
from apps.compagnie.models import Compagnie


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin pour restreindre l'accès aux admins uniquement."""

    def test_func(self):
        return self.request.user.has_global_access


class LigneListView(LoginRequiredMixin, ListView):
    """Liste des lignes."""
    model = Ligne
    template_name = 'lignes/ligne_list.html'
    context_object_name = 'lignes'

    def get_queryset(self):
        return Ligne.objects.all().order_by('ville_depart', 'ville_arrivee')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['nb_actives'] = qs.filter(active=True).count()
        context['nb_inactives'] = qs.filter(active=False).count()
        return context


class LigneCreateView(AdminRequiredMixin, CreateView):
    """Créer une nouvelle ligne."""
    model = Ligne
    form_class = LigneForm
    template_name = 'lignes/ligne_form.html'
    success_url = reverse_lazy('lignes:ligne_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Assigner automatiquement la compagnie
        compagnie = Compagnie.get_instance()
        if not compagnie:
            messages.error(self.request, 'Aucune compagnie n\'est configurée. Veuillez d\'abord créer une compagnie.')
            return self.form_invalid(form)
        form.instance.compagnie = compagnie
        messages.success(self.request, 'Ligne créée avec succès.')
        return super().form_valid(form)


class LigneUpdateView(AdminRequiredMixin, UpdateView):
    """Modifier une ligne."""
    model = Ligne
    form_class = LigneForm
    template_name = 'lignes/ligne_form.html'
    success_url = reverse_lazy('lignes:ligne_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Ligne modifiée avec succès.')
        return super().form_valid(form)


class LigneDeleteView(SuperAdminRequiredMixin, DeleteView):
    """
    Désactive une ligne (soft-delete).
    On ne supprime jamais physiquement une ligne : elle peut être référencée
    par des destinations, voyages et billets passés. On la marque inactive.
    """
    model = Ligne
    template_name = 'lignes/ligne_confirm_delete.html'
    success_url = reverse_lazy('lignes:ligne_list')

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.active = False
        self.object.save(update_fields=['active'])
        messages.success(self.request, 'Ligne désactivée avec succès.')
        return HttpResponseRedirect(success_url)
