from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.urls import reverse, NoReverseMatch


class Module(models.Model):
    cle         = models.SlugField(max_length=50, unique=True, verbose_name="Clé")
    nom         = models.CharField(max_length=100, verbose_name="Nom")
    description = models.CharField(max_length=200, blank=True, verbose_name="Description")
    icone       = models.CharField(max_length=100, default='bi-grid', verbose_name="Icône Bootstrap")
    url_name    = models.CharField(max_length=100, verbose_name="Nom d'URL Django")
    ordre       = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")
    actif       = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['ordre']
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return self.nom

    def get_url(self):
        try:
            return reverse(self.url_name)
        except NoReverseMatch:
            return '#'


class UtilisateurManager(BaseUserManager):
    """Manager personnalisé pour le modèle Utilisateur."""

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)


class Utilisateur(AbstractUser):
    """
    Modèle utilisateur personnalisé pour la gestion des rôles.
    """
    ROLE_CHOICES = [
        ('pdg', 'PDG'),
        ('super_admin', 'Super Administrateur'),
        ('manager', 'Manager'),
        ('comptable', 'Comptable'),
        ('chef_gare', 'Chef de Gare'),
        ('guichetier', 'Guichetier'),
        ('agent_courrier', 'Agent Courrier'),
    ]

    # Rôles à accès transversal : toutes les gares, tous les rapports, la
    # configuration globale. 'comptable' est un alias fonctionnel de 'manager'
    # (mêmes droits exactement) — voir aussi la propriété is_manager.
    ROLES_ACCES_GLOBAL = ('pdg', 'super_admin', 'manager', 'comptable')

    nom_complet = models.CharField(max_length=200, verbose_name="Nom complet")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='guichetier',
        verbose_name="Rôle"
    )
    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='utilisateurs',
        verbose_name="Gare"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    modules_autorises = models.ManyToManyField(
        'Module',
        blank=True,
        related_name='utilisateurs_autorises',
        verbose_name="Modules autorisés",
    )

    objects = UtilisateurManager()

    # Pas besoin d'email pour la connexion
    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['nom_complet']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['nom_complet']

    def __str__(self):
        return f"{self.nom_complet} ({self.get_role_display()})"

    @property
    def is_pdg(self):
        return self.role == 'pdg'

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_manager(self):
        # 'comptable' partage exactement les droits du manager (demande métier).
        return self.role in ('manager', 'comptable')

    @property
    def is_comptable(self):
        return self.role == 'comptable'

    @property
    def is_chef_gare(self):
        return self.role == 'chef_gare'

    @property
    def is_guichetier(self):
        return self.role == 'guichetier'

    @property
    def is_agent_courrier(self):
        return self.role == 'agent_courrier'

    @property
    def has_global_access(self):
        """Vérifie si l'utilisateur a accès à toutes les gares."""
        return self.role in self.ROLES_ACCES_GLOBAL

    def get_gares_accessibles(self):
        """Retourne les gares accessibles par l'utilisateur."""
        from apps.gares.models import Gare
        if self.has_global_access:
            return Gare.objects.filter(active=True)
        elif self.gare:
            return Gare.objects.filter(pk=self.gare.pk)
        return Gare.objects.none()


class Chauffeur(models.Model):
    """Modèle représentant un chauffeur de la compagnie."""

    SITUATION_MATRIMONIALE_CHOICES = [
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf/Veuve'),
    ]

    # Informations générales
    nom_complet = models.CharField(max_length=200, verbose_name="Nom complet")
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")
    numero_permis = models.CharField(max_length=50, verbose_name="Numéro de permis")

    # Identité
    numero_cni = models.CharField(max_length=50, blank=True, verbose_name="Numéro CNI")
    situation_matrimoniale = models.CharField(
        max_length=20,
        choices=SITUATION_MATRIMONIALE_CHOICES,
        blank=True,
        verbose_name="Situation matrimoniale"
    )
    nombre_enfants = models.PositiveIntegerField(default=0, verbose_name="Nombre d'enfants en charge")

    # Coordonnées
    telephone_2 = models.CharField(max_length=20, blank=True, verbose_name="Deuxième téléphone")
    lieu_habitation = models.CharField(max_length=200, blank=True, verbose_name="Lieu d'habitation")

    # Contact d'urgence
    personne_urgence = models.CharField(max_length=200, blank=True, verbose_name="Personne à contacter en cas d'urgence")
    telephone_urgence = models.CharField(max_length=20, blank=True, verbose_name="Téléphone personne d'urgence")

    # Informations professionnelles
    date_embauche = models.DateField(null=True, blank=True, verbose_name="Date d'embauche")
    salaire = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="Salaire")
    cv = models.FileField(upload_to='chauffeurs/cv/', blank=True, null=True, verbose_name="CV")

    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='chauffeurs',
        verbose_name="Compagnie"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chauffeur"
        verbose_name_plural = "Chauffeurs"
        ordering = ['nom_complet']

    def __str__(self):
        return self.nom_complet


