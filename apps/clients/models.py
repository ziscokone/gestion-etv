import uuid

from django.db import models


class Client(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Utilisé dans les URL à la place de l'identifiant interne, pour ne pas exposer le volume de clients."
    )
    telephone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Téléphone"
    )
    nom_complet = models.CharField(
        max_length=200,
        verbose_name="Nom complet"
    )
    numero_cni = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° CNI",
        help_text="Mémorisé dès qu'il est saisi une première fois (ex: retrait de colis) pour être réutilisé automatiquement ensuite."
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Synchronisé le",
        help_text="Renseigné quand ce client, créé sur un poste gare hors-ligne, a été remonté vers le serveur central."
    )

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['nom_complet']

    def __str__(self):
        return f"{self.nom_complet} ({self.telephone})"

    @property
    def nombre_voyages(self):
        return self.billets.filter(statut__in=['paye', 'reserve', 'reporte']).count()
