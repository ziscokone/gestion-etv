from datetime import date, time
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from apps.billets.models import Billet
from apps.compagnie.models import Compagnie
from apps.destinations.models import Destination
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur
from apps.vehicules.models import ModeleVehicule, Vehicule
from apps.voyages.models import Voyage
from apps.guichet import impression


def _info_billet(**overrides):
    """Dict minimal conforme à Billet.get_info_impression(), pour les tests unitaires
    du module d'impression (pas besoin de DB)."""
    info = {
        'public_id': 'test-uuid',
        'numero': 'T-0001',
        'numero_depart': 1,
        'client_nom': 'Jean Client',
        'numero_siege': 5,
        'ligne': 'Abidjan - Bouake',
        'destination': 'Bouake',
        'date_depart': '01/08/2026',
        'heure_depart': '08:00',
        'periode': 'Matinée',
        'montant': 5000,
        'moyen_paiement': 'cash',
        'moyen_paiement_display': 'Cash',
        'gare_nom': 'Gare Centrale',
        'gare_adresse': 'Adresse test',
        'gare_telephone': '0102030405',
        'compagnie_nom': 'Ma Compagnie',
        'compagnie_logo': '',
        'utiliser_souche': False,
        'message_bas_ticket': 'Bon voyage !',
        'statut': 'paye',
    }
    info.update(overrides)
    return info


class ImpressionModuleTests(SimpleTestCase):
    """Tests du module ESC/POS (apps.guichet.impression), sans imprimante
    physique : on injecte directement un escpos.printer.Dummy pour inspecter
    les octets générés."""

    databases = []

    def _imprimer(self, infos, duplicata=False):
        from escpos.printer import Dummy
        dummy = Dummy()
        impression.imprimer_billets(infos, duplicata=duplicata, imprimante=dummy, largeur=42)
        return dummy.output

    def test_un_cut_par_billet(self):
        sortie = self._imprimer([_info_billet(), _info_billet(numero='T-0002')])
        self.assertEqual(sortie.count(b'\x1dV'), 2)

    def test_banniere_duplicata(self):
        sortie = self._imprimer([_info_billet()], duplicata=True)
        self.assertIn(b'DUPLICATA', sortie)

    def test_pas_de_banniere_duplicata_par_defaut(self):
        sortie = self._imprimer([_info_billet()], duplicata=False)
        self.assertNotIn(b'DUPLICATA', sortie)

    def test_banniere_gratuit(self):
        sortie = self._imprimer([_info_billet(statut='gratuit')])
        self.assertIn(b'GRATUIT', sortie)

    def test_souche_si_utiliser_souche_et_paye(self):
        sortie = self._imprimer([_info_billet(utiliser_souche=True, statut='paye')])
        self.assertIn(b'SOUCHE', sortie)

    def test_pas_de_souche_si_non_paye(self):
        sortie = self._imprimer([_info_billet(utiliser_souche=True, statut='reserve')])
        self.assertNotIn(b'SOUCHE', sortie)

    def test_pas_de_souche_si_compagnie_ne_l_utilise_pas(self):
        sortie = self._imprimer([_info_billet(utiliser_souche=False, statut='paye')])
        self.assertNotIn(b'SOUCHE', sortie)

    @override_settings(IMPRIMANTE_BACKEND='dummy')
    def test_get_imprimante_dummy(self):
        from escpos.printer import Dummy
        self.assertIsInstance(impression.get_imprimante(), Dummy)

    @override_settings(IMPRIMANTE_BACKEND='autre_chose')
    def test_get_imprimante_backend_inconnu(self):
        with self.assertRaises(impression.ImprimanteNonConfiguree):
            impression.get_imprimante()


@override_settings(IMPRIMANTE_BACKEND='win32raw')
class ConfigImprimanteDepuisGareTests(TestCase):
    """get_imprimante() lit désormais le nom de l'imprimante sur Gare (menu
    "Configuration Imprimante Ticket"), plus sur IMPRIMANTE_NOM."""

    def test_non_configuree_sans_gare(self):
        with self.assertRaises(impression.ImprimanteNonConfiguree):
            impression.get_imprimante()

    def test_non_configuree_nom_vide(self):
        compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        Gare.objects.create(
            nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=compagnie,
            imprimante_nom=''
        )
        with self.assertRaises(impression.ImprimanteNonConfiguree):
            impression.get_imprimante()