class TypeDocumentChauffeur(models.Model):
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Type de document chauffeur"
        verbose_name_plural = "Types de documents chauffeur"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DocumentChauffeur(models.Model):
    chauffeur = models.ForeignKey(Chauffeur, on_delete=models.CASCADE, related_name='documents')
    type_document = models.ForeignKey(
        TypeDocumentChauffeur,
        on_delete=models.PROTECT,
        verbose_name="Type de document",
        related_name='documents'
    )
    nom = models.CharField(max_length=200, verbose_name="Nom du document", blank=True)
    fichier = models.FileField(upload_to='chauffeurs/documents/', verbose_name="Fichier")
    date_expiration = models.DateField(null=True, blank=True, verbose_name="Date d'expiration")
    date_ajout = models.DateTimeField(auto_now_add=True)
    ajoute_par = models.ForeignKey(
        'personnel.Utilisateur', on_delete=models.SET_NULL, null=True,
        related_name='documents_chauffeurs_ajoutes'
    )

    class Meta:
        verbose_name = "Document chauffeur"
        ordering = ['type_document__nom', '-date_ajout']

    def __str__(self):
        return f"{self.type_document.nom} — {self.chauffeur.nom_complet}"

    @property
    def type_nom(self):
        return self.type_document.nom if self.type_document else ''

    @property
    def est_expire(self):
        if self.date_expiration:
            from datetime import date
            return self.date_expiration < date.today()
        return False

    @property
    def expire_bientot(self):
        if self.date_expiration:
            from datetime import date, timedelta
            return date.today() <= self.date_expiration <= date.today() + timedelta(days=30)
        return False

    @property
    def extension(self):
        import os
        return os.path.splitext(self.fichier.name)[1].lower()

    @property
    def est_image(self):
        return self.extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']


class Convoyeur(models.Model):
    """Modèle représentant un convoyeur de la compagnie."""

    SITUATION_MATRIMONIALE_CHOICES = [
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf/Veuve'),
    ]

    # Informations générales
    nom_complet = models.CharField(max_length=200, verbose_name="Nom complet")
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")

    # Identité
    numero_cni = models.CharField(max_length=50, blank=True, verbose_name="Numéro CNI")
    situation_matrimoniale = models.CharField(
        max_length=20,
        choices=SITUATION_MATRIMONIALE_CHOICES,
        blank=True,
        verbose_name="Situation matrimoniale"
    )
    nombre_enfants = models.PositiveIntegerField(default=0, verbose_name="Nombre d'enfants en charge")

    # Coordonnées
    telephone_2 = models.CharField(max_length=20, blank=True, verbose_name="Deuxième téléphone")
    lieu_habitation = models.CharField(max_length=200, blank=True, verbose_name="Lieu d'habitation")

    # Contact d'urgence
    personne_urgence = models.CharField(max_length=200, blank=True, verbose_name="Personne à contacter en cas d'urgence")
    telephone_urgence = models.CharField(max_length=20, blank=True, verbose_name="Téléphone personne d'urgence")

    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='convoyeurs',
        verbose_name="Compagnie"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Convoyeur"
        verbose_name_plural = "Convoyeurs"
        ordering = ['nom_complet']

    def __str__(self):
        return self.nom_complet
