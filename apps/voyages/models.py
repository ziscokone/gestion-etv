import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Voyage(models.Model):
    """
    Modèle représentant un voyage/départ.
    Peut être créé automatiquement via un programme ou manuellement.
    """
    PERIODE_CHOICES = [
        ('matin', 'Matinée'),
        ('soir', 'Soir'),
    ]

    STATUT_CHOICES = [
        ('programme', 'Programmé'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ]

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Utilisé dans les URL à la place de l'identifiant interne, pour ne pas exposer le volume de voyages."
    )

    numero_depart = models.PositiveIntegerField(
        verbose_name="Numéro de départ",
        help_text="Numéro séquentiel du départ (ex: 1, 2, 3...)",
        default=1
    )

    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.CASCADE,
        related_name='voyages',
        verbose_name="Gare de départ"
    )
    ligne = models.ForeignKey(
        'lignes.Ligne',
        on_delete=models.CASCADE,
        related_name='voyages',
        verbose_name="Ligne"
    )
    date_depart = models.DateField(verbose_name="Date de départ")
    heure_depart = models.TimeField(verbose_name="Heure de départ")
    periode = models.CharField(
        max_length=10,
        choices=PERIODE_CHOICES,
        verbose_name="Période"
    )
    vehicule = models.ForeignKey(
        'vehicules.Vehicule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voyages',
        verbose_name="Véhicule"
    )
    chauffeur = models.ForeignKey(
        'personnel.Chauffeur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voyages',
        verbose_name="Chauffeur"
    )
    convoyeur = models.ForeignKey(
        'personnel.Convoyeur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voyages',
        verbose_name="Convoyeur"
    )
    recette_bagages = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Recette Bagages (FCFA)",
        help_text="Montant total des bagages pour ce voyage"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='programme',
        verbose_name="Statut"
    )
    programme = models.ForeignKey(
        'programmes.ProgrammeDepart',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voyages_generes',
        verbose_name="Programme source"
    )
    cree_automatiquement = models.BooleanField(
        default=False,
        verbose_name="Créé automatiquement"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Synchronisé le",
        help_text="Renseigné quand ce voyage, créé sur un poste gare hors-ligne, a été remonté vers le serveur central."
    )

    class Meta:
        verbose_name = "Voyage"
        verbose_name_plural = "Voyages"
        ordering = ['-date_depart', 'heure_depart']
        # Contrainte d'unicité pour éviter les doublons
        # Un voyage est unique par: gare + ligne + date + heure + période + numéro de départ
        unique_together = ['gare', 'ligne', 'date_depart', 'heure_depart', 'periode', 'numero_depart']

    def __str__(self):
        return f"{self.ligne} - {self.date_depart.strftime('%d/%m/%Y')} {self.heure_depart.strftime('%H:%M')} (Départ {self.numero_depart})"

    @property
    def est_passe(self):
        """Vérifie si le voyage est passé."""
        from datetime import datetime
        now = timezone.now()
        voyage_datetime = timezone.make_aware(
            datetime.combine(self.date_depart, self.heure_depart)
        )
        return now > voyage_datetime

    @property
    def capacite(self):
        """Retourne la capacité du véhicule assigné."""
        if self.vehicule:
            return self.vehicule.capacite
        return 0

    def get_sieges_disponibles(self):
        """Retourne la liste des sièges encore disponibles."""
        if not self.vehicule:
            return []

        sieges_vendables = self.vehicule.get_sieges_vendables()
        sieges_pris = self.billets.exclude(
            statut__in=['reporte', 'rembourse']
        ).values_list('numero_siege', flat=True)

        return [s for s in sieges_vendables if s not in sieges_pris]

    def get_sieges_reserves(self):
        """Retourne la liste des sièges réservés (non payés)."""
        return list(
            self.billets.filter(statut='reserve')
            .values_list('numero_siege', flat=True)
        )

    def get_sieges_payes(self):
        """Retourne la liste des sièges payés."""
        return list(
            self.billets.filter(statut='paye')
            .values_list('numero_siege', flat=True)
        )

    def get_sieges_gratuits_en_attente(self):
        return list(self.billets.filter(statut='gratuit_en_attente').values_list('numero_siege', flat=True))

    def get_sieges_gratuits(self):
        return list(self.billets.filter(statut='gratuit').values_list('numero_siege', flat=True))

    def get_nb_places_vendues(self):
        """Retourne le nombre de places payées."""
        return self.billets.filter(statut='paye').count()

    def get_nb_places_reservees(self):
        """Retourne le nombre de places réservées (non payées)."""
        return self.billets.filter(statut='reserve').count()

    def get_nb_places_disponibles(self):
        """Retourne le nombre de places encore disponibles."""
        return len(self.get_sieges_disponibles())

    def get_montant_total(self):
        """Retourne le montant total des billets payés."""
        from django.db.models import Sum
        total = self.billets.filter(statut='paye').aggregate(
            total=Sum('montant')
        )['total']
        return total or 0

    def get_total_recettes(self):
        """Retourne le total des recettes (billets + bagages)."""
        from decimal import Decimal
        montant_billets = Decimal(str(self.get_montant_total()))
        recette_bagages = self.recette_bagages if self.recette_bagages else Decimal('0')
        return montant_billets + recette_bagages

    def get_benefice_net(self):
        """Retourne le bénéfice net (recettes - dépenses)."""
        from decimal import Decimal
        total_recettes = self.get_total_recettes()
        depenses = self.depenses.all()
        total_depenses = sum((d.montant for d in depenses), Decimal('0'))
        return total_recettes - total_depenses

    def get_disposition_sieges_avec_statut(self):
        """
        Retourne la disposition des sièges avec leur statut actuel.
        Pour l'affichage dans l'interface guichetier.
        """
        if not self.vehicule:
            return None

        disposition = self.vehicule.modele.get_disposition_pour_affichage()
        sieges_reserves = set(self.get_sieges_reserves())
        sieges_payes = set(self.get_sieges_payes())
        sieges_gratuits_attente = set(self.get_sieges_gratuits_en_attente())
        sieges_gratuits = set(self.get_sieges_gratuits())

        for rangee in disposition['rangees']:
            for siege in rangee['sieges']:
                if siege['numero'] is not None:
                    if siege['numero'] in sieges_payes:
                        siege['statut'] = 'paye'
                    elif siege['numero'] in sieges_gratuits:
                        siege['statut'] = 'gratuit'
                    elif siege['numero'] in sieges_gratuits_attente:
                        siege['statut'] = 'gratuit_en_attente'
                    elif siege['numero'] in sieges_reserves:
                        siege['statut'] = 'reserve'
                    elif siege['type'] == 'non_vendable':
                        siege['statut'] = 'non_vendable'
                    else:
                        siege['statut'] = 'disponible'

        return disposition

    def siege_disponible(self, numero_siege):
        """Vérifie si un siège est disponible."""
        return numero_siege in self.get_sieges_disponibles()

    def changer_vehicule(self, nouveau_vehicule):
        """
        Change le véhicule assigné au voyage.
        Vérifie que le nouveau véhicule a assez de capacité.
        """
        billets_existants = self.billets.count()
        if nouveau_vehicule.capacite < billets_existants:
            raise ValueError(
                f"Le nouveau véhicule n'a pas assez de capacité. "
                f"Billets existants: {billets_existants}, "
                f"Capacité véhicule: {nouveau_vehicule.capacite}"
            )

        self.vehicule = nouveau_vehicule
        self.save(update_fields=['vehicule', 'date_modification'])


class ReassignationSiege(models.Model):
    """Trace chaque réassignation de siège lors d'un changement de véhicule."""
    voyage = models.ForeignKey(
        Voyage, on_delete=models.CASCADE,
        related_name='reassignations', verbose_name="Voyage"
    )
    billet = models.ForeignKey(
        'billets.Billet', on_delete=models.CASCADE,
        related_name='reassignations', verbose_name="Billet"
    )
    ancien_siege = models.PositiveIntegerField(verbose_name="Ancien siège")
    nouveau_siege = models.PositiveIntegerField(verbose_name="Nouveau siège")
    date_reassignation = models.DateTimeField(auto_now_add=True)
    effectuee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Effectuée par"
    )

    class Meta:
        verbose_name = "Réassignation de siège"
        verbose_name_plural = "Réassignations de sièges"
        ordering = ['-date_reassignation']

    def __str__(self):
        return f"Siège {self.ancien_siege} → {self.nouveau_siege} ({self.voyage})"
