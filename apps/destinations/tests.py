from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur

from .forms import DestinationForm
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


class DestinationUniciteTests(TestCase):
    """Doublons interdits sur (ligne + gare + ville d'arrivée + montant),
    sans tenir compte de la casse, des accents ni des espaces."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(nom='Gare Adjamé', code='ADJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan - Ouangolo', gare=self.gare,
            ville_depart='Abidjan', ville_arrivee='Ouangolo', compagnie=self.compagnie,
        )
        self.dest = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouaké', montant=6000,
        )

    def _form(self, **overrides):
        data = {
            'ligne': self.ligne.pk, 'gare': self.gare.pk,
            'ville_arrivee': 'Bouaké', 'montant': '6000', 'active': True,
        }
        data.update(overrides)
        return DestinationForm(data=data)

    def test_doublon_exact_refuse(self):
        self.assertFalse(self._form().is_valid())

    def test_doublon_casse_et_accents_refuse(self):
        form = self._form(ville_arrivee='  bouake ')
        self.assertFalse(form.is_valid())
        self.assertIn('ville_arrivee', form.errors)

    def test_doublon_majuscules_refuse(self):
        self.assertFalse(self._form(ville_arrivee='BOUAKÉ').is_valid())

    def test_montant_different_autorise(self):
        self.assertTrue(self._form(montant='7000').is_valid())

    def test_ville_differente_autorisee(self):
        self.assertTrue(self._form(ville_arrivee='Katiola').is_valid())

    def test_modification_sans_changement_autorisee(self):
        form = DestinationForm(
            data={
                'ligne': self.ligne.pk, 'gare': self.gare.pk,
                'ville_arrivee': 'BOUAKÉ', 'montant': '6000', 'active': True,
            },
            instance=self.dest,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_espaces_normalises_a_la_sauvegarde(self):
        form = self._form(ville_arrivee='Yamoussoukro', montant='7000')
        self.assertTrue(form.is_valid())
        form2 = self._form(ville_arrivee='  Yamoussoukro  ', montant='7000')
        self.assertEqual(form2.data['ville_arrivee'], '  Yamoussoukro  ')
        # après nettoyage la ville ne contient plus d'espaces superflus
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['ville_arrivee'], 'Yamoussoukro')
