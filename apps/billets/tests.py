from datetime import date

from django.test import TestCase

from .models import Billet


class RemiseBilletTests(TestCase):
    """Application de la remise à la vente : montant net = tarif − remise,
    par billet (y compris plage), jamais sur un ticket fidélité ni une réservation."""

    def setUp(self):
        from datetime import time
        from decimal import Decimal
        from apps.compagnie.models import Compagnie
        from apps.gares.models import Gare
        from apps.lignes.models import Ligne
        from apps.destinations.models import Destination
        from apps.vehicules.models import ModeleVehicule, Vehicule
        from apps.voyages.models import Voyage
        from apps.personnel.models import Utilisateur
        self.Decimal = Decimal
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        self.gare = Gare.objects.create(nom='G', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(nom='L', gare=self.gare, ville_depart='A', ville_arrivee='B', compagnie=self.compagnie)
        self.dest = Destination.objects.create(gare=self.gare, ligne=self.ligne, ville_arrivee='B', montant=10000)
        modele = ModeleVehicule.objects.create(nom='Bus', marque='T', capacite=50)
        veh = Vehicule.objects.create(immatriculation='AA-1-BB', modele=modele, compagnie=self.compagnie)
        self.voyage = Voyage.objects.create(gare=self.gare, ligne=self.ligne, date_depart=date.today(),
                                            heure_depart=time(8, 0), periode='matin', vehicule=veh)
        self.g = Utilisateur.objects.create_user(username='g', password='x', nom_complet='G', role='guichetier', gare=self.gare)

    def test_vente_unitaire_avec_remise(self):
        b = Billet.creer_billet(self.voyage, 'Awa', '0700000001', 1, self.g, destination=self.dest, remise=1000)
        self.assertEqual(b.montant, self.Decimal('9000'))
        self.assertEqual(b.remise, self.Decimal('1000'))
        self.assertEqual(b.tarif_plein, self.Decimal('10000'))

    def test_plage_remise_sur_chaque_billet(self):
        billets = Billet.creer_billets_plage(self.voyage, 'Awa', '0700000001', 1, 4, self.g, self.dest, remise=500)
        self.assertEqual(len(billets), 4)
        for b in billets:
            self.assertEqual(b.montant, self.Decimal('9500'))
            self.assertEqual(b.remise, self.Decimal('500'))
        self.assertEqual(sum(b.montant for b in billets), self.Decimal('38000'))

    def test_reservation_ignore_la_remise(self):
        b = Billet.creer_billet(self.voyage, 'Awa', '0700000001', 1, self.g, destination=self.dest, payer=False, remise=1000)
        self.assertEqual(b.statut, 'reserve')
        self.assertEqual(b.montant, self.Decimal('10000'))
        self.assertEqual(b.remise, self.Decimal('0'))

    def test_remise_plafonnee_au_tarif(self):
        b = Billet.creer_billet(self.voyage, 'Awa', '0700000001', 1, self.g, destination=self.dest, remise=99999)
        self.assertEqual(b.montant, self.Decimal('0'))
        self.assertEqual(b.remise, self.Decimal('10000'))

    def test_fidelite_jamais_de_remise(self):
        from decimal import Decimal
        from apps.clients.models import Client
        self.compagnie.fidelite_active = True
        self.compagnie.fidelite_seuil_voyages = 2
        self.compagnie.save()
        cl = Client.objects.create(telephone='0700000009', nom_complet='Yao', categorie='particulier')
        # 2 payés (avec remise) puis le 3e = fidélité (0 F, remise 0)
        billets = Billet.creer_billets_avec_fidelite(
            self.voyage, cl, 'Yao', '0700000009', [1, 2, 3], self.g, self.dest, remise=1000,
        )
        self.assertEqual([b.statut for b in billets], ['paye', 'paye', 'fidelite'])
        self.assertEqual(billets[0].montant, Decimal('9000'))
        self.assertEqual(billets[0].remise, Decimal('1000'))
        self.assertEqual(billets[2].montant, Decimal('0'))
        self.assertEqual(billets[2].remise, Decimal('0'))
