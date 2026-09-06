import hashlib
import secrets

from django.db import models


class Gare(models.Model):
    """Modèle représentant une gare routière."""
    nom = models.CharField(max_length=200, verbose_name="Nom de la gare")
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Code",
        help_text="Code unique pour la numérotation des tickets (ex: CKY, KND)"
    )
    ville = models.CharField(max_length=100, verbose_name="Ville")
    adresse = models.TextField(blank=True, verbose_name="Adresse")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='gares',
        verbose_name="Compagnie"
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # Compteur pour la numérotation des tickets
    dernier_numero_ticket = models.PositiveIntegerField(
        default=0,
        verbose_name="Dernier numéro de ticket"
    )
    mois_dernier_ticket = models.CharField(
        max_length=6,
        blank=True,
        default='',
        verbose_name="Mois du dernier ticket",
        help_text="Format YYYYMM pour la réinitialisation mensuelle"
    )

    # Configuration de l'impression thermique ESC/POS du poste (voir apps.guichet.impression)
    imprimante_nom = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Nom de l'imprimante (Windows)",
        help_text="Nom exact tel qu'affiché dans \"Périphériques et imprimantes\" sur ce poste."
    )
    imprimante_largeur_caracteres = models.PositiveIntegerField(
        default=42,
        verbose_name="Largeur du ticket (caractères)",
        help_text="42 convient à la plupart des imprimantes thermiques 80mm."
    )

    # Compteur pour la numérotation des codes colis (module Courrier)
    dernier_numero_colis = models.PositiveIntegerField(
        default=0,
        verbose_name="Dernier numéro de colis"
    )
    mois_dernier_colis = models.CharField(
        max_length=6,
        blank=True,
        default='',
        verbose_name="Mois du dernier colis",
        help_text="Format YYYYMM pour la réinitialisation mensuelle"
    )

    class Meta:
        verbose_name = "Gare"
        verbose_name_plural = "Gares"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code})"

    def get_chef_gare(self):
        """Retourne le chef de gare s'il existe."""
        return self.utilisateurs.filter(role='chef_gare', actif=True).first()

    def get_guichetiers(self):
        """Retourne tous les guichetiers actifs de cette gare."""
        return self.utilisateurs.filter(role='guichetier', actif=True)

    def generer_numero_ticket(self):
        """
        Génère un nouveau numéro de ticket unique pour cette gare.
        Format: {CODE}{ANNEE}{MOIS}{SEQUENCE:05d}
        Ex: CKY20260100001

        La séquence se réinitialise automatiquement chaque mois.
        Synchronise avec la BD pour éviter les doublons après migration.

        Les billets crees avant ce format (avec tirets, ex: CKY-202601-00001)
        gardent leur numero d'origine : aucune renumerotation retroactive.
        """
        from django.utils import timezone
        from apps.billets.models import Billet

        now = timezone.now()
        mois_actuel = now.strftime('%Y%m')
        prefixe = f"{self.code}{mois_actuel}"

        # Réinitialiser le compteur si on change de mois
        if self.mois_dernier_ticket != mois_actuel:
            self.dernier_numero_ticket = 0
            self.mois_dernier_ticket = mois_actuel

        # Vérifier le dernier numéro existant en BD pour ce mois
        # (sécurité après migration ou si compteur désynchronisé)
        dernier_billet = Billet.objects.filter(
            numero__startswith=prefixe
        ).order_by('-numero').first()

        if dernier_billet:
            try:
                # Extraire la séquence du numéro existant (ex: "...00044" -> 44)
                sequence_existante = int(dernier_billet.numero[len(prefixe):])
                # S'assurer que notre compteur est au moins égal
                if self.dernier_numero_ticket < sequence_existante:
                    self.dernier_numero_ticket = sequence_existante
            except (ValueError, IndexError):
                pass

        self.dernier_numero_ticket += 1
        self.save(update_fields=['dernier_numero_ticket', 'mois_dernier_ticket'])

        return f"{prefixe}{self.dernier_numero_ticket:05d}"

    def generer_numero_colis(self):
        """
        Génère un nouveau code colis unique pour cette gare.
        Format: COL-{CODE}{ANNEE}{MOIS}{SEQUENCE:05d}
        Ex: COL-CKY20260800001

        Même logique que generer_numero_ticket() (reset mensuel, sécurité
        anti-doublon via requête sur le dernier numéro en BD), avec le
        préfixe "COL-" pour qu'un code colis ne soit jamais confondu avec
        un numéro de billet, y compris à l'oral.
        """
        from django.utils import timezone
        from apps.courrier.models import Colis

        now = timezone.now()
        mois_actuel = now.strftime('%Y%m')
        prefixe = f"COL-{self.code}{mois_actuel}"

        if self.mois_dernier_colis != mois_actuel:
            self.dernier_numero_colis = 0
            self.mois_dernier_colis = mois_actuel

        dernier_colis = Colis.objects.filter(
            code_colis__startswith=prefixe
        ).order_by('-code_colis').first()

        if dernier_colis:
            try:
                sequence_existante = int(dernier_colis.code_colis[len(prefixe):])
                if self.dernier_numero_colis < sequence_existante:
                    self.dernier_numero_colis = sequence_existante
            except (ValueError, IndexError):
                pass

        self.dernier_numero_colis += 1
        self.save(update_fields=['dernier_numero_colis', 'mois_dernier_colis'])

        return f"{prefixe}{self.dernier_numero_colis:05d}"


class GareSyncToken(models.Model):
    """
    Jeton d'authentification machine-à-machine utilisé par un poste de guichet
    hors-ligne pour synchroniser ses données avec le serveur central (apps.sync).
    Le jeton en clair n'est jamais stocké : seul son hash est conservé.
    """
    gare = models.OneToOneField(
        Gare,
        on_delete=models.CASCADE,
        related_name='sync_token',
        verbose_name="Gare"
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    derniere_utilisation = models.DateTimeField(null=True, blank=True, verbose_name="Dernière utilisation")

    class Meta:
        verbose_name = "Jeton de synchronisation gare"
        verbose_name_plural = "Jetons de synchronisation gare"

    def __str__(self):
        return f"Jeton sync — {self.gare.nom}"

    @staticmethod
    def generer_pour(gare):
        """
        Génère un nouveau jeton en clair pour une gare (remplace l'ancien s'il existe)
        et retourne ce jeton en clair — c'est la seule fois où il est disponible.
        """
        token_clair = secrets.token_urlsafe(32)
        GareSyncToken.objects.update_or_create(
            gare=gare,
            defaults={
                'token_hash': hashlib.sha256(token_clair.encode()).hexdigest(),
                'actif': True,
            }
        )
        return token_clair

    @staticmethod
    def verifier(token_clair):
        """Retourne la Gare correspondant au jeton fourni (actif), ou None."""
        if not token_clair:
            return None
        token_hash = hashlib.sha256(token_clair.encode()).hexdigest()
        try:
            jeton = GareSyncToken.objects.select_related('gare').get(
                token_hash=token_hash, actif=True
            )
        except GareSyncToken.DoesNotExist:
            return None

        from django.utils import timezone
        jeton.derniere_utilisation = timezone.now()
        jeton.save(update_fields=['derniere_utilisation'])
        return jeton.gare
