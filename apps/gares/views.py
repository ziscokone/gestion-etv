from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect

from core.mixins import SuperAdminRequiredMixin
from .models import Gare
from .forms import GareForm, ImprimanteForm


class GestionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin pour restreindre l'accès aux admins et chefs de gare."""

    def test_func(self):
        return self.request.user.has_global_access or self.request.user.is_chef_gare


class GareListView(GestionRequiredMixin, ListView):
    """Liste des gares."""
    model = Gare
    template_name = 'gares/gare_list.html'
    context_object_name = 'gares'

    def get_queryset(self):
        user = self.request.user
        if user.has_global_access:
            return Gare.objects.all()
        return Gare.objects.filter(pk=user.gare.pk) if user.gare else Gare.objects.none()


class GareCreateView(GestionRequiredMixin, CreateView):
    """Créer une nouvelle gare."""
    model = Gare
    form_class = GareForm
    template_name = 'gares/gare_form.html'
    success_url = reverse_lazy('gares:gare_list')

    def test_func(self):
        return self.request.user.has_global_access

    def form_valid(self, form):
        messages.success(self.request, 'Gare créée avec succès.')
        return super().form_valid(form)


class GareUpdateView(GestionRequiredMixin, UpdateView):
    """Modifier une gare."""
    model = Gare
    form_class = GareForm
    template_name = 'gares/gare_form.html'
    success_url = reverse_lazy('gares:gare_list')

    def test_func(self):
        user = self.request.user
        if user.has_global_access:
            return True
        if user.is_chef_gare and user.gare:
            return self.get_object().pk == user.gare.pk
        return False

    def form_valid(self, form):
        messages.success(self.request, 'Gare modifiée avec succès.')
        return super().form_valid(form)


class GareDeleteView(SuperAdminRequiredMixin, DeleteView):
    """
    Désactive une gare (soft-delete).
    On ne supprime jamais physiquement une gare : elle peut être référencée
    par des voyages, destinations et billets passés. On la marque inactive.
    """
    model = Gare
    template_name = 'gares/gare_confirm_delete.html'
    success_url = reverse_lazy('gares:gare_list')

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.active = False
        self.object.save(update_fields=['active'])
        messages.success(self.request, 'Gare désactivée avec succès.')
        return HttpResponseRedirect(success_url)


class ImprimanteConfigView(GestionRequiredMixin, UpdateView):
    """
    Configuration de l'imprimante thermique ESC/POS de ce poste (nom Windows,
    largeur du ticket) — voir apps/guichet/impression.py. Chaque poste
    hors-ligne n'a qu'une seule gare locale (Gare.objects.first()), jamais
    recréée ici : elle doit venir de la synchronisation avec le central.
    """
    model = Gare
    form_class = ImprimanteForm
    template_name = 'gares/imprimante_config.html'
    success_url = reverse_lazy('gares:imprimante_config')

    def get_object(self, queryset=None):
        return Gare.objects.first()

    def _verifier_gare_existe(self, request):
        """None si une gare existe, sinon une redirection vers le statut de
        synchronisation. Appelé depuis get()/post() (pas dispatch()) pour que
        la vérification d'accès (GestionRequiredMixin) passe d'abord."""
        if self.get_object() is None:
            messages.error(
                request,
                "Aucune gare trouvée sur ce poste. Effectuez d'abord une "
                "synchronisation (sync_pull) avant de configurer l'imprimante."
            )
            return redirect('sync:statut')
        return None

    def get(self, request, *args, **kwargs):
        return self._verifier_gare_existe(request) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._verifier_gare_existe(request) or super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Configuration de l'imprimante enregistrée avec succès.")
        return super().form_valid(form)
