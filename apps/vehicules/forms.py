from django import forms
from django.forms import inlineformset_factory
from .models import ModeleVehicule, Vehicule, ReparationVehicule, LigneIntervention, TypeReparation
from datetime import date
import json


class ModeleVehiculeForm(forms.ModelForm):
    """Formulaire pour créer et modifier un modèle de véhicule."""

    class Meta:
        model = ModeleVehicule
        fields = ['marque', 'nom', 'capacite', 'disposition_sieges']
        widgets = {
            'marque': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Mercedes-Benz'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Sprinter 516'
            }),
            'capacite': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 20',
                'min': '1'
            }),
            'disposition_sieges': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': '''Exemple de disposition en JSON:
{
  "colonnes": 5,
  "rangees": [
    [1, 2, null, 3, 4],
    [5, 6, null, 7, 8],
    [9, 10, null, 11, 12]
  ],
  "sieges_non_vendables": [1]
}'''
            }),
        }
        labels = {
            'marque': 'Marque',
            'nom': 'Nom du modèle',
            'capacite': 'Capacité (nombre de places)',
            'disposition_sieges': 'Disposition des sièges (JSON)',
        }
        help_texts = {
            'disposition_sieges': 'Configuration JSON de la disposition des sièges. Utiliser null pour les espaces vides (couloirs).',
        }

    def clean_disposition_sieges(self):
        """Valider le format JSON de la disposition."""
        data = self.cleaned_data.get('disposition_sieges')
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise forms.ValidationError('Format JSON invalide.')

        # Validation de la structure
        if not isinstance(data, dict):
            raise forms.ValidationError('La disposition doit être un objet JSON.')

        if 'colonnes' not in data or 'rangees' not in data:
            raise forms.ValidationError('Les clés "colonnes" et "rangees" sont requises.')

        if not isinstance(data['rangees'], list):
            raise forms.ValidationError('Les rangées doivent être une liste.')

        return data


class VehiculeForm(forms.ModelForm):
    """Formulaire pour créer et modifier un véhicule."""

    class Meta:
        model = Vehicule
        fields = [
            # Informations générales
            'numero_ordre', 'modele', 'immatriculation', 'actif', 'notes',
            # Caractéristiques techniques
            'numero_chassis', 'annee_fabrication', 'date_mise_circulation',
            'type_carburant', 'type_boite', 'kilometrage_actuel',
            # Documents administratifs
            'numero_carte_grise', 'patente', 'carte_stationnement',
            # Documents & conformité légale
            'compagnie_assurance', 'date_expiration_assurance',
            'date_expiration_visite_technique', 'date_expiration_carte_grise',
            'date_expiration_licence_transport'
        ]
        widgets = {
            # Informations générales
            'numero_ordre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 01, 05, 30'
            }),
            'modele': forms.Select(attrs={
                'class': 'form-select',
            }),
            'immatriculation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: GN-1234-AB'
            }),
            'actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notes et observations sur le véhicule...'
            }),
            # Caractéristiques techniques
            'numero_chassis': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: WDD9066051P123456'
            }),
            'annee_fabrication': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2020',
                'min': '1990',
                'max': '2030'
            }),
            'date_mise_circulation': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'type_carburant': forms.Select(attrs={
                'class': 'form-select',
            }),
            'type_boite': forms.Select(attrs={
                'class': 'form-select',
            }),
            'kilometrage_actuel': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 150000',
                'min': '0'
            }),
            # Documents administratifs
            'numero_carte_grise': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de la carte grise'
            }),
            'patente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de la patente'
            }),
            'carte_stationnement': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de la carte de stationnement'
            }),
            # Documents & conformité légale
            'compagnie_assurance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Allianz Assurances Guinée'
            }),
            'date_expiration_assurance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_expiration_visite_technique': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_expiration_carte_grise': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_expiration_licence_transport': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            # Informations générales
            'numero_ordre': 'N° d\'ordre',
            'modele': 'Modèle de véhicule',
            'immatriculation': 'Numéro d\'immatriculation',
            'actif': 'Véhicule actif',
            'notes': 'Notes et observations',
            # Caractéristiques techniques
            'numero_chassis': 'Numéro de châssis (VIN)',
            'annee_fabrication': 'Année de fabrication',
            'date_mise_circulation': 'Date de mise en circulation',
            'type_carburant': 'Type de carburant',
            'type_boite': 'Type de boîte de vitesse',
            'kilometrage_actuel': 'Kilométrage actuel (km)',
            # Documents administratifs
            'numero_carte_grise': 'N° Carte Grise',
            'patente': 'Patente',
            'carte_stationnement': 'Carte de Stationnement',
            # Documents & conformité légale
            'compagnie_assurance': 'Compagnie d\'assurance',
            'date_expiration_assurance': 'Date d\'expiration assurance',
            'date_expiration_visite_technique': 'Date d\'expiration visite technique',
            'date_expiration_carte_grise': 'Date d\'expiration carte grise',
            'date_expiration_licence_transport': 'Date d\'expiration licence de transport',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un document marqué "n'expire pas" dans la config compagnie n'a pas
        # sa raison d'être dans ce formulaire : on retire le champ plutôt que
        # de laisser une date d'expiration inutile et source de confusion.
        from apps.compagnie.models import Compagnie
        compagnie = Compagnie.get_instance()
        if compagnie:
            for cle, _, champ_date in Compagnie.DOCUMENTS_VEHICULE:
                if not getattr(compagnie, f'alerte_{cle}_active') and champ_date in self.fields:
                    del self.fields[champ_date]


class ReparationVehiculeForm(forms.ModelForm):
    """Formulaire pour l'entête d'une entrée au garage."""

    class Meta:
        model = ReparationVehicule
        fields = ['vehicule', 'date_reparation', 'garage_prestataire', 'statut', 'notes']
        widgets = {
            'vehicule': forms.Select(attrs={'class': 'form-select'}),
            'date_reparation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'garage_prestataire': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Garage Central Auto'
            }),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes générales sur cette entrée au garage (optionnel)...'
            }),
        }
        labels = {
            'vehicule': 'Véhicule',
            'date_reparation': "Date d'entrée au garage",
            'garage_prestataire': 'Garage/Prestataire',
            'statut': 'Statut',
            'notes': 'Notes générales',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop('statut')

    def clean_date_reparation(self):
        date_rep = self.cleaned_data.get('date_reparation')
        if date_rep and date_rep > date.today():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return date_rep


class LigneInterventionForm(forms.ModelForm):
    """Formulaire pour une ligne d'intervention."""

    class Meta:
        model = LigneIntervention
        fields = [
            'type_reparation', 'description', 'montant',
            'kilometrage', 'pieces_remplacees',
            'huile_utilisee', 'intervalle_km',
        ]
        widgets = {
            'type_reparation': forms.Select(attrs={
                'class': 'form-select ligne-type-select',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Décrire l\'intervention...'
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 250000',
                'min': '0',
                'step': '0.01'
            }),
            'kilometrage': forms.NumberInput(attrs={
                'class': 'form-control ligne-km-field',
                'placeholder': 'Ex: 145000',
                'min': '0'
            }),
            'pieces_remplacees': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ex: Embrayage, disques de frein...'
            }),
            'huile_utilisee': forms.TextInput(attrs={
                'class': 'form-control ligne-huile-field',
                'placeholder': 'Ex: Total Rubia 15W40'
            }),
            'intervalle_km': forms.NumberInput(attrs={
                'class': 'form-control ligne-intervalle-field',
                'placeholder': 'Ex: 10000',
                'min': '0'
            }),
        }
        labels = {
            'type_reparation': "Type d'intervention",
            'description': 'Description',
            'montant': 'Montant (FCFA)',
            'kilometrage': 'Km au compteur',
            'pieces_remplacees': 'Pièces remplacées',
            'huile_utilisee': 'Huile utilisée',
            'intervalle_km': 'Prochain dans (km)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type_reparation'].queryset = TypeReparation.objects.filter(actif=True)

    def clean(self):
        cleaned_data = super().clean()
        type_rep = cleaned_data.get('type_reparation')
        if type_rep and type_rep.is_vidange:
            if not cleaned_data.get('huile_utilisee'):
                self.add_error('huile_utilisee', "L'huile est obligatoire pour une vidange.")
            if not cleaned_data.get('kilometrage'):
                self.add_error('kilometrage', "Le kilométrage est obligatoire pour une vidange.")
        return cleaned_data


def get_vidange_type_ids():
    """Retourne les IDs des types marqués is_vidange (pour afficher le champ huile)."""
    return list(TypeReparation.objects.filter(actif=True, is_vidange=True).values_list('id', flat=True))


def get_km_type_ids():
    """Retourne les IDs des types qui nécessitent la saisie du kilométrage."""
    return list(TypeReparation.objects.filter(actif=True, necessite_kilometrage=True).values_list('id', flat=True))


def get_suivi_km_type_ids():
    """Retourne les IDs des types avec suivi km (necessite_kilometrage ou intervalle_km_defaut défini)."""
    return list(TypeReparation.objects.filter(actif=True).exclude(
        necessite_kilometrage=False, intervalle_km_defaut__isnull=True
    ).values_list('id', flat=True))


LigneInterventionFormSet = inlineformset_factory(
    ReparationVehicule,
    LigneIntervention,
    form=LigneInterventionForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class TypeReparationForm(forms.ModelForm):
    """Formulaire pour créer et modifier un type de réparation."""

    class Meta:
        model = TypeReparation
        fields = ['nom', 'description', 'necessite_kilometrage', 'intervalle_km_defaut', 'is_vidange', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Courroie de distribution'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du type de réparation...'
            }),
            'necessite_kilometrage': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_necessite_kilometrage'
            }),
            'intervalle_km_defaut': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 10000',
                'min': '0'
            }),
            'is_vidange': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_is_vidange'
            }),
            'actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'nom': 'Nom',
            'description': 'Description',
            'necessite_kilometrage': 'Nécessite saisie kilométrage',
            'intervalle_km_defaut': 'Intervalle km par défaut',
            'is_vidange': "C'est une vidange (huile requise)",
            'actif': 'Actif',
        }
        help_texts = {
            'necessite_kilometrage': 'Affiche le bloc kilométrage lors de la création d\'une réparation de ce type.',
            'intervalle_km_defaut': 'Optionnel — km avant la prochaine intervention (ex: 10 000 pour une vidange).',
            'is_vidange': 'Affiche en plus le champ "huile utilisée". Uniquement pour les vidanges d\'huile.',
        }
