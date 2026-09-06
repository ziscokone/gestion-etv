from datetime import time

from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie
from apps.destinations.models import Destination
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur

from .models import ProgrammeDepart


class ProgrammeListAjaxTests(TestCase):
    """Filtrage en direct des programmes de départ (recherche automatique)."""

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
        self.dest_bouake = Destination.objects.create(gare=self.gare, ligne=self.ligne_bouake, ville_arrivee='Bouaké', montant=5000)
        self.dest_man = Destination.objects.create(gare=self.gare, ligne=self.ligne_man, ville_arrivee='Man', montant=8000)
        ProgrammeDepart.objects.create(
            gare=self.gare, ligne=self.ligne_bouake, destination=self.dest_bouake,
            periode='matin', heure_depart=time(8, 0), jours_actifs=['lun'],
        )
        ProgrammeDepart.objects.create(
            gare=self.gare, ligne=self.ligne_man, destination=self.dest_man,
            periode='matin', heure_depart=time(9, 0), jours_actifs=['lun'],
        )
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123', nom_complet='Manager Test', role='manager',
        )
        self.client.force_login(self.manager)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('programmes:programme_list_ajax'), {'q': 'Bouaké'})
        self.assertContains(response, 'Abidjan - Bouaké')
        self.assertNotContains(response, 'Abidjan - Man')

    def test_filtre_par_destination(self):
        # Couvre le bug corrigé : la recherche utilisait destination__ville (inexistant)
        # au lieu de destination__ville_arrivee, ce qui faisait planter toute recherche.
        response = self.client.get(reverse('programmes:programme_list_ajax'), {'q': 'Man'})
        self.assertContains(response, 'Abidjan - Man')
        self.assertNotContains(response, 'Abidjan - Bouaké')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('programmes:programme_list_ajax'))
        self.assertContains(response, 'Abidjan - Bouaké')
        self.assertContains(response, 'Abidjan - Man')
