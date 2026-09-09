from django.db import models


class SyncableModel(models.Model):
    """Base des modèles remontés d'un poste gare hors-ligne vers le serveur central.

    Le poste gare n'envoie au central (``sync_push``) que les enregistrements dont
    ``synced_at`` est ``NULL``. Sans précaution, un objet déjà remonté une fois ne
    repart jamais : une réservation payée après coup, un voyage passé à
    « terminé », une recette bagages saisie plus tard resteraient invisibles côté
    central.

    Ce mixin corrige ça : **toute écriture qui n'est pas le fait de la couche de
    synchronisation** (laquelle renseigne explicitement ``synced_at``) remet
    ``synced_at`` à ``NULL`` sur un objet déjà en base. Le prochain ``sync_push``
    renvoie donc l'objet avec ses nouvelles valeurs ; les fonctions ``_upsert_*``
    de ``apps.sync.services`` savent déjà appliquer ces mises à jour côté central.

    Anti-boucle : après un push réussi, ``apps.sync.client._marquer_synchronise``
    repositionne ``synced_at`` via ``QuerySet.update()``, qui n'appelle pas
    ``save()`` — ce mixin n'est donc pas déclenché et il n'y a pas de va-et-vient.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)

        ecriture_de_synchro = update_fields is not None and 'synced_at' in update_fields
        maj_partielle_vide = update_fields is not None and len(update_fields) == 0

        if (
            not self._state.adding
            and self.synced_at is not None
            and not ecriture_de_synchro
            and not maj_partielle_vide
        ):
            self.synced_at = None
            if update_fields is not None:
                update_fields.add('synced_at')
                kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)
