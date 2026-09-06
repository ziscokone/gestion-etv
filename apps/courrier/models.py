import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

DELAI_RETRAIT_JOURS = 30


class TypeColis(models.Model):
    """
    Catégorie de colis avec son tarif indicatif (ex: Enveloppe/Document,
    Petit colis, Colis moyen, Colis volumineux). Le montant reste toujours
    modifiable au cas par cas à l'enregistrement.
    """
    nom = models.CharField(max_length=100, verbose_name="Nom")
    tarif_indicatif = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Tarif indicatif (FCFA)"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='types_colis',
        verbose_name="Compagnie"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Type de colis"
        verbose_name_plural = "Types de colis"
        ordering = ['ordre', 'nom']
        unique_together = ['compagnie', 'nom']

    def __str__(self):
        return self.nom

    def peut_etre_supprime(self):
        return not self.colis.exists()


class Colis(models.Model):
    """
    Une expédition de colis entre deux gares de la compagnie.
    """
    STATUT_CHOICES = [
        ('enregistre', 'Enregistré'),
        ('en_transit', 'En transit'),
        ('arrive', 'Arrivé'),
        ('receptionne', 'Réceptionné'),
        ('retire', 'Retiré'),
        ('non_reclame', 'Non réclamé'),
        ('retourne', 'Retourné à l\'expéditeur'),
        ('annule', 'Annulé'),
    ]

    QUI_PAIE_CHOICES = [
        ('expediteur', 'Expéditeur (port payé)'),
        ('destinataire', 'Destinataire (port dû)'),
    ]

    MOYEN_PAIEMENT_CHOICES = [
        ('cash', 'Cash'),
        ('wave', 'Wave'),
        ('orange_money', 'Orange Money'),
        ('mtn_money', 'MTN Money'),
        ('moov_money', 'Moov Money'),
    ]

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Utilisé dans les URL à la place de l'identifiant interne, pour ne pas exposer le volume de colis."
    )
    code_colis = models.CharField(max_length=30, unique=True, verbose_name="Code colis")
    code_retrait = models.CharField(max_length=10, verbose_name="Code de retrait")

    gare_origine = models.ForeignKey(
        'gares.Gare',
        on_delete=models.PROTECT,
        related_name='colis_origine',
        verbose_name="Gare d'origine"
    )
    gare_destination = models.ForeignKey(
        'gares.Gare',
        on_delete=models.PROTECT,
        related_name='colis_destination',
        verbose_name="Gare de destination"
    )
    voyage = models.ForeignKey(
        'voyages.Voyage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis',
        verbose_name="Voyage",
        help_text="Renseigné uniquement au chargement — un lien logistique, jamais financier (la recette courrier reste indépendante de la recette du voyage)."
    )

    expediteur = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_envoyes',
        verbose_name="Expéditeur"
    )
    expediteur_nom = models.CharField(max_length=200, verbose_name="Nom de l'expéditeur")
    expediteur_telephone = models.CharField(max_length=20, verbose_name="Téléphone de l'expéditeur")

    destinataire = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_recus',
        verbose_name="Destinataire"
    )
    destinataire_nom = models.CharField(max_length=200, verbose_name="Nom du destinataire")
    destinataire_telephone = models.CharField(max_length=20, verbose_name="Téléphone du destinataire")

    type_colis = models.ForeignKey(
        TypeColis,
        on_delete=models.PROTECT,
        related_name='colis',
        verbose_name="Type de colis"
    )
    description = models.TextField(blank=True, verbose_name="Description du contenu")
    valeur_declaree = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Valeur déclarée (FCFA)"
    )

    montant = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Montant (FCFA)")
    qui_paie = models.CharField(max_length=15, choices=QUI_PAIE_CHOICES, default='expediteur', verbose_name="Qui paie")
    moyen_paiement = models.CharField(max_length=20, choices=MOYEN_PAIEMENT_CHOICES, default='cash', verbose_name="Moyen de paiement")
    paye = models.BooleanField(default=False, verbose_name="Payé")
    date_paiement = models.DateTimeField(null=True, blank=True, verbose_name="Date de paiement")

    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='enregistre', verbose_name="Statut")

    guichetier_enregistrement = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='colis_enregistres',
        verbose_name="Enregistré par"
    )
    guichetier_chargement = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_charges',
        verbose_name="Chargé par"
    )
    guichetier_reception = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_receptionnes',
        verbose_name="Réceptionné par"
    )
    guichetier_retrait = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_retires',
        verbose_name="Retiré par"
    )
    piece_identite_retrait = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° CNI présenté au retrait",
    )
    retirant = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colis_retires_pour',
        verbose_name="Retirant",
        help_text="Personne qui s'est effectivement présentée au retrait — le destinataire, ou un mandataire."
    )
    retirant_nom = models.CharField(max_length=200, blank=True, verbose_name="Nom du retirant")
    retirant_telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du retirant")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_chargement = models.DateTimeField(null=True, blank=True, verbose_name="Date de chargement")
    date_arrivee = models.DateTimeField(null=True, blank=True, verbose_name="Date d'arrivée")
    date_reception = models.DateTimeField(null=True, blank=True, verbose_name="Date de réception")
    date_limite_retrait = models.DateTimeField(null=True, blank=True, verbose_name="Date limite de retrait")
    date_retrait = models.DateTimeField(null=True, blank=True, verbose_name="Date de retrait")
    date_modification = models.DateTimeField(auto_now=True)

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Colis"
        verbose_name_plural = "Colis"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.code_colis} — {self.expediteur_nom} → {self.destinataire_nom}"

    def save(self, *args, **kwargs):
        if not self.code_colis:
            self.code_colis = self.gare_origine.generer_numero_colis()
        if not self.code_retrait:
            self.code_retrait = self._generer_code_retrait()
        super().save(*args, **kwargs)

    @staticmethod
    def _generer_code_retrait():
        """Code secret à 6 chiffres, indépendant du code colis — voir Colis.code_retrait."""
        for _ in range(10):
            code = ''.join(secrets.choice('0123456789') for _ in range(6))
            if not Colis.objects.filter(
                code_retrait=code, statut__in=['enregistre', 'en_transit', 'arrive', 'receptionne']
            ).exists():
                return code
        return code

    def enregistrer_transition(self, nouveau_statut, agent=None, gare=None, note=''):
        """Applique un changement de statut et journalise la transition."""
        ancien_statut = self.statut
        self.statut = nouveau_statut
        HistoriqueStatutColis.objects.create(
            colis=self,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            agent=agent,
            gare=gare,
            note=note,
        )

    def marquer_en_transit(self, voyage, agent):
        self.voyage = voyage
        self.date_chargement = timezone.now()
        self.guichetier_chargement = agent
        self.enregistrer_transition('en_transit', agent=agent, gare=voyage.gare)
        self.save(update_fields=[
            'voyage', 'date_chargement', 'guichetier_chargement', 'statut', 'date_modification'
        ])

    def marquer_arrive(self):
        self.date_arrivee = timezone.now()
        self.date_limite_retrait = self.date_arrivee + timedelta(days=DELAI_RETRAIT_JOURS)
        self.enregistrer_transition('arrive', gare=self.gare_destination)
        self.save(update_fields=[
            'date_arrivee', 'date_limite_retrait', 'statut', 'date_modification'
        ])

    def marquer_receptionne(self, agent):
        """
        Confirmation manuelle, par la gare de destination, qu'elle a
        physiquement le colis en main. Tant que ce n'est pas fait, le retrait
        reste bloqué (voir RetraitColisView).

        Peut se faire directement depuis 'en_transit' — le passage par
        'arrive' (automatique quand le Voyage est marqué "Terminé", voir
        signals.py) est une action séparée de la gare d'origine, pas
        toujours faite en pratique. La gare de destination n'a pas à
        attendre ça : elle constate elle-même que le colis est arrivé. Dans
        ce cas, date_arrivee/date_limite_retrait sont renseignées ici.
        """
        update_fields = ['date_reception', 'guichetier_reception', 'statut', 'date_modification']
        if not self.date_arrivee:
            self.date_arrivee = timezone.now()
            self.date_limite_retrait = self.date_arrivee + timedelta(days=DELAI_RETRAIT_JOURS)
            update_fields += ['date_arrivee', 'date_limite_retrait']
        self.date_reception = timezone.now()
        self.guichetier_reception = agent
        self.enregistrer_transition('receptionne', agent=agent, gare=self.gare_destination)
        self.save(update_fields=update_fields)

    def marquer_retire(self, agent, piece_identite, retirant=None, retirant_nom='', retirant_telephone='', moyen_paiement=None):
        self.date_retrait = timezone.now()
        self.guichetier_retrait = agent
        self.piece_identite_retrait = piece_identite
        self.retirant = retirant
        self.retirant_nom = retirant_nom
        self.retirant_telephone = retirant_telephone
        update_fields = [
            'date_retrait', 'guichetier_retrait', 'piece_identite_retrait',
            'retirant', 'retirant_nom', 'retirant_telephone', 'statut', 'date_modification'
        ]
        if not self.paye:
            self.paye = True
            self.date_paiement = timezone.now()
            if moyen_paiement:
                self.moyen_paiement = moyen_paiement
            update_fields += ['paye', 'date_paiement', 'moyen_paiement']
        self.enregistrer_transition('retire', agent=agent, gare=self.gare_destination)
        self.save(update_fields=update_fields)

    def annuler(self, agent, note=''):
        self.enregistrer_transition('annule', agent=agent, gare=self.gare_origine, note=note)
        self.save(update_fields=['statut', 'date_modification'])

    @property
    def code_retrait_verrouille(self):
        """Une fois retiré, le code de retrait ne doit plus être affiché nulle part."""
        return self.statut in ['retire', 'annule']


class HistoriqueStatutColis(models.Model):
    """Piste d'audit : une ligne par changement de statut d'un colis."""
    colis = models.ForeignKey(Colis, on_delete=models.CASCADE, related_name='historique', verbose_name="Colis")
    ancien_statut = models.CharField(max_length=15, choices=Colis.STATUT_CHOICES, blank=True, verbose_name="Ancien statut")
    nouveau_statut = models.CharField(max_length=15, choices=Colis.STATUT_CHOICES, verbose_name="Nouveau statut")
    agent = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Agent"
    )
    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Gare"
    )
    note = models.TextField(blank=True, verbose_name="Note")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        verbose_name = "Historique de statut colis"
        verbose_name_plural = "Historiques de statut colis"
        ordering = ['-date']

    def __str__(self):
        return f"{self.colis.code_colis} : {self.ancien_statut} → {self.nouveau_statut} ({self.date:%d/%m/%Y %H:%M})"
