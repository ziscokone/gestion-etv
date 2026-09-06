from django.db import models


class SyncLog(models.Model):
    """Historique des synchronisations entre un poste gare hors-ligne et le serveur central."""

    DIRECTION_CHOICES = [
        ('push', 'Push (gare → central)'),
        ('pull', 'Pull (central → gare)'),
    ]
    STATUT_CHOICES = [
        ('ok', 'Réussi'),
        ('partiel', 'Réussi avec erreurs'),
        ('erreur', 'Échoué'),
    ]

    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.CASCADE,
        related_name='sync_logs',
        verbose_name="Gare"
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, verbose_name="Sens")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ok', verbose_name="Statut")
    nb_enregistrements = models.PositiveIntegerField(default=0, verbose_name="Nombre d'enregistrements")
    detail = models.TextField(blank=True, verbose_name="Détail / erreurs")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        verbose_name = "Journal de synchronisation"
        verbose_name_plural = "Journaux de synchronisation"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.get_direction_display()} — {self.gare.nom} — {self.date_creation:%d/%m/%Y %H:%M} ({self.get_statut_display()})"
