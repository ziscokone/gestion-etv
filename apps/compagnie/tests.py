from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from django.urls import reverse

from apps.personnel.models import Utilisateur
from .models import Compagnie, Remise


class RemiseConfigTests(TestCase):
    def setUp(self):
        self.sa = Utilisateur.objects.create_user(
            username='sa', password='x', nom_complet='SA', role='super_admin',
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.sa)
        Compagnie.objects.create(nom='ETV', nom_pdg='PDG')

    def _base_payload(self):
        # champs mini requis du CompagnieForm + management_form du formset vide
        return {
            'nom': 'ETV', 'nom_pdg': 'PDG', 'fidelite_seuil_voyages': 10,
            'alerte_assurance_jours': 30, 'alerte_assurance_urgent_jours': 10,
            'alerte_visite_technique_jours': 30, 'alerte_visite_technique_urgent_jours': 10,
            'alerte_carte_grise_jours': 30, 'alerte_carte_grise_urgent_jours': 10,
            'alerte_licence_transport_jours': 30, 'alerte_licence_transport_urgent_jours': 10,
            'remises-TOTAL_FORMS': '1', 'remises-INITIAL_FORMS': '0',
            'remises-MIN_NUM_FORMS': '0', 'remises-MAX_NUM_FORMS': '1000',
        }

    def test_ajout_remise(self):
        data = self._base_payload()
        data.update({'remises-0-libelle': 'Geste commercial', 'remises-0-montant': '1000', 'remises-0-actif': 'on'})
        resp = self.client.post(reverse('compagnie:parametres'), data)
        self.assertEqual(resp.status_code, 302)
        r = Remise.objects.get()
        self.assertEqual(int(r.montant), 1000)
        self.assertTrue(r.actif)

    def test_montant_zero_refuse(self):
        data = self._base_payload()
        data.update({'remises-0-libelle': '', 'remises-0-montant': '0', 'remises-0-actif': 'on'})
        resp = self.client.post(reverse('compagnie:parametres'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Remise.objects.count(), 0)
