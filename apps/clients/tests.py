from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.compagnie.models import Compagnie
from apps.courrier.models import Colis, TypeColis
from apps.gares.models import Gare
from apps.personnel.models import Utilisateur

from .models import Client


class ClientListAjaxTests(TestCase):
    """Filtrage en direct de la liste des clients (recherche automatique)."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier',
        )
        self.jean = Client.objects.create(telephone='0100000001', nom_complet='Jean Traoré')
        self.marie = Client.objects.create(telephone='0100000002', nom_complet='Marie Diallo')

    def test_filtre_par_recherche(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('clients:client_list_ajax'), {'search': 'Jean'})
        self.assertContains(response, 'Jean Traoré')
        self.assertNotContains(response, 'Marie Diallo')

    def test_sans_filtre_retourne_tout(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('clients:client_list_ajax'))
        self.assertContains(response, 'Jean Traoré')
        self.assertContains(response, 'Marie Diallo')


class ClientDetailCourrierTests(TestCase):
    """
    La fiche client fusionne les colis où le client est expéditeur et ceux où
    il est destinataire (jamais les deux sur un même colis) dans l'onglet
    Expéditions, avec le rôle tenu indiqué par ligne.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_a = Gare.objects.create(nom='Gare Abidjan', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.gare_b = Gare.objects.create(nom='Gare Bouaké', code='BKE', ville='Bouaké', compagnie=self.compagnie)
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

        self.jean = Client.objects.create(telephone='0100000001', nom_complet='Jean Traoré')
        self.marie = Client.objects.create(telephone='0100000002', nom_complet='Marie Diallo')

        # Jean expéditeur d'un colis vers Marie...
        Colis.objects.create(
            gare_origine=self.gare_a, gare_destination=self.gare_b,
            expediteur=self.jean, expediteur_nom='Jean Traoré', expediteur_telephone='0100000001',
            destinataire=self.marie, destinataire_nom='Marie Diallo', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
        )
        # ...et destinataire d'un autre colis envoyé par Marie.
        Colis.objects.create(
            gare_origine=self.gare_b, gare_destination=self.gare_a,
            expediteur=self.marie, expediteur_nom='Marie Diallo', expediteur_telephone='0100000002',
            destinataire=self.jean, destinataire_nom='Jean Traoré', destinataire_telephone='0100000001',
            type_colis=self.type_colis, montant=3000,
        )

        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        self.client.force_login(self.user)

    def test_fusionne_les_deux_roles(self):
        response = self.client.get(reverse('clients:client_detail', kwargs={'public_id': self.jean.public_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['nb_colis'], 2)
        self.assertEqual(response.context['nb_colis_envoyes'], 1)
        self.assertEqual(response.context['nb_colis_recus'], 1)
        roles = sorted(c.role_pour_client for c in response.context['colis_page'])
        self.assertEqual(roles, ['destinataire', 'expediteur'])


class FideliteTests(TestCase):
    """
    Logique d'éligibilité au voyage offert (programme de fidélité).
    Comptage = billets 'paye' payés après l'activation ; report → seul le
    billet payé compte ; remboursement → le billet sort du compte ;
    jamais pour les clients « Société ».
    """

    def setUp(self):
        from datetime import time
        from apps.lignes.models import Ligne
        from apps.destinations.models import Destination
        from apps.voyages.models import Voyage

        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.compagnie.fidelite_active = True
        self.compagnie.fidelite_seuil_voyages = 3
        self.compagnie.save()

        self.gare = Gare.objects.create(nom='Gare Abidjan', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan - Bouaké', gare=self.gare,
            ville_depart='Abidjan', ville_arrivee='Bouaké', compagnie=self.compagnie,
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouaké', montant=3000,
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne,
            date_depart=timezone.now().date(), heure_depart=time(8, 0), periode='matin',
        )
        self.client_part = Client.objects.create(telephone='0100000001', nom_complet='Awa Particulier')
        self.client_soc = Client.objects.create(
            telephone='0100000002', nom_complet='ACME SARL', categorie='societe',
        )

    def _billet(self, client, statut='paye', siege=1, paye=True):
        from apps.billets.models import Billet
        return Billet.objects.create(
            voyage=self.voyage, destination=self.destination, client=client,
            client_nom=client.nom_complet, client_telephone=client.telephone,
            numero_siege=siege, montant=3000 if statut != 'fidelite' else 0,
            statut=statut, numero=f'T{statut[:2]}{siege}',
            date_paiement=timezone.now() if paye else None,
        )

    def test_eligible_apres_le_seuil(self):
        for i in range(1, 4):
            self._billet(self.client_part, siege=i)
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 3)
        self.assertTrue(self.client_part.fidelite_eligible)
        self.assertEqual(self.client_part.fidelite_reste, 0)

    def test_pas_eligible_avant_le_seuil(self):
        self._billet(self.client_part, siege=1)
        self._billet(self.client_part, siege=2)
        self.assertFalse(self.client_part.fidelite_eligible)
        self.assertEqual(self.client_part.fidelite_reste, 1)

    def test_remboursement_retire_le_point(self):
        for i in range(1, 4):
            self._billet(self.client_part, siege=i)
        b = self._billet(self.client_part, siege=4)
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 4)
        b.statut = 'rembourse'
        b.save(update_fields=['statut'])
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 3)

    def test_report_ne_compte_pas_double(self):
        # billet reporté (ne compte pas) + billet payé final (compte)
        self._billet(self.client_part, statut='reporte', siege=1)
        self._billet(self.client_part, statut='paye', siege=2)
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 1)

    def test_ticket_fidelite_non_compte_et_cycle_repart(self):
        for i in range(1, 4):
            self._billet(self.client_part, siege=i)
        self._billet(self.client_part, statut='fidelite', siege=10)
        # 3 payés, 1 ticket émis → objectif suivant = 6
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 3)
        self.assertEqual(self.client_part.fidelite_tickets_emis, 1)
        self.assertFalse(self.client_part.fidelite_eligible)
        self.assertEqual(self.client_part.fidelite_reste, 3)

    def test_societe_jamais_eligible(self):
        for i in range(1, 6):
            self._billet(self.client_soc, siege=i)
        self.assertFalse(self.client_soc.fidelite_eligible)
        self.assertEqual(self.client_soc.fidelite_voyages_comptabilises, 0)
        self.assertIsNone(self.client_soc.fidelite_reste)

    def test_programme_inactif_desactive_tout(self):
        self.compagnie.fidelite_active = False
        self.compagnie.save()
        for i in range(1, 6):
            self._billet(self.client_part, siege=i)
        self.assertFalse(self.client_part.fidelite_eligible)
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 0)

    def test_voyages_avant_activation_non_comptes(self):
        from apps.billets.models import Billet
        # Un billet payé "hier", activation "aujourd'hui" → non compté.
        vieux = self._billet(self.client_part, siege=1)
        Billet.objects.filter(pk=vieux.pk).update(
            date_paiement=self.compagnie.fidelite_active_depuis - timezone.timedelta(days=1)
        )
        self._billet(self.client_part, siege=2)
        self._billet(self.client_part, siege=3)
        self.assertEqual(self.client_part.fidelite_voyages_comptabilises, 2)
