import uuid

from django.db import models


class Client(models.Model):
    CATEGORIE_CHOICES = [
        ('particulier', 'Particulier'),
        ('societe', 'Société'),
    ]

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Utilisé dans les URL à la place de l'identifiant interne, pour ne pas exposer le volume de clients."
    )
    categorie = models.CharField(
        max_length=15,
        choices=CATEGORIE_CHOICES,
        default='particulier',
        db_index=True,
        verbose_name="Catégorie",
        help_text="« Société » = structure qui nous envoie des passagers. Le programme de fidélité ne s'applique qu'aux « Particulier »."
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

    @property
    def est_particulier(self):
        return self.categorie == 'particulier'

    # ── Programme de fidélité ──────────────────────────────────────────
    # Un « voyage fidélité » = un billet réellement payé (statut 'paye'),
    # payé après la date d'activation du programme. Un report ne compte donc
    # qu'une fois (seul le billet payé final est en 'paye'), et un billet
    # remboursé (statut 'rembourse') sort automatiquement du compte.

    def _fidelite_config(self):
        """(active, seuil, depuis) du programme, ou (False, 0, None) si inactif."""
        from apps.compagnie.models import Compagnie
        c = Compagnie.get_instance()
        if not c or not c.fidelite_active or not c.fidelite_seuil_voyages:
            return False, 0, None
        return True, c.fidelite_seuil_voyages, c.fidelite_active_depuis

    @property
    def fidelite_voyages_comptabilises(self):
        """Nombre de voyages payés pris en compte pour la fidélité."""
        active, _, depuis = self._fidelite_config()
        if not active or not self.est_particulier:
            return 0
        qs = self.billets.filter(statut='paye')
        if depuis:
            qs = qs.filter(date_paiement__gte=depuis)
        return qs.count()

    @property
    def fidelite_tickets_emis(self):
        """Nombre de tickets fidélité déjà accordés à ce client."""
        return self.billets.filter(statut='fidelite').count()

    @property
    def fidelite_eligible(self):
        """True si le client a droit, maintenant, à un voyage offert."""
        active, seuil, _ = self._fidelite_config()
        if not active or not self.est_particulier:
            return False
        objectif = seuil * (self.fidelite_tickets_emis + 1)
        return self.fidelite_voyages_comptabilises >= objectif

    @property
    def fidelite_reste(self):
        """Voyages payés restants avant le prochain voyage offert (0 si éligible)."""
        active, seuil, _ = self._fidelite_config()
        if not active or not self.est_particulier:
            return None
        objectif = seuil * (self.fidelite_tickets_emis + 1)
        return max(0, objectif - self.fidelite_voyages_comptabilises)
