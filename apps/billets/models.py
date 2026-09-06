import uuid

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Billet(models.Model):
    """
    Modèle représentant un billet de transport.
    """
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Utilisé dans les URL à la place de l'identifiant interne, pour ne pas exposer le volume de billets."
    )

    STATUT_CHOICES = [
        ('reserve', 'Réservé'),
        ('paye', 'Payé'),
        ('gratuit_en_attente', 'Gratuit (en attente)'),
        ('gratuit', 'Gratuit'),
        ('reporte', 'Reporté'),
        ('rembourse', 'Remboursé'),
    ]

    MOYEN_PAIEMENT_CHOICES = [
        ('cash', 'Cash'),
        ('wave', 'Wave'),
        ('orange_money', 'Orange Money'),
        ('mtn_money', 'MTN Money'),
        ('moov_money', 'Moov Money'),
    ]

    numero = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Numéro du ticket"
    )
    voyage = models.ForeignKey(
        'voyages.Voyage',
        on_delete=models.CASCADE,
        related_name='billets',
        verbose_name="Voyage"
    )
    destination = models.ForeignKey(
        'destinations.Destination',
        on_delete=models.PROTECT,
        related_name='billets',
        verbose_name="Destination",
        null=True,
        blank=True
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billets',
        verbose_name="Client"
    )
    client_nom = models.CharField(max_length=200, verbose_name="Nom du client")
    client_telephone = models.CharField(max_length=20, verbose_name="Téléphone du client")
    numero_siege = models.PositiveIntegerField(null=True, blank=True, verbose_name="Numéro de siège")
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant (FCFA)"
    )
    statut = models.CharField(
        max_length=25,
        choices=STATUT_CHOICES,
        default='reserve',
        verbose_name="Statut"
    )
    moyen_paiement = models.CharField(
        max_length=20,
        choices=MOYEN_PAIEMENT_CHOICES,
        default='cash',
        verbose_name="Moyen de paiement"
    )
    guichetier = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='billets_vendus',
        verbose_name="Guichetier"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_paiement = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de paiement"
    )
    date_modification = models.DateTimeField(auto_now=True)
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Synchronisé le",
        help_text="Renseigné quand ce billet, créé sur un poste gare hors-ligne, a été remonté vers le serveur central."
    )

    # Champs pour la gestion des reports
    reporte_vers_billet = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billet_origine',
        verbose_name="Reporté vers le billet"
    )
    date_report = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date du report"
    )
    guichetier_report = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_effectues',
        verbose_name="Guichetier ayant effectué le report"
    )
    motif_report = models.TextField(
        blank=True,
        verbose_name="Motif du report"
    )

    class Meta:
        verbose_name = "Billet"
        verbose_name_plural = "Billets"
        ordering = ['-date_creation']
        # Un siège ne peut être vendu qu'une fois par voyage
        unique_together = ['voyage', 'numero_siege']

    def __str__(self):
        siege_str = f"Siège {self.numero_siege}" if self.numero_siege else "Remboursé"
        return f"{self.numero} - {self.client_nom} ({siege_str})"

    def clean(self):
        """Validation du billet."""
        if self.voyage_id and self.numero_siege:
            # Vérifier si le siège est disponible
            if not self.pk:  # Nouveau billet
                if not self.voyage.siege_disponible(self.numero_siege):
                    raise ValidationError(
                        f"Le siège {self.numero_siege} n'est pas disponible pour ce voyage."
                    )

    def save(self, *args, **kwargs):
        # Générer le numéro de ticket si non défini
        if not self.numero:
            self.numero = self.voyage.gare.generer_numero_ticket()

        # Définir le montant depuis la destination si non défini
        if not self.montant and self.destination:
            self.montant = self.destination.montant
        elif not self.montant:
            # Si pas de destination spécifiée, le montant doit être fourni explicitement
            raise ValueError("Le montant doit être spécifié si aucune destination n'est fournie")

        super().save(*args, **kwargs)

    def payer(self, moyen_paiement='cash'):
        """Marque le billet comme payé."""
        if self.statut == 'paye':
            return False

        self.statut = 'paye'
        self.moyen_paiement = moyen_paiement
        self.date_paiement = timezone.now()
        self.save(update_fields=['statut', 'moyen_paiement', 'date_paiement', 'date_modification'])
        return True

    @property
    def est_paye(self):
        return self.statut == 'paye'

    @property
    def est_reserve(self):
        return self.statut == 'reserve'

    def get_info_impression(self):
        """Retourne les informations pour l'impression du ticket."""
        gare = self.voyage.gare
        compagnie = gare.compagnie if gare else None

        # Mapping des moyens de paiement pour l'affichage
        moyen_paiement_display = {
            'cash': 'Cash',
            'wave': 'Wave',
            'orange_money': 'Orange Money',
            'mtn_money': 'MTN Money',
            'moov_money': 'Moov Money',
        }

        return {
            'public_id': str(self.public_id),
            'numero': self.numero,
            'numero_depart': self.voyage.numero_depart if hasattr(self.voyage, 'numero_depart') else 'N/A',
            'client_nom': self.client_nom,
            'numero_siege': self.numero_siege,
            'ligne': str(self.voyage.ligne),
            'destination': self.destination.ville_arrivee if self.destination else 'N/A',
            'date_depart': self.voyage.date_depart.strftime('%d/%m/%Y'),
            'heure_depart': self.voyage.heure_depart.strftime('%H:%M'),
            'periode': self.voyage.get_periode_display(),
            'montant': self.montant,
            'moyen_paiement': self.moyen_paiement,
            'moyen_paiement_display': moyen_paiement_display.get(self.moyen_paiement, 'Cash'),
            # Informations de la gare
            'gare_nom': gare.nom if gare else '',
            'gare_adresse': gare.adresse if gare else '',
            'gare_telephone': gare.telephone if gare else '',
            # Informations de la compagnie
            'compagnie_nom': compagnie.nom if compagnie else '',
            'compagnie_logo': compagnie.logo.url if compagnie and compagnie.logo else '',
            'utiliser_souche': compagnie.utiliser_souche if compagnie else False,
            'message_bas_ticket': compagnie.message_bas_ticket if compagnie else '',
            'statut': self.statut,
        }

    @classmethod
    def creer_billet(cls, voyage, client_nom, client_telephone, numero_siege, guichetier, destination=None, payer=True, moyen_paiement='cash'):
        """
        Crée un nouveau billet.

        Args:
            voyage: Instance du Voyage
            client_nom: Nom du client
            client_telephone: Téléphone du client
            numero_siege: Numéro du siège
            guichetier: Utilisateur qui crée le billet
            destination: Instance de la Destination choisie par le client
            payer: Si True, marque directement comme payé
            moyen_paiement: Moyen de paiement (cash, wave, orange_money, mtn_money, moov_money)

        Returns:
            Instance du Billet créé
        """
        if not voyage.siege_disponible(numero_siege):
            raise ValidationError(f"Le siège {numero_siege} n'est pas disponible.")

        # Vérifier que la destination est fournie
        if not destination:
            raise ValidationError("Une destination doit être spécifiée pour créer un billet.")

        billet = cls(
            voyage=voyage,
            destination=destination,
            client_nom=client_nom,
            client_telephone=client_telephone,
            numero_siege=numero_siege,
            montant=destination.montant,
            guichetier=guichetier,
            statut='paye' if payer else 'reserve',
            moyen_paiement=moyen_paiement if payer else 'cash',
            date_paiement=timezone.now() if payer else None
        )
        billet.save()
        return billet

    @classmethod
    def creer_billets_plage(cls, voyage, client_nom, client_telephone, siege_debut, siege_fin, guichetier, destination, payer=True, moyen_paiement='cash'):
        """
        Crée plusieurs billets pour une plage de sièges.
        Ignore les sièges déjà pris.

        Args:
            voyage: Instance du Voyage
            client_nom: Nom du client
            client_telephone: Téléphone du client
            siege_debut: Premier siège de la plage
            siege_fin: Dernier siège de la plage
            guichetier: Utilisateur qui crée les billets
            destination: Instance de la Destination (obligatoire)
            payer: Si True, marque directement comme payé
            moyen_paiement: Moyen de paiement (cash, wave, orange_money, mtn_money, moov_money)

        Returns:
            list: Liste des billets créés
        """
        if not destination:
            raise ValidationError("Une destination doit être spécifiée pour créer des billets.")

        billets_crees = []
        sieges_disponibles = voyage.get_sieges_disponibles()

        for numero_siege in range(siege_debut, siege_fin + 1):
            if numero_siege in sieges_disponibles:
                try:
                    billet = cls.creer_billet(
                        voyage=voyage,
                        client_nom=client_nom,
                        client_telephone=client_telephone,
                        numero_siege=numero_siege,
                        guichetier=guichetier,
                        destination=destination,
                        payer=payer,
                        moyen_paiement=moyen_paiement
                    )
                    billets_crees.append(billet)
                except ValidationError:
                    # Siège déjà pris entre temps, on continue
                    continue

        return billets_crees


