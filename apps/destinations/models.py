import unicodedata

from django.db import models
from django.db.models.functions import Lower


def cle_ville(valeur):
    """Forme normalisée d'une ville d'arrivée, utilisée pour comparer deux
    destinations : espaces multiples réduits, accents retirés, casse ignorée.

    « Bouaké », «  bouake  » et « BOUAKÉ » donnent tous la même clé. Ce test
    est fait en Python (et non via ``LOWER()`` SQL) car ``LOWER()`` de SQLite
    ne gère que l'ASCII : « É » y resterait en majuscule.
    """
    texte = ' '.join((valeur or '').split())
    texte = unicodedata.normalize('NFKD', texte)
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    return texte.casefold()


class Destination(models.Model):
    """
    Modèle représentant une destination depuis une gare.
    Chaque gare a ses propres destinations avec ses tarifs.
    """
    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.CASCADE,
        related_name='destinations',
        verbose_name="Gare de départ"
    )
    ligne = models.ForeignKey(
        'lignes.Ligne',
        on_delete=models.CASCADE,
        related_name='destinations',
        verbose_name="Ligne"
    )
    ville_arrivee = models.CharField(max_length=100, verbose_name="Ville d'arrivée")
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant (FCFA)"
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Destination"
        verbose_name_plural = "Destinations"
        ordering = ['gare', 'ville_arrivee']
        constraints = [
            models.UniqueConstraint(
                'gare', 'ligne', Lower('ville_arrivee'), 'montant',
                name='destination_unique_gare_ligne_ville_montant_ci',
                violation_error_message=(
                    "Cette destination existe déjà : même ligne, même gare de départ, "
                    "même ville d'arrivée et même montant (la casse n'est pas prise en compte)."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.gare.ville} → {self.ville_arrivee} ({self.montant} FCFA)"

    @property
    def trajet_complet(self):
        """Retourne le trajet complet."""
        return f"{self.gare.ville} → {self.ville_arrivee}"
