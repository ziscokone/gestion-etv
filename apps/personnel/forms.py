from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Utilisateur, Chauffeur, Convoyeur


class UtilisateurForm(forms.ModelForm):
    """Formulaire pour créer et modifier un utilisateur."""
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Laisser vide pour conserver le mot de passe actuel'
    )
    password2 = forms.CharField(
        label='Confirmation du mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Utilisateur
        fields = ['username', 'nom_complet', 'telephone', 'role', 'gare', 'actif']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'nom_complet': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'gare': forms.Select(attrs={'class': 'form-select'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'username': 'Nom d\'utilisateur pour la connexion',
            'gare': 'Gare assignée (requis pour Chef de gare et Guichetier)',
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['password1'].help_text = 'Laisser vide pour conserver le mot de passe actuel'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['password1'].help_text = 'Minimum 8 caractères'

        # Seul le vrai superuser Django peut activer/désactiver un compte
        if not (self.current_user and self.current_user.is_superuser):
            self.fields.pop('actif', None)

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Les mots de passe ne correspondent pas.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class ChauffeurForm(forms.ModelForm):
    """Formulaire pour créer et modifier un chauffeur."""

    class Meta:
        model = Chauffeur
        fields = [
            # Informations générales
            'nom_complet', 'telephone', 'numero_permis',
            # Identité
            'numero_cni', 'situation_matrimoniale', 'nombre_enfants',
            # Coordonnées
            'telephone_2', 'lieu_habitation',
            # Contact d'urgence
            'personne_urgence', 'telephone_urgence',
            # Informations professionnelles
            'date_embauche', 'salaire', 'cv',
            # Statut
            'actif'
        ]
        widgets = {
            'nom_complet': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et prénom'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 70 00 00 00'}),
            'numero_permis': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro du permis de conduire'}),
            'numero_cni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro carte nationale d\'identité'}),
            'situation_matrimoniale': forms.Select(attrs={'class': 'form-select'}),
            'nombre_enfants': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'telephone_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone secondaire'}),
            'lieu_habitation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quartier / Ville'}),
            'personne_urgence': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la personne'}),
            'telephone_urgence': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone de la personne'}),
            'date_embauche': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salaire': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Salaire en FCFA'}),
            'cv': forms.FileInput(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ConvoyeurForm(forms.ModelForm):
    """Formulaire pour créer et modifier un convoyeur."""

    class Meta:
        model = Convoyeur
        fields = [
            # Informations générales
            'nom_complet', 'telephone',
            # Identité
            'numero_cni', 'situation_matrimoniale', 'nombre_enfants',
            # Coordonnées
            'telephone_2', 'lieu_habitation',
            # Contact d'urgence
            'personne_urgence', 'telephone_urgence',
            # Statut
            'actif'
        ]
        widgets = {
            'nom_complet': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et prénom'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 70 00 00 00'}),
            'numero_cni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro carte nationale d\'identité'}),
            'situation_matrimoniale': forms.Select(attrs={'class': 'form-select'}),
            'nombre_enfants': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'telephone_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone secondaire'}),
            'lieu_habitation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quartier / Ville'}),
            'personne_urgence': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la personne'}),
            'telephone_urgence': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone de la personne'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
