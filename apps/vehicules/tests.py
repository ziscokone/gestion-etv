from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie
from apps.personnel.models import Utilisateur

from .models import ModeleVehicule, ReparationVehicule, TypeReparation, Vehicule


class ModeleListAjaxTests(TestCase):
    """Filtrage en direct des modèles de véhicules (recherche automatique)."""

    def setUp(self):
        ModeleVehicule.objects.create(nom='Sprinter 516', marque='Mercedes-Benz', capacite=20)
        ModeleVehicule.objects.create(nom='Coaster', marque='Toyota', capacite=30)
        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        self.client.force_login(self.user)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('vehicules:modele_list_ajax'), {'q': 'Mercedes'})
        self.assertContains(response, 'Sprinter 516')
        self.assertNotContains(response, 'Coaster')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('vehicules:modele_list_ajax'))
        self.assertContains(response, 'Sprinter 516')
        self.assertContains(response, 'Coaster')


class TypeReparationListAjaxTests(TestCase):
    """Filtrage en direct des types de réparation (recherche automatique)."""

    def setUp(self):
        TypeReparation.objects.create(nom='Vidange')
        TypeReparation.objects.create(nom='Freins')
        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        self.client.force_login(self.user)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('vehicules:type_reparation_list_ajax'), {'q': 'Vidange'})
        self.assertContains(response, 'Vidange')
        self.assertNotContains(response, 'Freins')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('vehicules:type_reparation_list_ajax'))
        self.assertContains(response, 'Vidange')
        self.assertContains(response, 'Freins')


class VehiculeListAjaxTests(TestCase):
    """Filtrage en direct de la liste des véhicules (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        modele = ModeleVehicule.objects.create(nom='Sprinter 516', marque='Mercedes-Benz', capacite=20)
        Vehicule.objects.create(numero_ordre='01', immatriculation='AB-111-CD', modele=modele, compagnie=self.compagnie, actif=True)
        Vehicule.objects.create(numero_ordre='02', immatriculation='XY-222-ZT', modele=modele, compagnie=self.compagnie, actif=False)
        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        self.client.force_login(self.user)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('vehicules:vehicule_list_ajax'), {'q': 'AB-111'})
        self.assertContains(response, 'AB-111-CD')
        self.assertNotContains(response, 'XY-222-ZT')

    def test_filtre_par_statut(self):
        response = self.client.get(reverse('vehicules:vehicule_list_ajax'), {'statut': 'actif'})
        self.assertContains(response, 'AB-111-CD')
        self.assertNotContains(response, 'XY-222-ZT')


class ReparationListAjaxTests(TestCase):
    """Filtrage en direct de la liste des réparations (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        modele = ModeleVehicule.objects.create(nom='Sprinter 516', marque='Mercedes-Benz', capacite=20)
        self.vehicule_a = Vehicule.objects.create(numero_ordre='01', immatriculation='AB-111-CD', modele=modele, compagnie=self.compagnie)
        self.vehicule_b = Vehicule.objects.create(numero_ordre='02', immatriculation='XY-222-ZT', modele=modele, compagnie=self.compagnie)
        ReparationVehicule.objects.create(vehicule=self.vehicule_a, date_reparation=date.today(), garage_prestataire='Garage A')
        ReparationVehicule.objects.create(vehicule=self.vehicule_b, date_reparation=date.today(), garage_prestataire='Garage B')
        self.user = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        self.client.force_login(self.user)

    def test_filtre_par_vehicule(self):
        response = self.client.get(reverse('vehicules:reparation_list_ajax'), {'vehicule': self.vehicule_a.pk})
        self.assertContains(response, 'AB-111-CD')
        self.assertNotContains(response, 'XY-222-ZT')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('vehicules:reparation_list_ajax'))
        self.assertContains(response, 'AB-111-CD')
        self.assertContains(response, 'XY-222-ZT')


