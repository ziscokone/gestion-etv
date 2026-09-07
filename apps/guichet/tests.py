from datetime import date, time
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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


class CreerBilletCategorieClientTests(TestCase):
    """La vente transmet la catégorie choisie (particulier / société) pour un
    nouveau client ; une fiche existante n'est jamais réécrasée."""

    def setUp(self):
        from apps.clients.models import Client
        self.Client = Client
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = Gare.objects.create(nom='Gare Centrale', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan-Bouake', gare=self.gare, ville_depart='Abidjan',
            ville_arrivee='Bouake', compagnie=self.compagnie,
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouake', montant=5000,
        )
        modele = ModeleVehicule.objects.create(nom='Coaster', marque='Toyota', capacite=30)
        vehicule = Vehicule.objects.create(
            immatriculation='AB-123-CD', modele=modele, compagnie=self.compagnie,
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=vehicule,
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='g1', password='x', nom_complet='G1', role='guichetier', gare=self.gare,
        )
        self.client.force_login(self.guichetier)

    def _vendre(self, tel, nom, siege, categorie=None):
        data = {
            'client_nom': nom, 'client_telephone': tel,
            'destination_id': self.destination.pk, 'mode_vente': 'unitaire',
            'numero_siege': siege, 'payer': 'true', 'moyen_paiement': 'cash',
        }
        if categorie is not None:
            data['client_categorie'] = categorie
        return self.client.post(f'/api/creer-billet/{self.voyage.public_id}/', data)

    def test_nouveau_client_societe(self):
        r = self._vendre('0700000001', 'ACME SARL', 1, categorie='societe')
        self.assertTrue(r.json()['success'])
        self.assertEqual(self.Client.objects.get(telephone='0700000001').categorie, 'societe')

    def test_nouveau_client_defaut_particulier(self):
        r = self._vendre('0700000002', 'Awa', 2)  # pas de client_categorie
        self.assertTrue(r.json()['success'])
        self.assertEqual(self.Client.objects.get(telephone='0700000002').categorie, 'particulier')

    def test_categorie_non_ecrasee_sur_client_existant(self):
        self.Client.objects.create(telephone='0700000003', nom_complet='Déjà Là', categorie='societe')
        r = self._vendre('0700000003', 'Déjà Là', 3, categorie='particulier')
        self.assertTrue(r.json()['success'])
        self.assertEqual(self.Client.objects.get(telephone='0700000003').categorie, 'societe')


