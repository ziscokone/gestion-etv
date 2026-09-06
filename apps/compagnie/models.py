from django.db import models


class Compagnie(models.Model):
    """
    Modèle représentant la compagnie de transport.
    Une seule instance de ce modèle devrait exister (singleton).
    """
    nom = models.CharField(max_length=200, verbose_name="Nom de la compagnie")
    logo = models.ImageField(
        upload_to='logos/',
        blank=True,
        null=True,
        verbose_name="Logo"
    )
    nom_pdg = models.CharField(max_length=200, verbose_name="Nom du PDG")
    adresse = models.TextField(blank=True, verbose_name="Adresse")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    utiliser_souche = models.BooleanField(
        default=False,
        verbose_name="Imprimer avec souche",
        help_text="Si activé, chaque ticket payé sera imprimé avec une souche détachable pour la compagnie"
    )
    message_bas_ticket = models.TextField(
        blank=True,
        verbose_name="Message bas de ticket",
        help_text="Message affiché au bas du ticket client. Ex: Soyez à la gare 30 min avant le départ. BON VOYAGE !"
    )

    # ── Alertes documents véhicules ──────────────────────────────────
    # Un document non "actif" est totalement ignoré par les alertes, même si
    # une date d'expiration existe encore en base pour un véhicule (rien
    # n'est supprimé, juste ignoré). Les valeurs par défaut (30 / 10 jours,
    # actif=True) reproduisent exactement le comportement codé en dur
    # historiquement, pour ne rien changer tant que personne n'y touche.
    alerte_assurance_active = models.BooleanField(
        default=True, verbose_name="L'assurance expire"
    )
    alerte_assurance_jours = models.PositiveIntegerField(
        default=30, verbose_name="Alerter X jours avant expiration (assurance)"
    )
    alerte_assurance_urgent_jours = models.PositiveIntegerField(
        default=10, verbose_name="Seuil urgent en jours (assurance)"
    )

    alerte_visite_technique_active = models.BooleanField(
        default=True, verbose_name="La visite technique expire"
    )
    alerte_visite_technique_jours = models.PositiveIntegerField(
        default=30, verbose_name="Alerter X jours avant expiration (visite technique)"
    )
    alerte_visite_technique_urgent_jours = models.PositiveIntegerField(
        default=10, verbose_name="Seuil urgent en jours (visite technique)"
    )

    alerte_carte_grise_active = models.BooleanField(
        default=True, verbose_name="La carte grise expire"
    )
    alerte_carte_grise_jours = models.PositiveIntegerField(
        default=30, verbose_name="Alerter X jours avant expiration (carte grise)"
    )
    alerte_carte_grise_urgent_jours = models.PositiveIntegerField(
        default=10, verbose_name="Seuil urgent en jours (carte grise)"
    )

    alerte_licence_transport_active = models.BooleanField(
        default=True, verbose_name="La licence de transport expire"
    )
    alerte_licence_transport_jours = models.PositiveIntegerField(
        default=30, verbose_name="Alerter X jours avant expiration (licence transport)"
    )
    alerte_licence_transport_urgent_jours = models.PositiveIntegerField(
        default=10, verbose_name="Seuil urgent en jours (licence transport)"
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # Description des 4 documents véhicule surveillés : (clé, libellé, champ date sur Vehicule)
    DOCUMENTS_VEHICULE = [
        ('assurance', 'Assurance', 'date_expiration_assurance'),
        ('visite_technique', 'Visite technique', 'date_expiration_visite_technique'),
        ('carte_grise', 'Carte grise', 'date_expiration_carte_grise'),
        ('licence_transport', 'Licence de transport', 'date_expiration_licence_transport'),
    ]

    class Meta:
        verbose_name = "Compagnie"
        verbose_name_plural = "Compagnie"

    def __str__(self):
        return self.nom

    def get_documents_alertes_actifs(self):
        """
        Retourne la liste des documents véhicules à surveiller (ceux marqués
        comme expirant), avec leur champ date et leurs seuils. Un document
        désactivé est absent de cette liste et donc ignoré par les alertes.
        """
        resultat = []
        for cle, label, champ_date in self.DOCUMENTS_VEHICULE:
            if getattr(self, f'alerte_{cle}_active'):
                resultat.append({
                    'champ_date': champ_date,
                    'label': label,
                    'seuil_alerte': getattr(self, f'alerte_{cle}_jours'),
                    'seuil_urgent': getattr(self, f'alerte_{cle}_urgent_jours'),
                })
        return resultat

    def save(self, *args, **kwargs):
        """Assure qu'il n'y a qu'une seule instance de Compagnie."""
        if not self.pk and Compagnie.objects.exists():
            existing = Compagnie.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        """Retourne l'instance unique de la compagnie ou None."""
        return cls.objects.first()
