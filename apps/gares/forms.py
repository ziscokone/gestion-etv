from django import forms
from .models import Gare


class GareForm(forms.ModelForm):
    """Formulaire pour créer/modifier une gare."""

    class Meta:
        model = Gare
        fields = ['nom', 'code', 'ville', 'adresse', 'telephone', 'compagnie', 'active']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la gare'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CKY', 'maxlength': 10}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro de téléphone'}),
            'compagnie': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
        return code


class ImprimanteForm(forms.ModelForm):
    """Configuration de l'imprimante thermique ESC/POS de ce poste."""

    class Meta:
        model = Gare
        fields = ['imprimante_nom', 'imprimante_largeur_caracteres']
        widgets = {
            'imprimante_nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: XP-80C, EPSON TM-T20II',
            }),
            'imprimante_largeur_caracteres': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '20', 'max': '64',
            }),
        }
        labels = {
            'imprimante_nom': "Nom de l'imprimante (tel qu'affiché dans Windows)",
            'imprimante_largeur_caracteres': 'Largeur du ticket (caractères)',
        }
        help_texts = {
            'imprimante_nom': "Ouvrir \"Périphériques et imprimantes\" dans Windows et copier le nom exact affiché.",
            'imprimante_largeur_caracteres': "42 convient à la plupart des imprimantes thermiques 80mm. À ajuster si le texte déborde ou semble trop étroit.",
        }
