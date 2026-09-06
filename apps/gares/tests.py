from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie
from apps.gares.models import Gare
from apps.personnel.models import Utilisateur


class ImprimanteConfigViewTests(TestCase):
    """Tests d'accès et de fonctionnement de la page "Configuration Imprimante
    Ticket" (menu utilisateur)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(
            nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=self.compagnie
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare
        )
        self.chef_gare = Utilisateur.objects.create_user(
            username='chef1', password='pass123',
            nom_complet='Awa Chef', role='chef_gare', gare=self.gare
        )
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager Test', role='manager'
        )

    def _url(self):
        return reverse('gares:imprimante_config')

    def test_guichetier_refuse(self):
        self.client.force_login(self.guichetier)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_chef_gare_autorise(self):
        self.client.force_login(self.chef_gare)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_acces_global_autorise(self):
        self.client.force_login(self.manager)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_soumission_met_a_jour_la_gare(self):
        self.client.force_login(self.chef_gare)
        response = self.client.post(self._url(), {
            'imprimante_nom': 'XP-80C',
            'imprimante_largeur_caracteres': 48,
        })
        self.assertRedirects(response, self._url())
        self.gare.refresh_from_db()
        self.assertEqual(self.gare.imprimante_nom, 'XP-80C')
        self.assertEqual(self.gare.imprimante_largeur_caracteres, 48)

    def test_redirige_si_aucune_gare(self):
        Gare.objects.all().delete()
        self.client.force_login(self.manager)
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse('sync:statut'))
