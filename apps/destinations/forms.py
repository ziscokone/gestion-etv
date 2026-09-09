from django import forms
from .models import Destination, cle_ville
from apps.lignes.models import Ligne
from apps.gares.models import Gare


class DestinationForm(forms.ModelForm):
    """Formulaire pour créer et modifier une destination."""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer uniquement les lignes actives
        self.fields['ligne'].queryset = Ligne.objects.filter(active=True)

        # Filtrer les gares pour les utilisateurs non-global
        if self.user and not self.user.has_global_access:
            if self.user.gare:
                self.fields['gare'].queryset = Gare.objects.filter(pk=self.user.gare.pk)
                self.fields['gare'].initial = self.user.gare
                self.fields['gare'].widget.attrs['readonly'] = True
            else:
                self.fields['gare'].queryset = Gare.objects.none()

    class Meta:
        model = Destination
        fields = ['ligne', 'gare', 'ville_arrivee', 'montant', 'active']
        widgets = {
            'ligne': forms.Select(attrs={
                'class': 'form-select',
            }),
            'gare': forms.Select(attrs={
                'class': 'form-select',
            }),
            'ville_arrivee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Kankan'
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 150000',
                'min': '0',
                'step': '100'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'ligne': 'Ligne',
            'gare': 'Gare de départ',
            'ville_arrivee': "Ville d'arrivée",
            'montant': 'Montant (FCFA)',
            'active': 'Destination active',
        }
        help_texts = {
            'montant': 'Prix du billet en Francs CFA',
            'active': 'Si désactivée, cette destination ne sera plus disponible à la vente',
        }

    def clean_ville_arrivee(self):
        """Normalise les espaces : « Bouaké  » et «  Bouaké » deviennent « Bouaké »."""
        ville = self.cleaned_data.get('ville_arrivee') or ''
        return ' '.join(ville.split())

    def clean(self):
        """Empêche les doublons sur la combinaison
        (ligne + gare de départ + ville d'arrivée + montant),
        sans tenir compte de la casse, des accents ni des espaces.
        """
        cleaned = super().clean()
        ligne = cleaned.get('ligne')
        gare = cleaned.get('gare')
        ville = cleaned.get('ville_arrivee')
        montant = cleaned.get('montant')

        if ligne and gare and ville and montant is not None:
            doublons = Destination.objects.filter(gare=gare, ligne=ligne, montant=montant)
            if self.instance and self.instance.pk:
                doublons = doublons.exclude(pk=self.instance.pk)
            cible = cle_ville(ville)
            if any(cle_ville(d.ville_arrivee) == cible for d in doublons):
                self.add_error('ville_arrivee', (
                    "Cette destination existe déjà : même ligne, même gare de départ, "
                    "même ville d'arrivée et même montant. L'écriture (majuscules, "
                    "accents, espaces) n'est pas prise en compte."
                ))
        return cleaned
