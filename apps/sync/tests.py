"""
Tests du mixin ``core.models.SyncableModel`` : une modification locale d'un
enregistrement déjà remonté au central doit remettre ``synced_at`` à ``NULL``
pour qu'il reparte au prochain ``sync_push``, sauf si l'écriture provient de la
couche de synchronisation elle-même.
"""
from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.billets.models import Billet
from apps.clients.models import Client
from apps.comptabilite.models import Depense, TypeDepense
from apps.compagnie.models import Compagnie
from apps.destinations.models import Destination
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur
from apps.vehicules.models import ModeleVehicule, Vehicule
from apps.voyages.models import Voyage


class SyncableModelResetTests(TestCase):
    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        self.gare = Gare.objects.create(nom='G', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='L', gare=self.gare, ville_depart='A', ville_arrivee='B', compagnie=self.compagnie,
        )
        self.dest = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='B', montant=10000,
        )
        modele = ModeleVehicule.objects.create(nom='Bus', marque='T', capacite=50)
        self.veh = Vehicule.objects.create(
            immatriculation='AA-1-BB', modele=modele, compagnie=self.compagnie,
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=self.veh,
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='g', password='x', nom_complet='G', role='guichetier', gare=self.gare,
        )

    def _billet_synchronise(self, **kwargs):
        billet = Billet.creer_billet(
            self.voyage, 'Awa', '0700000001', 1, self.guichetier,
            destination=self.dest, payer=False, **kwargs,
        )
        Billet.objects.filter(pk=billet.pk).update(synced_at=timezone.now())
        billet.refresh_from_db()
        return billet

    # ── Le cœur : une modif locale invalide synced_at ────────────────────
    def test_paiement_dune_reservation_deja_synchronisee(self):
        billet = self._billet_synchronise()
        self.assertIsNotNone(billet.synced_at)

        billet.payer('cash')

        billet.refresh_from_db()
        self.assertIsNone(billet.synced_at, "le paiement doit forcer un renvoi au central")
        self.assertEqual(billet.statut, 'paye')

    def test_save_complet_invalide_synced_at(self):
        billet = self._billet_synchronise()
        billet.numero_siege = 2
        billet.save()
        billet.refresh_from_db()
        self.assertIsNone(billet.synced_at)

    def test_voyage_termine_invalide_synced_at(self):
        Voyage.objects.filter(pk=self.voyage.pk).update(synced_at=timezone.now())
        self.voyage.refresh_from_db()

        self.voyage.statut = 'termine'
        self.voyage.save(update_fields=['statut', 'date_modification'])

        self.voyage.refresh_from_db()
        self.assertIsNone(self.voyage.synced_at)

    def test_client_modifie_invalide_synced_at(self):
        client = Client.objects.create(telephone='0700000002', nom_complet='Awa K.')
        Client.objects.filter(pk=client.pk).update(synced_at=timezone.now())
        client.refresh_from_db()

        client.nom_complet = 'Awa Koné'
        client.save()

        client.refresh_from_db()
        self.assertIsNone(client.synced_at)

    def test_depense_modifiee_invalide_synced_at(self):
        type_dep = TypeDepense.objects.create(code='carburant', nom='Carburant', compagnie=self.compagnie)
        depense = Depense.objects.create(
            voyage=self.voyage, type_depense=type_dep, montant=5000, guichetier=self.guichetier,
        )
        Depense.objects.filter(pk=depense.pk).update(synced_at=timezone.now())
        depense.refresh_from_db()

        depense.montant = 6000
        depense.save()

        depense.refresh_from_db()
        self.assertIsNone(depense.synced_at)

    # ── Les garde-fous : la synchro elle-même ne se ré-invalide pas ──────
    def test_ecriture_avec_synced_at_explicite_est_preservee(self):
        billet = self._billet_synchronise()
        billet.statut = 'paye'
        billet.synced_at = timezone.now()
        billet.save(update_fields=['statut', 'synced_at', 'date_modification'])
        billet.refresh_from_db()
        self.assertIsNotNone(billet.synced_at, "une écriture de synchro ne doit pas se ré-invalider")

    def test_update_queryset_ne_declenche_pas_le_mixin(self):
        billet = self._billet_synchronise()
        # _marquer_synchronise procède par .update() : ne doit pas toucher synced_at
        Billet.objects.filter(pk=billet.pk).update(statut='paye')
        billet.refresh_from_db()
        self.assertIsNotNone(billet.synced_at)

    def test_creation_avec_synced_at_est_preservee(self):
        client = Client.objects.create(
            telephone='0700000003', nom_complet='Sync', synced_at=timezone.now(),
        )
        client.refresh_from_db()
        self.assertIsNotNone(client.synced_at)

    def test_upsert_billet_central_ne_reinvalide_pas(self):
        """Côté central, _upsert_billet met à jour un billet et le laisse marqué synchronisé."""
        from apps.sync import services

        billet = self._billet_synchronise()
        self.voyage.public_id  # s'assure qu'il existe
        payload = {
            'public_id': str(billet.public_id),
            'numero': billet.numero,
            'voyage_public_id': str(self.voyage.public_id),
            'destination_id': self.dest.id,
            'client_public_id': None,
            'client_nom': billet.client_nom,
            'client_telephone': billet.client_telephone,
            'numero_siege': billet.numero_siege,
            'montant': str(billet.montant),
            'statut': 'paye',
            'moyen_paiement': 'cash',
            'guichetier_id': self.guichetier.id,
            'date_paiement': timezone.now().isoformat(),
        }
        services._upsert_billet(payload, self.gare)

        billet.refresh_from_db()
        self.assertEqual(billet.statut, 'paye')
        self.assertIsNotNone(billet.synced_at)
