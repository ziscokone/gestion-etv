from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from core.mixins import SuperAdminRequiredMixin
from .forms import CompagnieForm
from .models import Compagnie


class CompagnieConfigView(SuperAdminRequiredMixin, UpdateView):
    """
    Configuration de la compagnie (logo, contact, souche, message de ticket).
    Réservée strictement au rôle super_admin — pas au PDG, pas au manager.
    """
    model = Compagnie
    form_class = CompagnieForm
    template_name = 'compagnie/parametres.html'
    success_url = reverse_lazy('compagnie:parametres')

    def get_object(self, queryset=None):
        instance = Compagnie.get_instance()
        if instance is None:
            instance = Compagnie.objects.create(nom='', nom_pdg='')
        return instance

    def form_valid(self, form):
        messages.success(self.request, 'Paramètres de la compagnie enregistrés avec succès.')
        return super().form_valid(form)
