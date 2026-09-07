from django import forms

from .models import Compagnie

DOCUMENTS_CLES = [cle for cle, _, _ in Compagnie.DOCUMENTS_VEHICULE]


class CompagnieForm(forms.ModelForm):
    """Formulaire de configuration de la compagnie (réservé au Super Admin)."""

    class Meta:
        model = Compagnie
        fields = [
            'nom', 'logo', 'nom_pdg',
            'adresse', 'telephone', 'email',
            'utiliser_souche', 'message_bas_ticket',
            'fidelite_active', 'fidelite_seuil_voyages',
        ] + [
            f'alerte_{cle}_{suffixe}'
            for cle in DOCUMENTS_CLES
            for suffixe in ('active', 'jours', 'urgent_jours')
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'nom_pdg': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'utiliser_souche': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'message_bas_ticket': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fidelite_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fidelite_seuil_voyages': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            **{
                f'alerte_{cle}_active': forms.CheckboxInput(attrs={
                    'class': 'form-check-input doc-alerte-toggle',
                    'data-doc': cle,
                })
                for cle in DOCUMENTS_CLES
            },
            **{
                f'alerte_{cle}_jours': forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm', 'min': '1',
                })
                for cle in DOCUMENTS_CLES
            },
            **{
                f'alerte_{cle}_urgent_jours': forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm', 'min': '1',
                })
                for cle in DOCUMENTS_CLES
            },
        }
        labels = {
            'nom': 'Nom de la compagnie',
            'nom_pdg': 'Nom du PDG',
            'utiliser_souche': 'Imprimer avec souche',
            'message_bas_ticket': 'Message bas de ticket',
            'fidelite_active': 'Activer le programme de fidélité',
            'fidelite_seuil_voyages': 'Voyages payés pour un voyage offert',
        }

    def clean_fidelite_seuil_voyages(self):
        seuil = self.cleaned_data.get('fidelite_seuil_voyages')
        if self.cleaned_data.get('fidelite_active') and (not seuil or seuil < 1):
            raise forms.ValidationError("Indiquez un nombre de voyages d'au moins 1 pour activer la fidélité.")
        return seuil

    def clean(self):
        cleaned_data = super().clean()
        for cle in DOCUMENTS_CLES:
            seuil_alerte = cleaned_data.get(f'alerte_{cle}_jours')
            seuil_urgent = cleaned_data.get(f'alerte_{cle}_urgent_jours')
            if seuil_alerte is not None and seuil_urgent is not None and seuil_urgent > seuil_alerte:
                self.add_error(
                    f'alerte_{cle}_urgent_jours',
                    "Le seuil urgent doit être inférieur ou égal au seuil d'alerte."
                )
        return cleaned_data