@override_settings(IMPRIMANTE_BACKEND='dummy')
class ImprimerBilletsVueTests(TestCase):
    """Tests d'intégration de la vue guichet:imprimer_billets."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(
            nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=self.compagnie
        )
        self.autre_gare = Gare.objects.create(
            nom='Autre Gare', code='BKE', ville='Bouake', compagnie=self.compagnie
        )
        self.ligne = Ligne.objects.create(
            nom='Abidjan-Bouake', gare=self.gare, ville_depart='Abidjan',
            ville_arrivee='Bouake', compagnie=self.compagnie
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouake', montant=5000
        )
        modele = ModeleVehicule.objects.create(nom='Coaster', marque='Toyota', capacite=30)
        vehicule = Vehicule.objects.create(
            immatriculation='AB-123-CD', modele=modele, compagnie=self.compagnie
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=vehicule
        )

        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare
        )

        self.billet = Billet.creer_billet(
            voyage=self.voyage, client_nom='Client Test', client_telephone='0100000000',
            numero_siege=1, guichetier=self.guichetier, destination=self.destination,
            payer=True, moyen_paiement='cash'
        )

        self.client.force_login(self.guichetier)

    def _url(self):
        return reverse('guichet:imprimer_billets')

    def test_impression_reussie(self):
        response = self.client.post(self._url(), {'public_id': [str(self.billet.public_id)]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_liste_vide(self):
        response = self.client.post(self._url(), {})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Aucun billet', data['error'])

    def test_public_id_inexistant(self):
        response = self.client.post(self._url(), {'public_id': ['00000000-0000-0000-0000-000000000000']})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('introuvable', data['error'])

    def test_acces_refuse_autre_gare(self):
        billet_autre_gare = Billet.creer_billet(
            voyage=Voyage.objects.create(
                gare=self.autre_gare, ligne=self.ligne, date_depart=date.today(),
                heure_depart=time(9, 0), periode='soir',
                vehicule=self.voyage.vehicule
            ),
            client_nom='Autre Client', client_telephone='0100000001',
            numero_siege=2, guichetier=self.guichetier, destination=self.destination,
            payer=True, moyen_paiement='cash'
        )
        response = self.client.post(self._url(), {'public_id': [str(billet_autre_gare.public_id)]})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('non autorisé', data['error'])

    def test_public_id_expose_dans_get_info_impression(self):
        info = self.billet.get_info_impression()
        self.assertEqual(info['public_id'], str(self.billet.public_id))

    def test_lot_de_plusieurs_billets(self):
        billet2 = Billet.creer_billet(
            voyage=self.voyage, client_nom='Client Test 2', client_telephone='0100000002',
            numero_siege=2, guichetier=self.guichetier, destination=self.destination,
            payer=True, moyen_paiement='cash'
        )
        response = self.client.post(self._url(), {
            'public_id': [str(self.billet.public_id), str(billet2.public_id)]
        })
        self.assertTrue(response.json()['success'])

    @patch('apps.guichet.views.impression.imprimer_billets')
    def test_erreur_imprimante_non_configuree_remontee(self, mock_imprimer):
        mock_imprimer.side_effect = impression.ImprimanteNonConfiguree('Imprimante non configurée sur ce poste.')
        response = self.client.post(self._url(), {'public_id': [str(self.billet.public_id)]})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Imprimante non configurée sur ce poste.')

    @patch('apps.guichet.views.impression.imprimer_billets')
    def test_erreur_inattendue_renvoie_500(self, mock_imprimer):
        mock_imprimer.side_effect = RuntimeError('boom')
        response = self.client.post(self._url(), {'public_id': [str(self.billet.public_id)]})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()['success'])


class ReservationsAjaxTests(TestCase):
    """Filtrage en direct des réservations en attente (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan-Bouake', gare=self.gare, ville_depart='Abidjan',
            ville_arrivee='Bouake', compagnie=self.compagnie
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouake', montant=5000
        )
        modele = ModeleVehicule.objects.create(nom='Coaster', marque='Toyota', capacite=30)
        vehicule = Vehicule.objects.create(immatriculation='AB-123-CD', modele=modele, compagnie=self.compagnie)
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=vehicule
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare
        )
        self.reservation_jean = Billet.creer_billet(
            voyage=self.voyage, client_nom='Jean Client', client_telephone='0100000001',
            numero_siege=1, guichetier=self.guichetier, destination=self.destination, payer=False,
        )
        self.reservation_marie = Billet.creer_billet(
            voyage=self.voyage, client_nom='Marie Client', client_telephone='0100000002',
            numero_siege=2, guichetier=self.guichetier, destination=self.destination, payer=False,
        )
        self.client.force_login(self.guichetier)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('guichet:reservations_ajax'), {'search': 'Jean'})
        self.assertContains(response, 'Jean Client')
        self.assertNotContains(response, 'Marie Client')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('guichet:reservations_ajax'))
        self.assertContains(response, 'Jean Client')
        self.assertContains(response, 'Marie Client')


class VoyageListAjaxTests(TestCase):
    """Filtrage en direct de la liste des voyages (module guichet, recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne_bouake = Ligne.objects.create(
            nom='Abidjan-Bouake', gare=self.gare, ville_depart='Abidjan',
            ville_arrivee='Bouake', compagnie=self.compagnie
        )
        self.ligne_man = Ligne.objects.create(
            nom='Abidjan-Man', gare=self.gare, ville_depart='Abidjan',
            ville_arrivee='Man', compagnie=self.compagnie
        )
        self.voyage_bouake = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne_bouake, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin',
        )
        self.voyage_man = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne_man, date_depart=date.today(),
            heure_depart=time(9, 0), periode='matin',
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare
        )
        self.client.force_login(self.guichetier)

    def test_filtre_par_ligne(self):
        response = self.client.get(reverse('guichet:voyage_list_ajax'), {'ligne': self.ligne_bouake.pk})
        self.assertContains(response, '→ Bouake')
        self.assertNotContains(response, '→ Man')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('guichet:voyage_list_ajax'))
        self.assertContains(response, '→ Bouake')
        self.assertContains(response, '→ Man')
