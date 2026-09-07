from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from core.mixins import SuperAdminRequiredMixin
from .forms import CompagnieForm, RemiseFormSet
from .models import Compagnie, Remise


class CompagnieConfigView(SuperAdminRequiredMixin, UpdateView):
    """
    Configuration de la compagnie (logo, contact, souche, message de ticket,
    fidélité, alertes véhicules) + la liste des remises pré-définies.
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

    def _remise_formset(self):
        kwargs = {'queryset': Remise.objects.all().order_by('ordre', 'montant'), 'prefix': 'remises'}
        if self.request.method == 'POST':
            return RemiseFormSet(self.request.POST, **kwargs)
        return RemiseFormSet(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('remise_formset', self._remise_formset())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = self._remise_formset()
        if form.is_valid() and formset.is_valid():
            return self.forms_valid(form, formset)
        return self.render_to_response(
            self.get_context_data(form=form, remise_formset=formset)
        )

    def forms_valid(self, form, formset):
        self.object = form.save()
        instances = formset.save(commit=False)
        for obj in instances:
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        messages.success(self.request, 'Paramètres de la compagnie enregistrés avec succès.')
        return super().form_valid(form)
