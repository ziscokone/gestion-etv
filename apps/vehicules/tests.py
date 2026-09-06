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
