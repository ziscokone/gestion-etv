from django.test import TestCase
from django.urls import reverse

from apps.compagnie.models import Compagnie

from .models import Chauffeur, Convoyeur, TypeDocumentChauffeur, Utilisateur


class ChauffeurListAjaxTests(TestCase):
    """Filtrage en direct de la liste des chauffeurs (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.admin = Utilisateur.objects.create_user(
            username='super1', password='pass123', nom_complet='Super Admin', role='super_admin',
        )
        Chauffeur.objects.create(nom_complet='Jean Traoré', telephone='0100000001', numero_permis='P001', compagnie=self.compagnie)
        Chauffeur.objects.create(nom_complet='Marie Diallo', telephone='0100000002', numero_permis='P002', compagnie=self.compagnie)
        self.client.force_login(self.admin)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('personnel:chauffeur_list_ajax'), {'q': 'Jean'})
        self.assertContains(response, 'Jean Traoré')
        self.assertNotContains(response, 'Marie Diallo')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('personnel:chauffeur_list_ajax'))
        self.assertContains(response, 'Jean Traoré')
        self.assertContains(response, 'Marie Diallo')


class ConvoyeurListAjaxTests(TestCase):
    """Filtrage en direct de la liste des convoyeurs (recherche automatique)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.admin = Utilisateur.objects.create_user(
            username='super1', password='pass123', nom_complet='Super Admin', role='super_admin',
        )
        Convoyeur.objects.create(nom_complet='Issa Bamba', telephone='0100000003', compagnie=self.compagnie)
        Convoyeur.objects.create(nom_complet='Awa Koné', telephone='0100000004', compagnie=self.compagnie)
        self.client.force_login(self.admin)

    def test_filtre_par_recherche(self):
        response = self.client.get(reverse('personnel:convoyeur_list_ajax'), {'q': 'Issa'})
        self.assertContains(response, 'Issa Bamba')
        self.assertNotContains(response, 'Awa Koné')

    def test_sans_filtre_retourne_tout(self):
        response = self.client.get(reverse('personnel:convoyeur_list_ajax'))
        self.assertContains(response, 'Issa Bamba')
        self.assertContains(response, 'Awa Koné')


class TypeDocumentListAjaxTests(TestCase):
    """Filtrage en direct des types de document chauffeur — réservé au super administrateur."""

    def setUp(self):
        self.super_admin = Utilisateur.objects.create_user(
            username='super1', password='pass123', nom_complet='Super Admin',
            role='super_admin', is_superuser=True,
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        TypeDocumentChauffeur.objects.get_or_create(nom='Attestation médicale')
        TypeDocumentChauffeur.objects.get_or_create(nom='Casier judiciaire')

    def test_filtre_par_recherche(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse('personnel:type_document_list_ajax'), {'q': 'médicale'})
        self.assertContains(response, 'Attestation médicale')
        self.assertNotContains(response, 'Casier judiciaire')

    def test_refuse_hors_super_admin(self):
        self.client.force_login(self.guichetier)
        response = self.client.get(reverse('personnel:type_document_list_ajax'))
        self.assertEqual(response.status_code, 403)


class UtilisateurListAjaxTests(TestCase):
    """Filtrage en direct de la liste des utilisateurs — accès global ou chef de gare uniquement."""

    def setUp(self):
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123', nom_complet='Manager Test', role='manager',
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123', nom_complet='Jean Guichetier', role='guichetier',
        )
        Utilisateur.objects.create_user(
            username='courrier1', password='pass123', nom_complet='Fatou Courrier', role='agent_courrier',
        )

    def test_filtre_par_role(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('personnel:utilisateur_list_ajax'), {'role': 'agent_courrier'})
        self.assertContains(response, 'Fatou Courrier')
        self.assertNotContains(response, 'Jean Guichetier')

    def test_refuse_pour_guichetier(self):
        self.client.force_login(self.guichetier)
        response = self.client.get(reverse('personnel:utilisateur_list_ajax'))
        self.assertEqual(response.status_code, 403)
