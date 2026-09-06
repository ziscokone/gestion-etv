from django import forms
from .models import ProgrammeDepart
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.vehicules.models import Vehicule


class ProgrammeDepartForm(forms.ModelForm):
    """Formulaire pour créer et modifier un programme de départ."""

    # Champs pour la sélection multiple des jours
    jours_lundi = forms.BooleanField(required=False, label='Lundi')
    jours_mardi = forms.BooleanField(required=False, label='Mardi')
    jours_mercredi = forms.BooleanField(required=False, label='Mercredi')
    jours_jeudi = forms.BooleanField(required=False, label='Jeudi')
    jours_vendredi = forms.BooleanField(required=False, label='Vendredi')
    jours_samedi = forms.BooleanField(required=False, label='Samedi')
    jours_dimanche = forms.BooleanField(required=False, label='Dimanche')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Exclure les véhicules en réparation (en_attente ou en_cours)
        self.fields['vehicule_defaut'].queryset = Vehicule.objects.filter(
            actif=True
        ).exclude(
            reparations__statut__in=['en_attente', 'en_cours']
        )

        # Filtrer les gares pour les utilisateurs non-global
        if self.user and not self.user.has_global_access:
            if self.user.gare:
                self.fields['gare'].queryset = Gare.objects.filter(pk=self.user.gare.pk)
                self.fields['gare'].initial = self.user.gare
                self.fields['gare'].widget.attrs['readonly'] = True
                # Filtrer les lignes pour n'afficher que celles de la gare de l'utilisateur
                self.fields['ligne'].queryset = Ligne.objects.filter(gare=self.user.gare)
            else:
                self.fields['gare'].queryset = Gare.objects.none()
                self.fields['ligne'].queryset = Ligne.objects.none()


        # Initialiser les champs de jours si l'instance existe
        if self.instance and self.instance.pk and self.instance.jours_actifs:
            jours_map = {
                'lun': 'jours_lundi',
                'mar': 'jours_mardi',
                'mer': 'jours_mercredi',
                'jeu': 'jours_jeudi',
                'ven': 'jours_vendredi',
                'sam': 'jours_samedi',
                'dim': 'jours_dimanche',
            }
            for jour_code, field_name in jours_map.items():
                if jour_code in self.instance.jours_actifs:
                    self.fields[field_name].initial = True

    class Meta:
        model = ProgrammeDepart
        fields = [
            'gare', 'ligne', 'periode', 'heure_depart',
            'numero_depart', 'vehicule_defaut', 'actif'
        ]
        widgets = {
            'gare': forms.Select(attrs={'class': 'form-select'}),
            'ligne': forms.Select(attrs={'class': 'form-select'}),
            'periode': forms.Select(attrs={'class': 'form-select'}),
            'heure_depart': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': 'HH:MM'
            }),
            'numero_depart': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '1, 2, 3...'
            }),
            'vehicule_defaut': forms.Select(attrs={
                'class': 'form-select searchable-select',
                'data-placeholder': "Rechercher un véhicule (n° d'ordre ou immatriculation)...",
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'gare': 'Gare de départ',
            'ligne': 'Ligne',
            'periode': 'Période',
            'heure_depart': 'Heure de départ',
            'numero_depart': 'Numéro de départ',
            'vehicule_defaut': 'Véhicule par défaut',
            'actif': 'Programme actif',
        }
        help_texts = {
            'numero_depart': 'Numéro séquentiel du départ (pour distinguer plusieurs départs à la même heure)',
            'vehicule_defaut': 'Le véhicule sera automatiquement assigné aux voyages créés',
            'actif': 'Désactiver temporairement ce programme sans le supprimer',
        }

    def clean(self):
        cleaned_data = super().clean()

        # Construire le tableau jours_actifs à partir des cases cochées
        jours_actifs = []
        jours_map = {
            'jours_lundi': 'lun',
            'jours_mardi': 'mar',
            'jours_mercredi': 'mer',
            'jours_jeudi': 'jeu',
            'jours_vendredi': 'ven',
            'jours_samedi': 'sam',
            'jours_dimanche': 'dim',
        }

        for field_name, jour_code in jours_map.items():
            if cleaned_data.get(field_name):
                jours_actifs.append(jour_code)

        if not jours_actifs:
            raise forms.ValidationError(
                'Vous devez sélectionner au moins un jour de la semaine.'
            )

        cleaned_data['jours_actifs'] = jours_actifs

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.jours_actifs = self.cleaned_data['jours_actifs']

        if commit:
            instance.save()

        return instance
