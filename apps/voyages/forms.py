from django import forms
from .models import Voyage
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.vehicules.models import Vehicule


class VoyageForm(forms.ModelForm):
    """Formulaire pour créer et modifier un voyage."""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Exclure les véhicules en réparation (en_attente ou en_cours)
        self.fields['vehicule'].queryset = Vehicule.objects.filter(
            actif=True
        ).exclude(
            reparations__statut__in=['en_attente', 'en_cours']
        )

        # Filtrer les gares et lignes pour les utilisateurs non-global
        if self.user and not self.user.has_global_access:
            if self.user.gare:
                # L'utilisateur ne voit que sa gare
                self.fields['gare'].queryset = Gare.objects.filter(pk=self.user.gare.pk)
                self.fields['gare'].initial = self.user.gare
                self.fields['gare'].widget.attrs['readonly'] = True

                # Filtrer les lignes par la gare de l'utilisateur
                self.fields['ligne'].queryset = Ligne.objects.filter(
                    gare=self.user.gare,
                    active=True
                )
            else:
                self.fields['gare'].queryset = Gare.objects.none()
                self.fields['ligne'].queryset = Ligne.objects.none()
        else:
            # Pour les utilisateurs globaux, filtrer les lignes actives
            self.fields['ligne'].queryset = Ligne.objects.filter(active=True)

        # Si on modifie un voyage existant, filtrer les lignes par la gare du voyage
        if self.instance and self.instance.pk and self.instance.gare:
            self.fields['ligne'].queryset = Ligne.objects.filter(
                gare=self.instance.gare,
                active=True
            )

    class Meta:
        model = Voyage
        fields = [
            'gare', 'ligne', 'date_depart', 'heure_depart',
            'periode', 'numero_depart', 'vehicule', 'chauffeur', 'convoyeur', 'statut'
        ]
        widgets = {
            'gare': forms.Select(attrs={'class': 'form-select'}),
            'ligne': forms.Select(attrs={'class': 'form-select'}),
            'date_depart': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'heure_depart': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': 'HH:MM'
            }),
            'periode': forms.Select(attrs={'class': 'form-select'}),
            'numero_depart': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '1, 2, 3...'
            }),
            'vehicule': forms.Select(attrs={
                'class': 'form-select searchable-select',
                'data-placeholder': "Rechercher un véhicule (n° d'ordre ou immatriculation)...",
            }),
            'chauffeur': forms.Select(attrs={'class': 'form-select'}),
            'convoyeur': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'gare': 'Gare de départ',
            'ligne': 'Ligne',
            'date_depart': 'Date de départ',
            'heure_depart': 'Heure de départ',
            'periode': 'Période',
            'numero_depart': 'Numéro de départ',
            'vehicule': 'Véhicule',
            'chauffeur': 'Chauffeur',
            'convoyeur': 'Convoyeur',
            'statut': 'Statut',
        }
        help_texts = {
            'chauffeur': 'Optionnel - peut être assigné plus tard',
            'convoyeur': 'Optionnel - peut être assigné plus tard',
            'numero_depart': 'Numéro séquentiel du départ pour identifier les voyages avec même horaire',
            'ligne': 'La ligne détermine la destination du voyage',
        }

    def clean(self):
        cleaned_data = super().clean()

        gare = cleaned_data.get('gare')
        ligne = cleaned_data.get('ligne')
        date_depart = cleaned_data.get('date_depart')
        heure_depart = cleaned_data.get('heure_depart')
        periode = cleaned_data.get('periode')
        numero_depart = cleaned_data.get('numero_depart')

        # Vérifier que la ligne appartient à la gare sélectionnée
        if gare and ligne:
            if ligne.gare and ligne.gare != gare:
                raise forms.ValidationError(
                    'La ligne sélectionnée n\'appartient pas à cette gare.'
                )

        # Vérifier l'unicité du numéro de départ par gare et date
        if gare and date_depart and numero_depart:
            numero_existant = Voyage.objects.filter(
                gare=gare,
                date_depart=date_depart,
                numero_depart=numero_depart
            )

            if self.instance and self.instance.pk:
                numero_existant = numero_existant.exclude(pk=self.instance.pk)

            if numero_existant.exists():
                raise forms.ValidationError(
                    f'Le numéro de départ N°{numero_depart} existe déjà pour la gare {gare} '
                    f'à la date du {date_depart.strftime("%d/%m/%Y")}. '
                    f'Veuillez choisir un autre numéro de départ.'
                )

        # Vérifier l'unicité du voyage (éviter les doublons)
        if gare and ligne and date_depart and heure_depart and periode and numero_depart:
            voyage_existant = Voyage.objects.filter(
                gare=gare,
                ligne=ligne,
                date_depart=date_depart,
                heure_depart=heure_depart,
                periode=periode,
                numero_depart=numero_depart
            )

            # Exclure l'instance actuelle si on est en mode modification
            if self.instance and self.instance.pk:
                voyage_existant = voyage_existant.exclude(pk=self.instance.pk)

            if voyage_existant.exists():
                raise forms.ValidationError(
                    f'Un voyage existe déjà pour cette combinaison : '
                    f'{ligne} - {date_depart.strftime("%d/%m/%Y")} à {heure_depart.strftime("%H:%M")} '
                    f'({dict(Voyage.PERIODE_CHOICES)[periode]}) - Départ N°{numero_depart}. '
                    f'Veuillez modifier le numéro de départ ou les autres informations.'
                )

        return cleaned_data
