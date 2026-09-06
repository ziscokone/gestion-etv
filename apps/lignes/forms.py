from django import forms
from .models import Ligne
from apps.gares.models import Gare


class LigneForm(forms.ModelForm):
    """Formulaire pour créer et modifier une ligne."""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les gares pour les utilisateurs non-global
        if self.user and not self.user.has_global_access:
            if self.user.gare:
                self.fields['gare'].queryset = Gare.objects.filter(pk=self.user.gare.pk)
                self.fields['gare'].initial = self.user.gare
            else:
                self.fields['gare'].queryset = Gare.objects.none()
        else:
            self.fields['gare'].queryset = Gare.objects.filter(active=True)

    class Meta:
        model = Ligne
        fields = ['gare', 'nom', 'ville_depart', 'ville_arrivee', 'distance_km', 'duree_estimee', 'active']
        widgets = {
            'gare': forms.Select(attrs={
                'class': 'form-select'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Conakry - Kankan'
            }),
            'ville_depart': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Conakry'
            }),
            'ville_arrivee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Kankan'
            }),
            'distance_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Distance en km (optionnel)'
            }),
            'duree_estimee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM:SS (optionnel)'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'gare': 'Gare de départ',
            'nom': 'Nom de la ligne',
            'ville_depart': 'Ville de départ',
            'ville_arrivee': 'Ville d\'arrivée',
            'distance_km': 'Distance (km)',
            'duree_estimee': 'Durée estimée',
            'active': 'Ligne active',
        }
        help_texts = {
            'gare': 'La gare depuis laquelle cette ligne part',
        }
