import uuid

from django.db import models
from django.core.exceptions import ValidationError


class TypeDepense(models.Model):
    """
    Modèle représentant un type de dépense pour les voyages.
    Exemples: Carburant, Frais Chauffeur, Frais de Route, Ration, Divers
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Code unique du type de dépense (ex: carburant, frais_chauffeur)"
    )
    nom = models.CharField(
        max_length=100,
        verbose_name="Nom",
        help_text="Nom affiché du type de dépense (ex: Carburant, Frais Chauffeur)"
    )
    description_obligatoire = models.BooleanField(
        default=False,
        verbose_name="Description obligatoire",
        help_text="Si coché, une description sera obligatoire lors de la saisie"
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver pour masquer ce type sans le supprimer"
    )
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Ordre d'affichage dans les formulaires (0 = premier)"
    )
    compagnie = models.ForeignKey(
        'compagnie.Compagnie',
        on_delete=models.CASCADE,
        related_name='types_depenses',
        verbose_name="Compagnie"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Type de dépense"
        verbose_name_plural = "Types de dépenses"
        ordering = ['ordre', 'nom']
        unique_together = ['compagnie', 'code']

    def __str__(self):
        return self.nom

    def peut_etre_supprime(self):
        """Vérifie si le type peut être supprimé (pas de dépenses associées)."""
        return not self.depenses.exists()

    def delete(self, *args, **kwargs):
        """Empêche la suppression si des dépenses sont associées."""
        if not self.peut_etre_supprime():
            raise ValidationError(
                f"Impossible de supprimer '{self.nom}' car des dépenses utilisent ce type."
            )
        super().delete(*args, **kwargs)


class Depense(models.Model):
    """
    Modèle représentant une dépense liée à un voyage.
    Permet de suivre toutes les sorties de caisse pour chaque voyage.
    """
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Identifiant public",
        help_text="Identifiant stable utilisé pour la synchronisation depuis un poste gare hors-ligne."
    )
    voyage = models.ForeignKey(
        'voyages.Voyage',
        on_delete=models.CASCADE,
        related_name='depenses',
        verbose_name="Voyage"
    )
    type_depense = models.ForeignKey(
        TypeDepense,
        on_delete=models.PROTECT,
        related_name='depenses',
        verbose_name="Type de dépense",
        help_text="Type de dépense (Carburant, Frais chauffeur, etc.)"
    )
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant (FCFA)",
        help_text="Montant de la dépense en FCFA"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Description détaillée (obligatoire pour certains types)"
    )
    guichetier = models.ForeignKey(
        'personnel.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='depenses_saisies',
        verbose_name="Saisi par",
        help_text="Guichetier qui a enregistré cette dépense"
    )
    reparation = models.ForeignKey(
        'vehicules.ReparationVehicule',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='depense_source',
        verbose_name="Réparation liée",
        help_text="Réparation créée depuis cette dépense"
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de saisie")
    date_modification = models.DateTimeField(auto_now=True)
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Synchronisé le",
        help_text="Renseigné quand cette dépense, saisie sur un poste gare hors-ligne, a été remontée vers le serveur central."
    )

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.type_depense.nom} - {self.montant} FCFA ({self.voyage})"

    def clean(self):
        """Validation : description obligatoire si le type l'exige."""
        super().clean()
        if self.type_depense and self.type_depense.description_obligatoire:
            if self.montant and self.montant > 0 and not self.description:
                raise ValidationError({
                    'description': f"La description est obligatoire pour le type '{self.type_depense.nom}'."
                })

    def save(self, *args, **kwargs):
        """Validation avant sauvegarde."""
        self.full_clean()
        super().save(*args, **kwargs)

    def a_reparation_liee(self):
        """Vérifie si cette dépense a une réparation associée."""
        return self.reparation is not None

    def peut_creer_reparation(self):
        """Vérifie si on peut créer une réparation depuis cette dépense."""
        # Vérifier par code OU par nom (pour compatibilité avec types créés manuellement)
        is_reparation_type = (
            self.type_depense.code == 'reparation' or
            'réparation' in self.type_depense.nom.lower() or
            'reparation' in self.type_depense.nom.lower()
        )
        return (
            is_reparation_type and
            not self.a_reparation_liee() and
            self.voyage.vehicule is not None
        )
