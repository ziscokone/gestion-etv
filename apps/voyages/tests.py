from datetime import time

from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.compagnie.models import Compagnie
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur

from .models import Voyage
from .views import voyage_list_ajax


class VoyageListAjaxTests(TestCase):
    """
    Filtrage en direct de la liste des voyages (module voyages, recherche automatique).

    Note : la vue est appelée directement via RequestFactory plutôt que par
    reverse()/self.client — l'URL /voyages/ajax/ est actuellement masquée par
    apps.guichet.urls (qui déclare aussi 'voyages/' à la racine, monté avant
    apps.voyages.urls dans config/urls.py) : /voyages/ résout déjà vers
    guichet:voyage_list avant même ce changement (collision préexistante,
    voir mémoire projet). Ce test valide la logique de la vue elle-même,
    indépendamment de ce problème de routage préexistant.
    """

    def setUp(self):
        self.factory = RequestFactory()
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
        today = timezone.now().date()
        Voyage.objects.create(gare=self.gare, ligne=self.ligne_bouake, date_depart=today, heure_depart=time(8, 0), periode='matin')
        Voyage.objects.create(gare=self.gare, ligne=self.ligne_man, date_depart=today, heure_depart=time(9, 0), periode='matin')
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123', nom_complet='Manager Test', role='manager',
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier', gare=self.gare,
        )

    def _get(self, user, params=None):
        request = self.factory.get('/voyages/ajax/', params or {})
        request.user = user
        return voyage_list_ajax(request)

    def test_filtre_par_recherche(self):
        response = self._get(self.manager, {'q': 'Bouaké'})
        content = response.content.decode()
        self.assertIn('Bouaké', content)
        self.assertNotIn('>Man<', content)

    def test_sans_filtre_retourne_tout(self):
        response = self._get(self.manager)
        content = response.content.decode()
        self.assertIn('Bouaké', content)
        self.assertIn('>Man<', content)

    def test_accessible_au_guichetier(self):
        response = self._get(self.guichetier)
        self.assertEqual(response.status_code, 200)
