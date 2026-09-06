from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur

from .models import Destination


class DestinationListAjaxTests(TestCase):
    """Filtrage en direct de la liste des destinations (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(nom='Gare Abidjan', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne_bouake = Ligne.objects.create(
            nom='Abidjan - Bouaké', gare=self.gare,
            ville_depart='Abidjan', ville_arrivee='Bouaké', compagnie=self.compagnie,
        )
        self.ligne_man = Ligne.objects.create(
            nom='Abidjan - Man', gare=self.gare,
            ville_depart='Abidjan', ville_arrivee='Man', compagnie=self.compagnie,
        )
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123', nom_complet='Manager Test', role='manager',
        )
        self.dest_bouake = Destination.objects.create(gare=self.gare, ligne=self.ligne_bouake, ville_arrivee='Bouaké', montant=5000)
        self.dest_man = Destination.objects.create(gare=self.gare, ligne=self.ligne_man, ville_arrivee='Man', montant=8000)

    def test_filtre_par_recherche(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('destinations:destination_list_ajax'), {'q': 'Bouaké'})
        self.assertContains(response, 'Bouaké')
        self.assertNotContains(response, 'Man</td>')

    def test_sans_filtre_retourne_tout(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('destinations:destination_list_ajax'))
        self.assertContains(response, 'Bouaké')
        self.assertContains(response, 'Man</td>')
