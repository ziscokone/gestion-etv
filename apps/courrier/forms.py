from django import forms

from .models import Colis, TypeColis


class ColisForm(forms.ModelForm):
    """
    Formulaire d'enregistrement d'un colis. Les champs expéditeur/destinataire
    sont de simples champs texte (pas des FK) — la réconciliation avec la
    base clients se fait côté vue via Client.objects.get_or_create, comme
    pour un billet (voir apps.guichet.views.creer_billet).
    """
    expediteur_nom = forms.CharField(
        max_length=200,
        label="Nom de l'expéditeur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom complet de l'expéditeur"})
    )
    expediteur_telephone = forms.CharField(
        max_length=20,
        label="Téléphone de l'expéditeur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro de téléphone', 'autocomplete': 'off'})
    )
    destinataire_nom = forms.CharField(
        max_length=200,
        label="Nom du destinataire",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet du destinataire'})
    )
    destinataire_telephone = forms.CharField(
        max_length=20,
        label="Téléphone du destinataire",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro de téléphone', 'autocomplete': 'off'})
    )

    class Meta:
        model = Colis
        fields = [
            'gare_origine', 'gare_destination',
            'expediteur_nom', 'expediteur_telephone',
            'destinataire_nom', 'destinataire_telephone',
            'type_colis', 'description', 'valeur_declaree',
            'montant', 'moyen_paiement',
        ]
        widgets = {
            'gare_origine': forms.Select(attrs={'class': 'form-select'}),
            'gare_destination': forms.Select(attrs={'class': 'form-select'}),
            'type_colis': forms.Select(attrs={'class': 'form-select', 'id': 'id_type_colis'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Nature du contenu (ex: vêtements, documents, téléphone...)'
            }),
            'valeur_declaree': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': 'Optionnel', 'min': '0'
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'id_montant', 'min': '0'
            }),
            'moyen_paiement': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'gare_origine': "Gare d'origine",
            'gare_destination': 'Gare de destination',
            'type_colis': 'Type de colis',
            'description': 'Description du contenu',
            'valeur_declaree': 'Valeur déclarée (FCFA)',
            'montant': 'Montant du transport (FCFA)',
            'moyen_paiement': 'Moyen de paiement',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type_colis'].queryset = TypeColis.objects.filter(actif=True)

        # Un guichetier/chef de gare enregistre toujours au nom de sa propre
        # gare — seuls les accès globaux choisissent explicitement la gare
        # d'origine (même patron que ReparationVehiculeForm qui retire le
        # champ 'statut' pour une nouvelle réparation).
        if user is not None and not user.has_global_access and user.gare_id:
            self.fields.pop('gare_origine')
            self.initial_gare_origine = user.gare
        else:
            self.initial_gare_origine = None

        # La gare de destination ne doit jamais être la gare d'origine.
        if user is not None and not user.has_global_access and user.gare_id:
            self.fields['gare_destination'].queryset = self.fields['gare_destination'].queryset.exclude(
                pk=user.gare_id
            ).filter(active=True)
        else:
            self.fields['gare_destination'].queryset = self.fields['gare_destination'].queryset.filter(active=True)

    def clean(self):
        cleaned_data = super().clean()
        gare_destination = cleaned_data.get('gare_destination')
        gare_origine = cleaned_data.get('gare_origine') or self.initial_gare_origine
        if gare_destination and gare_origine and gare_destination == gare_origine:
            self.add_error('gare_destination', "La gare de destination doit être différente de la gare d'origine.")

        expediteur_tel = (cleaned_data.get('expediteur_telephone') or '').strip()
        destinataire_tel = (cleaned_data.get('destinataire_telephone') or '').strip()
        if expediteur_tel and destinataire_tel and expediteur_tel == destinataire_tel:
            self.add_error(
                'destinataire_telephone',
                "Le téléphone du destinataire ne peut pas être le même que celui de l'expéditeur."
            )

        return cleaned_data


class TypeColisForm(forms.ModelForm):
    class Meta:
        model = TypeColis
        fields = ['nom', 'tarif_indicatif', 'ordre', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Petit colis'}),
            'tarif_indicatif': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Ex: 2500'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nom': 'Nom',
            'tarif_indicatif': 'Tarif indicatif (FCFA)',
            'ordre': "Ordre d'affichage",
            'actif': 'Actif',
        }
        help_texts = {
            'tarif_indicatif': "Montant suggéré à l'enregistrement d'un colis — toujours modifiable au cas par cas.",
        }


class RetraitColisForm(forms.Form):
    """
    Le retirant n'est pas forcément le destinataire enregistré sur le colis —
    ça peut être un mandataire. On capture systématiquement qui s'est présenté
    (nom, téléphone, CNI) : le téléphone sert aussi de clé pour retrouver/
    mémoriser cette personne comme Client, afin que la prochaine fois son nom
    et son CNI ressortent automatiquement (voir vue RetraitColisView + endpoint
    clients:suggerer_clients).
    """
    code_retrait = forms.CharField(
        max_length=10,
        label="Code de retrait",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Code communiqué par l\'expéditeur',
            'autocomplete': 'off', 'readonly': 'readonly',
        })
    )
    retirant_telephone = forms.CharField(
        max_length=20,
        label="Téléphone du retirant",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro de téléphone', 'autocomplete': 'off'})
    )
    retirant_nom = forms.CharField(
        max_length=200,
        label="Nom du retirant",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet de la personne qui retire'})
    )
    piece_identite = forms.CharField(
        max_length=100,
        label="N° CNI présenté",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 123456789', 'autocomplete': 'off'})
    )
