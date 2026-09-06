from django.db import models
from django.utils import timezone
from datetime import timedelta


class ProgrammeDepart(models.Model):
    """
    Modèle représentant un programme de départ récurrent.
    Permet la création automatique des voyages sur 7 jours.
    """
    PERIODE_CHOICES = [
        ('matin', 'Matinée'),
        ('soir', 'Soir'),
    ]

    JOURS_SEMAINE = [
        ('lun', 'Lundi'),
        ('mar', 'Mardi'),
        ('mer', 'Mercredi'),
        ('jeu', 'Jeudi'),
        ('ven', 'Vendredi'),
        ('sam', 'Samedi'),
        ('dim', 'Dimanche'),
    ]

    numero_depart = models.PositiveIntegerField(
        verbose_name="Numéro de départ",
        help_text="Numéro séquentiel du départ (ex: 1, 2, 3...)",
        default=1
    )
    gare = models.ForeignKey(
        'gares.Gare',
        on_delete=models.CASCADE,
        related_name='programmes',
        verbose_name="Gare de départ"
    )
    ligne = models.ForeignKey(
        'lignes.Ligne',
        on_delete=models.CASCADE,
        related_name='programmes',
        verbose_name="Ligne"
    )
    destination = models.ForeignKey(
        'destinations.Destination',
        on_delete=models.CASCADE,
        related_name='programmes',
        verbose_name="Destination",
        null=True,
        blank=True
    )
    periode = models.CharField(
        max_length=10,
        choices=PERIODE_CHOICES,
        verbose_name="Période"
    )
    heure_depart = models.TimeField(verbose_name="Heure de départ")
    vehicule_defaut = models.ForeignKey(
        'vehicules.Vehicule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='programmes',
        verbose_name="Véhicule par défaut"
    )
    jours_actifs = models.JSONField(
        verbose_name="Jours actifs",
        default=list,
        help_text="Liste des jours de la semaine où ce programme est actif"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Programme de départ"
        verbose_name_plural = "Programmes de départ"
        ordering = ['gare', 'heure_depart']

    def __str__(self):
        return f"{self.gare.code} - {self.ligne} - {self.heure_depart.strftime('%H:%M')} ({self.get_periode_display()})"

    def est_actif_jour(self, jour_semaine):
        """
        Vérifie si le programme est actif pour un jour donné.

        Args:
            jour_semaine: int (0=lundi, 6=dimanche) ou str ('lun', 'mar', etc.)
        """
        jours_map = {0: 'lun', 1: 'mar', 2: 'mer', 3: 'jeu', 4: 'ven', 5: 'sam', 6: 'dim'}

        if isinstance(jour_semaine, int):
            jour_semaine = jours_map.get(jour_semaine)

        return jour_semaine in self.jours_actifs

    def creer_voyages_semaine(self, jours_avance=7):
        """
        Crée les voyages pour les prochains jours selon la configuration.

        Args:
            jours_avance: nombre de jours à l'avance pour créer les voyages

        Returns:
            list: Liste des voyages créés
        """
        from apps.voyages.models import Voyage

        voyages_crees = []
        aujourd_hui = timezone.now().date()

        for i in range(jours_avance):
            date_voyage = aujourd_hui + timedelta(days=i)
            jour_semaine = date_voyage.weekday()  # 0=lundi, 6=dimanche

            if not self.est_actif_jour(jour_semaine):
                continue

            # Vérifier si le numéro de départ existe déjà pour cette gare et date
            numero_depart_existe = Voyage.objects.filter(
                gare=self.gare,
                date_depart=date_voyage,
                numero_depart=self.numero_depart
            ).exists()

            if numero_depart_existe:
                continue

            # Vérifier si le voyage existe déjà (éviter les doublons)
            voyage_existe = Voyage.objects.filter(
                gare=self.gare,
                ligne=self.ligne,
                date_depart=date_voyage,
                heure_depart=self.heure_depart,
                periode=self.periode,
                numero_depart=self.numero_depart
            ).exists()

            if voyage_existe:
                continue

            # Assigner le véhicule uniquement s'il n'est pas en réparation
            vehicule = self.vehicule_defaut
            if vehicule and vehicule.est_en_reparation:
                vehicule = None

            # Créer le voyage
            voyage = Voyage.objects.create(
                gare=self.gare,
                ligne=self.ligne,
                date_depart=date_voyage,
                heure_depart=self.heure_depart,
                periode=self.periode,
                numero_depart=self.numero_depart,
                vehicule=vehicule,
                cree_automatiquement=True,
                programme=self
            )
            voyages_crees.append(voyage)

        return voyages_crees

    @classmethod
    def creer_tous_voyages(cls, jours_avance=7):
        """
        Crée les voyages pour tous les programmes actifs.

        Returns:
            int: Nombre total de voyages créés
        """
        total_crees = 0
        programmes_actifs = cls.objects.filter(actif=True)

        for programme in programmes_actifs:
            voyages = programme.creer_voyages_semaine(jours_avance)
            total_crees += len(voyages)

        return total_crees
