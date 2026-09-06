from django.test import TestCase
from django.urls import reverse

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