class FideliteEmissionVenteTests(TestCase):
    """Émission automatique du billet fidélité au moment de la vente (unitaire
    et par plage), via la vue guichet:creer_billet."""

    def setUp(self):
        from apps.clients.models import Client
        self.Client = Client
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        self.compagnie.fidelite_active = True
        self.compagnie.fidelite_seuil_voyages = 10
        self.compagnie.save()
        self.gare = Gare.objects.create(nom='G', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='L', gare=self.gare, ville_depart='Abidjan', ville_arrivee='Bouake', compagnie=self.compagnie,
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouake', montant=5000,
        )
        modele = ModeleVehicule.objects.create(nom='Bus', marque='Toyota', capacite=60)
        vehicule = Vehicule.objects.create(immatriculation='XX-1-YY', modele=modele, compagnie=self.compagnie)
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=vehicule,
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='g', password='x', nom_complet='G', role='guichetier', gare=self.gare,
        )
        self.client.force_login(self.guichetier)

    def _vendre(self, tel, nom, *, siege=None, debut=None, fin=None, categorie='particulier'):
        data = {
            'client_nom': nom, 'client_telephone': tel,
            'destination_id': self.destination.pk, 'payer': 'true',
            'moyen_paiement': 'cash', 'client_categorie': categorie,
        }
        if siege is not None:
            data['mode_vente'] = 'unitaire'
            data['numero_siege'] = siege
        else:
            data['mode_vente'] = 'plage'
            data['siege_debut'] = debut
            data['siege_fin'] = fin
        return self.client.post(f'/api/creer-billet/{self.voyage.public_id}/', data)

    def test_plage_de_12_le_11e_est_offert(self):
        r = self._vendre('0700000001', 'Awa', debut=1, fin=12)
        j = r.json()
        self.assertTrue(j['success'])
        self.assertEqual(j['nb_offerts'], 1)
        statuts = [b['statut'] for b in j['billets']]
        self.assertEqual(statuts.count('fidelite'), 1)
        self.assertEqual(statuts.count('paye'), 11)
        offert = next(b for b in j['billets'] if b['statut'] == 'fidelite')
        self.assertEqual(offert['numero_siege'], 11)
        self.assertEqual(int(offert['montant']), 0)

    def test_client_societe_jamais_de_billet_offert(self):
        r = self._vendre('0700000002', 'ACME', debut=1, fin=15, categorie='societe')
        j = r.json()
        self.assertTrue(j['success'])
        self.assertEqual(j['nb_offerts'], 0)

    def test_unitaire_offert_quand_seuil_deja_atteint(self):
        cl = self.Client.objects.create(telephone='0700000003', nom_complet='Kofi', categorie='particulier')
        from apps.billets.models import Billet
        for i in range(1, 11):
            Billet.objects.create(
                voyage=self.voyage, destination=self.destination, client=cl,
                client_nom='Kofi', client_telephone='0700000003', numero_siege=i,
                montant=5000, statut='paye', numero=f'P{i}', date_paiement=timezone.now(),
            )
        r = self._vendre('0700000003', 'Kofi', siege=11)
        j = r.json()
        self.assertTrue(j['success'])
        self.assertEqual(j['nb_offerts'], 1)
        self.assertEqual(j['billets'][0]['statut'], 'fidelite')

    def test_reservation_non_payee_ne_declenche_rien(self):
        cl = self.Client.objects.create(telephone='0700000004', nom_complet='Ama', categorie='particulier')
        from apps.billets.models import Billet
        for i in range(1, 11):
            Billet.objects.create(
                voyage=self.voyage, destination=self.destination, client=cl,
                client_nom='Ama', client_telephone='0700000004', numero_siege=i,
                montant=5000, statut='paye', numero=f'Q{i}', date_paiement=timezone.now(),
            )
        data = {
            'client_nom': 'Ama', 'client_telephone': '0700000004',
            'destination_id': self.destination.pk, 'payer': 'false',
            'mode_vente': 'unitaire', 'numero_siege': 11, 'client_categorie': 'particulier',
        }
        r = self.client.post(f'/api/creer-billet/{self.voyage.public_id}/', data)
        j = r.json()
        self.assertTrue(j['success'])
        self.assertEqual(j['billets'][0]['statut'], 'reserve')


class FideliteSiegeDispositionTests(TestCase):
    """Un siège vendu en fidélité apparaît avec le statut 'fidelite' sur le
    plan des sièges (et n'est donc plus proposé comme disponible)."""

    def setUp(self):
        from apps.clients.models import Client
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        self.compagnie.fidelite_active = True
        self.compagnie.fidelite_seuil_voyages = 2
        self.compagnie.save()
        self.gare = Gare.objects.create(nom='G', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='L', gare=self.gare, ville_depart='Abidjan', ville_arrivee='Bouake', compagnie=self.compagnie,
        )
        self.destination = Destination.objects.create(
            gare=self.gare, ligne=self.ligne, ville_arrivee='Bouake', montant=5000,
        )
        modele = ModeleVehicule.objects.create(nom='Bus', marque='Toyota', capacite=60)
        vehicule = Vehicule.objects.create(immatriculation='ZZ-9-ZZ', modele=modele, compagnie=self.compagnie)
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne, date_depart=date.today(),
            heure_depart=time(8, 0), periode='matin', vehicule=vehicule,
        )
        self.client_part = Client.objects.create(telephone='0700000009', nom_complet='Yao', categorie='particulier')

    def test_siege_fidelite_dans_la_disposition(self):
        from apps.billets.models import Billet
        # 2 payés → le 3e est offert
        Billet.creer_billets_avec_fidelite(
            voyage=self.voyage, client=self.client_part,
            client_nom='Yao', client_telephone='0700000009',
            sieges=[1, 2, 3], guichetier=None, destination=self.destination,
        )
        self.assertEqual(self.voyage.get_sieges_fidelite(), [3])
        dispo = self.voyage.get_disposition_sieges_avec_statut()
        statuts = {
            s['numero']: s['statut']
            for r in dispo['rangees'] for s in r['sieges'] if s['numero'] in (1, 2, 3)
        }
        self.assertEqual(statuts[1], 'paye')
        self.assertEqual(statuts[2], 'paye')
        self.assertEqual(statuts[3], 'fidelite')
        self.assertNotIn(3, self.voyage.get_sieges_disponibles())