class CreditPieceGarageTests(TestCase):
    """Pièces à crédit : cumul des versements, reste dû, statut auto, garde-fou anti-surpaiement."""

    def setUp(self):
        from decimal import Decimal
        self.Decimal = Decimal
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        modele = ModeleVehicule.objects.create(nom='Bus', marque='Toyota', capacite=30)
        self.vehicule = Vehicule.objects.create(
            immatriculation='AB-1-CD', modele=modele, compagnie=self.compagnie,
        )
        self.reparation = ReparationVehicule.objects.create(
            vehicule=self.vehicule, date_reparation=date.today(), garage_prestataire='Garage X',
        )
        self.admin = Utilisateur.objects.create_user(
            username='sa', password='x', nom_complet='SA', role='super_admin',
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.admin)

    def _credit(self, total='100000'):
        from apps.vehicules.models import CreditPieceGarage
        return CreditPieceGarage.objects.create(
            reparation=self.reparation, fournisseur='Ets Sanogo',
            libelle='plaquettes + disques', montant_total=self.Decimal(total),
            date_achat=date.today(),
        )

    def test_versements_cumules_et_reste(self):
        from apps.vehicules.models import VersementCredit
        c = self._credit('100000')
        VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=40000)
        VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=25000)
        c.refresh_from_db()
        self.assertEqual(c.montant_paye, self.Decimal('65000'))
        self.assertEqual(c.reste_a_payer, self.Decimal('35000'))
        self.assertFalse(c.est_solde)
        self.assertEqual(c.statut, 'en_cours')

    def test_solde_automatique(self):
        from apps.vehicules.models import VersementCredit
        c = self._credit('50000')
        VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=50000)
        c.refresh_from_db()
        self.assertTrue(c.est_solde)
        self.assertEqual(c.statut, 'solde')
        self.assertEqual(c.reste_a_payer, self.Decimal('0'))

    def test_suppression_versement_recalcule(self):
        from apps.vehicules.models import VersementCredit
        c = self._credit('50000')
        v = VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=50000)
        c.refresh_from_db(); self.assertEqual(c.statut, 'solde')
        v.delete()
        c.refresh_from_db()
        self.assertEqual(c.statut, 'en_cours')
        self.assertEqual(c.montant_paye, self.Decimal('0'))

    def test_form_refuse_surpaiement(self):
        from apps.vehicules.forms import VersementCreditForm
        c = self._credit('100000')
        from apps.vehicules.models import VersementCredit
        VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=80000)
        form = VersementCreditForm(
            data={'date_versement': date.today(), 'montant': 30000, 'moyen_paiement': 'cash', 'note': ''},
            credit=c,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('montant', form.errors)

    def test_vue_versement_cree_et_redirige(self):
        c = self._credit('60000')
        url = reverse('vehicules:versement_create', kwargs={'credit_pk': c.pk})
        resp = self.client.post(url, {
            'date_versement': date.today(), 'montant': 60000, 'moyen_paiement': 'virement', 'note': 'solde',
        })
        self.assertEqual(resp.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.statut, 'solde')

    def test_ecran_credits_liste_accessible(self):
        self._credit('100000')
        resp = self.client.get(reverse('vehicules:credit_garage_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ets Sanogo')


class BilanMensuelCreditGarageTests(TestCase):
    """Le bilan mensuel expose le point crédits garage : contracté / versé / encours."""

    def setUp(self):
        from decimal import Decimal
        from datetime import time
        from apps.lignes.models import Ligne
        from apps.voyages.models import Voyage
        self.Decimal = Decimal
        self.compagnie = Compagnie.objects.create(nom='C', nom_pdg='P')
        from apps.gares.models import Gare
        self.gare = Gare.objects.create(nom='G', code='ABJ', ville='Abidjan', compagnie=self.compagnie)
        ligne = Ligne.objects.create(nom='L', gare=self.gare, ville_depart='A', ville_arrivee='B', compagnie=self.compagnie)
        # un voyage ce mois pour que le bilan ait un mois sélectionnable
        self.voyage = Voyage.objects.create(
            gare=self.gare, ligne=ligne, date_depart=date.today(), heure_depart=time(8, 0), periode='matin',
        )
        modele = ModeleVehicule.objects.create(nom='Bus', marque='T', capacite=30)
        veh = Vehicule.objects.create(immatriculation='XX-9-YY', modele=modele, compagnie=self.compagnie)
        rep = ReparationVehicule.objects.create(vehicule=veh, date_reparation=date.today(), garage_prestataire='GX')
        from apps.vehicules.models import CreditPieceGarage, VersementCredit
        c = CreditPieceGarage.objects.create(
            reparation=rep, fournisseur='Sanogo', libelle='pièces',
            montant_total=Decimal('200000'), date_achat=date.today(),
        )
        VersementCredit.objects.create(credit=c, date_versement=date.today(), montant=Decimal('75000'))
        self.pdg = Utilisateur.objects.create_user(
            username='pdg', password='x', nom_complet='PDG', role='pdg',
        )
        self.client.force_login(self.pdg)

    def test_bloc_credit_dans_le_bilan(self):
        mois = date.today().strftime('%Y-%m')
        resp = self.client.get(reverse('comptabilite:bilan_mensuel'), {'mois': mois})
        self.assertEqual(resp.status_code, 200)
        cg = resp.context['credit_garage']
        self.assertEqual(cg['contracte_mois'], self.Decimal('200000'))
        self.assertEqual(cg['verse_mois'], self.Decimal('75000'))
        self.assertEqual(cg['encours_fin_mois'], self.Decimal('125000'))
        self.assertContains(resp, 'Point crédits garage')
