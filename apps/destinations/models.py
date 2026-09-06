from django.db import models
from django.db.models.functions import Lower


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
                'gare', 'ligne', Lower('ville_arrivee'),
                name='destination_unique_gare_ligne_ville_ci',
                violation_error_message="Une destination existe déjà pour cette gare, cette ligne et cette ville d'arrivée (la casse n'est pas prise en compte).",
            ),
        ]

    def __str__(self):
        return f"{self.gare.ville} → {self.ville_arrivee} ({self.montant} FCFA)"

    @property
    def trajet_complet(self):
        """Retourne le trajet complet."""
        return f"{self.gare.ville} → {self.ville_arrivee}"
