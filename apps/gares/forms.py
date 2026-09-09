from django import forms

from apps.personnel.models import Utilisateur

from .models import Gare


class GareForm(forms.ModelForm):
    """Formulaire pour créer/modifier une gare."""

    chef_gare = forms.ModelChoiceField(
        queryset=Utilisateur.objects.filter(role='chef_gare', actif=True).order_by('nom_complet'),
        required=False,
        label="Chef de gare",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Affecte ce chef de gare à cette gare (déplacé s'il était sur une autre gare).",
    )

    class Meta:
        model = Gare
        fields = ['nom', 'code', 'ville', 'adresse', 'telephone', 'compagnie', 'active']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Gare Adjamé'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : GADJ', 'maxlength': 10}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Abidjan'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 09 50 96 90 50'}),
            'compagnie': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['chef_gare'].initial = self.instance.get_chef_gare()
        # Étiquettes : « Nom — (gare actuelle) » pour repérer un chef déjà affecté.
        self.fields['chef_gare'].label_from_instance = (
            lambda u: f"{u.nom_complet}" + (f" — actuellement à {u.gare.nom}" if u.gare else " — non affecté")
        )

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
        return code

    def save(self, commit=True):
        gare = super().save(commit=commit)
        if commit:
            self._appliquer_chef(gare)
        return gare

    def _appliquer_chef(self, gare):
        nouveau = self.cleaned_data.get('chef_gare')
        ancien = gare.get_chef_gare()
        if ancien and ancien != nouveau:
            ancien.gare = None
            ancien.save(update_fields=['gare'])
        if nouveau and nouveau.gare_id != gare.pk:
            nouveau.gare = gare
            nouveau.save(update_fields=['gare'])


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