class HistoriqueReport(models.Model):
    """
    Modèle pour tracer l'historique des reports de billets.
    """
    ancien_billet = models.ForeignKey(
        Billet,
        on_delete=models.CASCADE,
        related_name='historique_ancien',
        verbose_name="Ancien billet"
    )
    nouveau_billet = models.ForeignKey(
        Billet,
        on_delete=models.CASCADE,
        related_name='historique_nouveau',
        verbose_name="Nouveau billet"
    )
    ancien_voyage = models.ForeignKey(
        'voyages.Voyage',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_depuis',
        verbose_name="Ancien voyage"
    )
    nouveau_voyage = models.ForeignKey(
        'voyages.Voyage',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_vers',
        verbose_name="Nouveau voyage"
    )
    ancien_siege = models.PositiveIntegerField(verbose_name="Ancien siège")
    nouveau_siege = models.PositiveIntegerField(verbose_name="Nouveau siège")
    guichetier = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Guichetier"
    )
    motif = models.TextField(verbose_name="Motif du report")
    date_report = models.DateTimeField(auto_now_add=True, verbose_name="Date du report")

    class Meta:
        verbose_name = "Historique de report"
        verbose_name_plural = "Historiques de reports"
        ordering = ['-date_report']

    def __str__(self):
        return f"Report {self.ancien_billet.numero} → {self.nouveau_billet.numero} ({self.date_report.strftime('%d/%m/%Y %H:%M')})"


