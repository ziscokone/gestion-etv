from django.db import models


class Ligne(models.Model):
    """
    Modèle représentant une ligne de transport.
    Chaque ligne appartient à une gare spécifique.
    Ex: La gare d'Abidjan a la ligne "Abidjan → Tengrela"
        La gare de Tengrela a la ligne "Tengrela → Abidjan"
    """
    nom = models.CharField(
        max_length=200,
        verbose_name="Nom de la ligne",
        help_text="Ex: Conakry - Kindia"
    )
    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Gare",
        help_text="Gare de départ de cette ligne",
        null=True,
        blank=True
    )
    ville_depart = models.CharField(max_length=100, verbose_name="Ville de départ")
    ville_arrivee = models.CharField(max_length=100, verbose_name="Ville d'arrivée")
    distance_km = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Distance (km)"
    )
    duree_estimee = models.DurationField(
        blank=True,
        null=True,
        verbose_name="Durée estimée",
        help_text="Format: HH:MM:SS"
    )
    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Compagnie"
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ligne"
        verbose_name_plural = "Lignes"
        ordering = ['nom']
        unique_together = ['ville_depart', 'ville_arrivee', 'gare']

    def __str__(self):
        return f"{self.ville_depart} → {self.ville_arrivee}"

    def get_trajet_inverse(self):
        """Retourne la ligne inverse si elle existe."""
        return Ligne.objects.filter(
            ville_depart=self.ville_arrivee,
            ville_arrivee=self.ville_depart,
            compagnie=self.compagnie
        ).first()