class DemandeRemboursement(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuvee', 'Approuvée'),
        ('rejetee', 'Rejetée'),
    ]

    billet = models.OneToOneField(
        Billet,
        on_delete=models.CASCADE,
        related_name='demande_remboursement',
        verbose_name="Billet"
    )
    demandee_par = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='demandes_remboursement_creees',
        verbose_name="Demandée par"
    )
    motif = models.TextField(verbose_name="Motif du remboursement")
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant à rembourser"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_attente',
        verbose_name="Statut"
    )
    date_demande = models.DateTimeField(auto_now_add=True, verbose_name="Date de la demande")
    traitee_par = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='remboursements_traites',
        verbose_name="Traitée par"
    )
    date_traitement = models.DateTimeField(null=True, blank=True, verbose_name="Date de traitement")
    commentaire = models.TextField(blank=True, verbose_name="Commentaire")

    class Meta:
        verbose_name = "Demande de remboursement"
        verbose_name_plural = "Demandes de remboursement"
        ordering = ['-date_demande']

    def __str__(self):
        return f"Remboursement {self.billet.numero} - {self.get_statut_display()}"


class DemandeTicketGratuit(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
    ]

    billet = models.OneToOneField(
        Billet,
        on_delete=models.CASCADE,
        related_name='demande_gratuit',
        verbose_name="Billet"
    )
    motif = models.TextField(blank=True, verbose_name="Motif")
    statut = models.CharField(
        max_length=15,
        choices=STATUT_CHOICES,
        default='en_attente',
        verbose_name="Statut"
    )
    demande_par = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='demandes_gratuit_creees',
        verbose_name="Demandée par"
    )
    traite_par = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demandes_gratuit_traitees',
        verbose_name="Traitée par"
    )
    date_demande = models.DateTimeField(auto_now_add=True, verbose_name="Date de la demande")
    date_traitement = models.DateTimeField(null=True, blank=True, verbose_name="Date de traitement")
    commentaire = models.TextField(blank=True, verbose_name="Commentaire (refus)")

    class Meta:
        verbose_name = "Demande de ticket gratuit"
        verbose_name_plural = "Demandes de tickets gratuits"
        ordering = ['-date_demande']

    def __str__(self):
        return f"Gratuit {self.billet.numero} — {self.get_statut_display()}"
