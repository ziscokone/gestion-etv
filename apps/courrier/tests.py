from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client
from apps.compagnie.models import Compagnie
from apps.gares.models import Gare
from apps.lignes.models import Ligne
from apps.personnel.models import Utilisateur
from apps.voyages.models import Voyage

from .forms import ColisForm
from .models import Colis, TypeColis
from .views import _gares_pour_voyage


def _creer_gare(compagnie, nom, code, ville):
    return Gare.objects.create(nom=nom, code=code, ville=ville, compagnie=compagnie)


class NumerotationColisTests(TestCase):
    """Génération du code colis (Gare.generer_numero_colis) et du code de retrait."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Centrale', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

    def _creer_colis(self):
        return Colis.objects.create(
            gare_origine=self.gare, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
        )

    def test_format_code_colis(self):
        colis = self._creer_colis()
        self.assertTrue(colis.code_colis.startswith('COL-ABJ'))
        self.assertTrue(colis.code_colis.endswith('00001'))

    def test_sequence_incrementale(self):
        c1 = self._creer_colis()
        c2 = self._creer_colis()
        self.assertNotEqual(c1.code_colis, c2.code_colis)
        self.assertTrue(c2.code_colis.endswith('00002'))

    def test_reset_mensuel(self):
        self.gare.mois_dernier_colis = '202601'
        self.gare.dernier_numero_colis = 42
        self.gare.save()
        colis = self._creer_colis()
        self.assertTrue(colis.code_colis.endswith('00001'))

    def test_code_retrait_a_6_chiffres_et_distinct_du_code_colis(self):
        colis = self._creer_colis()
        self.assertEqual(len(colis.code_retrait), 6)
        self.assertTrue(colis.code_retrait.isdigit())
        self.assertNotIn(colis.code_retrait, colis.code_colis)


class FluxColisTests(TestCase):
    """Parcours complet : enregistrement → chargement → arrivée automatique → retrait."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan - Bouaké', gare=self.gare_origine,
            ville_depart='Abidjan', ville_arrivee='Bouaké', compagnie=self.compagnie,
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare_origine, ligne=self.ligne,
            date_depart=date(2026, 9, 1), heure_depart=time(8, 0), periode='matin',
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare_origine,
        )
        self.colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            guichetier_enregistrement=self.guichetier,
        )

    def test_chargement_puis_arrivee_automatique_puis_retrait(self):
        self.assertEqual(self.colis.statut, 'enregistre')

        self.colis.marquer_en_transit(self.voyage, self.guichetier)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'en_transit')
        self.assertEqual(self.colis.voyage_id, self.voyage.id)

        # Le voyage passe à 'termine' → le signal doit faire arriver le colis automatiquement.
        self.voyage.statut = 'termine'
        self.voyage.save()
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'arrive')
        self.assertIsNotNone(self.colis.date_limite_retrait)
        self.assertGreater(self.colis.date_limite_retrait, self.colis.date_arrivee)

        # L'arrivée automatique ne suffit pas — la gare doit réceptionner manuellement.
        self.colis.marquer_receptionne(self.guichetier)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'receptionne')

        self.colis.marquer_retire(
            agent=self.guichetier, piece_identite='12345',
            retirant_nom='Awa Destinataire', retirant_telephone='0100000002',
        )
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'retire')
        self.assertEqual(self.colis.piece_identite_retrait, '12345')
        self.assertEqual(self.colis.retirant_nom, 'Awa Destinataire')
        self.assertEqual(self.colis.historique.count(), 4)

    def test_port_du_reste_impaye_tant_que_non_retire(self):
        # Le formulaire d'enregistrement n'expose plus "qui_paie" (toujours expéditeur,
        # payé à l'enregistrement) — mais le modèle garde ce comportement générique
        # au cas où le port dû reviendrait un jour ; ce test protège Colis.marquer_retire().
        colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Client', expediteur_telephone='0100000003',
            destinataire_nom='Destinataire', destinataire_telephone='0100000004',
            type_colis=self.type_colis, montant=3000, qui_paie='destinataire',
        )
        self.assertFalse(colis.paye)
        colis.marquer_retire(agent=self.guichetier, piece_identite='CNI 999', moyen_paiement='wave')
        colis.refresh_from_db()
        self.assertTrue(colis.paye)
        self.assertEqual(colis.moyen_paiement, 'wave')

    def test_annulation_impossible_apres_chargement(self):
        self.colis.marquer_en_transit(self.voyage, self.guichetier)
        self.colis.refresh_from_db()
        self.assertNotEqual(self.colis.statut, 'enregistre')


class ReceptionColisViewTests(TestCase):
    """
    Écran de réception : la gare de destination doit confirmer avoir
    physiquement le colis avant que le retrait ne devienne possible — le
    passage automatique en 'arrive' (à la fin du voyage) ne suffit pas.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.agent_dest = Utilisateur.objects.create_user(
            username='agent_dest', password='pass123',
            nom_complet='Agent Destination', role='guichetier', gare=self.gare_dest,
        )
        self.colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            statut='arrive', date_arrivee=timezone.now(),
        )

    def test_colis_arrive_visible_sur_l_ecran_de_reception(self):
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:reception_liste'))
        self.assertContains(response, self.colis.code_colis)

    def test_reception_bascule_le_statut(self):
        self.client.force_login(self.agent_dest)
        response = self.client.post(reverse('courrier:reception_liste'), {'colis_id': str(self.colis.public_id)})
        self.assertRedirects(response, reverse('courrier:reception_liste'))
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'receptionne')
        self.assertIsNotNone(self.colis.date_reception)
        self.assertEqual(self.colis.guichetier_reception, self.agent_dest)

    def test_colis_en_transit_visible_sur_l_ecran_de_reception(self):
        # Le voyage n'a pas forcément été marqué "Terminé" par la gare d'origine
        # (action séparée) — la gare de destination doit pouvoir réceptionner
        # dès que le colis est chargé (en_transit), sans attendre ce signal.
        colis_en_transit = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Autre Expéditeur', expediteur_telephone='0100000003',
            destinataire_nom='Autre Destinataire', destinataire_telephone='0100000004',
            type_colis=self.type_colis, montant=2500, statut='en_transit',
        )
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:reception_liste'))
        self.assertContains(response, colis_en_transit.code_colis)

    def test_reception_directe_depuis_en_transit_renseigne_la_date_d_arrivee(self):
        colis_en_transit = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Autre Expéditeur', expediteur_telephone='0100000003',
            destinataire_nom='Autre Destinataire', destinataire_telephone='0100000004',
            type_colis=self.type_colis, montant=2500, statut='en_transit',
        )
        self.client.force_login(self.agent_dest)
        response = self.client.post(reverse('courrier:reception_liste'), {'colis_id': str(colis_en_transit.public_id)})
        self.assertRedirects(response, reverse('courrier:reception_liste'))
        colis_en_transit.refresh_from_db()
        self.assertEqual(colis_en_transit.statut, 'receptionne')
        self.assertIsNotNone(colis_en_transit.date_arrivee)
        self.assertIsNotNone(colis_en_transit.date_limite_retrait)

    def test_retrait_impossible_avant_reception(self):
        self.client.force_login(self.agent_dest)
        response = self.client.post(reverse('courrier:retrait'), {
            'colis_id': str(self.colis.public_id),
            'code_retrait': self.colis.code_retrait,
            'retirant_nom': 'Awa Destinataire',
            'retirant_telephone': '0100000002',
            'piece_identite': '12345678',
        })
        self.assertEqual(response.status_code, 404)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'arrive')

    def test_gare_tierce_ne_voit_pas_le_colis_sur_l_ecran_de_reception(self):
        autre_gare = _creer_gare(self.compagnie, 'Gare Man', 'MAN', 'Man')
        agent_tiers = Utilisateur.objects.create_user(
            username='agent_tiers', password='pass123',
            nom_complet='Agent Tiers', role='guichetier', gare=autre_gare,
        )
        self.client.force_login(agent_tiers)
        response = self.client.get(reverse('courrier:reception_liste'))
        self.assertNotContains(response, self.colis.code_colis)


class RetraitViewTests(TestCase):
    """
    Vérification côté vue : le code de retrait est bien contrôlé, le retrait
    n'est possible qu'une fois réceptionné, et le retirant (destinataire ou
    mandataire) est capturé et mémorisé comme Client (nom + N° CNI).
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.chef_gare = Utilisateur.objects.create_user(
            username='chef1', password='pass123',
            nom_complet='Awa Chef', role='chef_gare', gare=self.gare_dest,
        )
        self.colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            statut='receptionne', date_arrivee=timezone.now(), date_reception=timezone.now(),
        )

    def _post(self, **overrides):
        data = {
            'colis_id': str(self.colis.public_id),
            'code_retrait': self.colis.code_retrait,
            'retirant_nom': 'Awa Destinataire',
            'retirant_telephone': '0100000002',
            'piece_identite': '12345678',
        }
        data.update(overrides)
        return self.client.post(reverse('courrier:retrait'), data)

    def test_retrait_refuse_avec_mauvais_code(self):
        self.client.force_login(self.chef_gare)
        response = self._post(code_retrait='000000')
        self.assertEqual(response.status_code, 200)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'receptionne')

    def test_retrait_reussi_avec_bon_code(self):
        self.client.force_login(self.chef_gare)
        response = self._post()
        self.assertRedirects(response, reverse('courrier:colis_detail', kwargs={'public_id': self.colis.public_id}))
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'retire')
        self.assertEqual(self.colis.retirant_nom, 'Awa Destinataire')
        self.assertEqual(self.colis.retirant_telephone, '0100000002')
        self.assertEqual(self.colis.piece_identite_retrait, '12345678')

    def test_retrait_refuse_hors_gare_destination(self):
        autre_gare = _creer_gare(self.compagnie, 'Gare Man', 'MAN', 'Man')
        agent_autre_gare = Utilisateur.objects.create_user(
            username='chef2', password='pass123',
            nom_complet='Autre Chef', role='chef_gare', gare=autre_gare,
        )
        self.client.force_login(agent_autre_gare)
        response = self._post()
        self.assertEqual(response.status_code, 403)

    def test_retrait_par_un_mandataire_different_du_destinataire(self):
        self.client.force_login(self.chef_gare)
        response = self._post(retirant_nom='Koffi Mandataire', retirant_telephone='0100000099')
        self.assertRedirects(response, reverse('courrier:colis_detail', kwargs={'public_id': self.colis.public_id}))
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.retirant_nom, 'Koffi Mandataire')
        self.assertEqual(self.colis.retirant_telephone, '0100000099')
        self.assertTrue(Client.objects.filter(telephone='0100000099', nom_complet='Koffi Mandataire').exists())

    def test_cni_memorise_ressort_via_la_suggestion_au_retrait_suivant(self):
        self.client.force_login(self.chef_gare)
        self._post(piece_identite='CI-0099887766')
        client = Client.objects.get(telephone='0100000002')
        self.assertEqual(client.numero_cni, 'CI-0099887766')

        # Un second colis retiré par la même personne : le formulaire s'appuie
        # sur clients:suggerer_clients pour faire ressortir le CNI mémorisé.
        response = self.client.get(reverse('clients:suggerer_clients'), {'q': '0100000002'})
        data = response.json()
        self.assertEqual(data['clients'][0]['numero_cni'], 'CI-0099887766')


class RetraitRechercheAjaxTests(TestCase):
    """Recherche en direct sur l'écran de retrait (sans clic sur le bouton)."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.chef_gare = Utilisateur.objects.create_user(
            username='chef1', password='pass123',
            nom_complet='Awa Chef', role='chef_gare', gare=self.gare_dest,
        )
        self.colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            statut='receptionne', date_arrivee=timezone.now(), date_reception=timezone.now(),
        )

    def test_recherche_ajax_retourne_le_colis_avec_le_code_retrait_prerempli(self):
        self.client.force_login(self.chef_gare)
        response = self.client.get(reverse('courrier:retrait_ajax'), {'q': self.colis.code_colis})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.colis.code_colis)
        self.assertContains(response, f'value="{self.colis.code_retrait}"')

    def test_recherche_ajax_sans_resultat(self):
        self.client.force_login(self.chef_gare)
        response = self.client.get(reverse('courrier:retrait_ajax'), {'q': 'INTROUVABLE'})
        self.assertContains(response, 'Aucun colis')


class ColisCreateViewTests(TestCase):
    """Enregistrement d'un colis depuis le guichet : réconciliation client, génération des codes."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare_origine,
        )
        self.client_existant = Client.objects.create(telephone='0100000009', nom_complet='Ancien Client')

    def test_enregistrement_cree_le_colis_et_reconcilie_les_clients(self):
        self.client.force_login(self.guichetier)
        response = self.client.post(reverse('courrier:colis_create'), {
            'gare_destination': self.gare_dest.pk,
            'expediteur_telephone': '0100000009',  # correspond à un client existant
            'expediteur_nom': 'Peu importe (client déjà connu)',
            'destinataire_telephone': '0100000099',  # nouveau client
            'destinataire_nom': 'Nouveau Destinataire',
            'type_colis': self.type_colis.pk,
            'montant': 2500,
            'moyen_paiement': 'cash',
        })
        self.assertEqual(Colis.objects.count(), 1)
        colis = Colis.objects.first()
        self.assertRedirects(response, reverse('courrier:colis_detail', kwargs={'public_id': colis.public_id}))

        self.assertEqual(colis.gare_origine, self.gare_origine)
        self.assertEqual(colis.expediteur_id, self.client_existant.id)
        self.assertTrue(Client.objects.filter(telephone='0100000099').exists())
        # Le port est toujours payé par l'expéditeur, encaissé immédiatement — plus de choix "qui paie" dans le formulaire.
        self.assertEqual(colis.qui_paie, 'expediteur')
        self.assertTrue(colis.paye)
        self.assertEqual(colis.guichetier_enregistrement, self.guichetier)
        self.assertTrue(colis.code_colis.startswith('COL-ABJ'))
        self.assertEqual(len(colis.code_retrait), 6)

    def test_destination_egale_origine_refusee(self):
        # Un accès global choisit explicitement les deux gares (le champ gare_origine
        # n'est retiré du formulaire que pour les rôles rattachés à une seule gare) —
        # c'est ce cas que la validation croisée de ColisForm.clean() doit intercepter.
        manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager Test', role='manager',
        )
        form = ColisForm(data={
            'gare_origine': self.gare_origine.pk,
            'gare_destination': self.gare_origine.pk,
            'expediteur_telephone': '0100000001',
            'expediteur_nom': 'Test',
            'destinataire_telephone': '0100000002',
            'destinataire_nom': 'Test 2',
            'type_colis': self.type_colis.pk,
            'montant': 2500,
            'moyen_paiement': 'cash',
        }, user=manager)
        self.assertFalse(form.is_valid())
        self.assertIn('gare_destination', form.errors)

    def test_expediteur_et_destinataire_meme_telephone_refuse(self):
        form = ColisForm(data={
            'gare_destination': self.gare_dest.pk,
            'expediteur_telephone': '0100000005',
            'expediteur_nom': 'Test',
            'destinataire_telephone': '0100000005',
            'destinataire_nom': 'Test 2',
            'type_colis': self.type_colis.pk,
            'montant': 2500,
            'moyen_paiement': 'cash',
        }, user=self.guichetier)
        self.assertFalse(form.is_valid())
        self.assertIn('destinataire_telephone', form.errors)

    def test_enregistrement_refuse_via_la_vue_si_meme_telephone(self):
        self.client.force_login(self.guichetier)
        response = self.client.post(reverse('courrier:colis_create'), {
            'gare_destination': self.gare_dest.pk,
            'expediteur_telephone': '0100000006',
            'expediteur_nom': 'Test',
            'destinataire_telephone': '0100000006',
            'destinataire_nom': 'Test 2',
            'type_colis': self.type_colis.pk,
            'montant': 2500,
            'moyen_paiement': 'cash',
        })
        self.assertEqual(response.status_code, 200)  # re-rendu du formulaire avec l'erreur, pas de redirection
        self.assertEqual(Colis.objects.count(), 0)


class ColisListPaginationTests(TestCase):
    """La liste des colis doit être paginée par 20, les plus récents en premier."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager Test', role='manager',
        )
        for i in range(25):
            Colis.objects.create(
                gare_origine=self.gare, gare_destination=self.gare_dest,
                expediteur_nom=f'Expéditeur {i}', expediteur_telephone=f'01000001{i:02d}',
                destinataire_nom=f'Destinataire {i}', destinataire_telephone=f'01000002{i:02d}',
                type_colis=self.type_colis, montant=2500,
            )

    def test_pagination_par_20(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:colis_list'))
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['colis_liste']), 20)
        self.assertEqual(response.context['page_obj'].paginator.count, 25)

    def test_deuxieme_page(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:colis_list'), {'page': 2})
        self.assertEqual(len(response.context['colis_liste']), 5)


class ColisListAjaxTests(TestCase):
    """Filtrage en direct (recherche/statut) sans rechargement de page."""

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager Test', role='manager',
        )
        self.colis_jean = Colis.objects.create(
            gare_origine=self.gare, gare_destination=self.gare_dest,
            expediteur_nom='Jean Traoré', expediteur_telephone='0100000010',
            destinataire_nom='Awa Koné', destinataire_telephone='0100000011',
            type_colis=self.type_colis, montant=2500,
        )
        self.colis_marie = Colis.objects.create(
            gare_origine=self.gare, gare_destination=self.gare_dest,
            expediteur_nom='Marie Diallo', expediteur_telephone='0100000020',
            destinataire_nom='Issa Bamba', destinataire_telephone='0100000021',
            type_colis=self.type_colis, montant=2500,
        )

    def test_filtre_par_recherche(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:colis_list_ajax'), {'q': 'Jean'})
        self.assertContains(response, self.colis_jean.code_colis)
        self.assertNotContains(response, self.colis_marie.code_colis)
        self.assertEqual(response['X-Nb-Total'], '1')

    def test_sans_filtre_retourne_tout(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:colis_list_ajax'))
        self.assertContains(response, self.colis_jean.code_colis)
        self.assertContains(response, self.colis_marie.code_colis)
        self.assertEqual(response['X-Nb-Total'], '2')


class RoleAgentCourrierTests(TestCase):
    """
    Le rôle « Agent Courrier » doit donner accès aux écrans opérationnels du
    courrier, sans ouvrir pour autant les autres modules de gestion (garage)
    qui restent gérés par core.mixins.GestionRequiredMixin, volontairement
    non modifié — voir apps/courrier/mixins.py.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.agent_courrier = Utilisateur.objects.create_user(
            username='agentcourrier1', password='pass123',
            nom_complet='Fatou Courrier', role='agent_courrier', gare=self.gare,
        )

    def test_agent_courrier_accede_a_l_enregistrement_colis(self):
        self.client.force_login(self.agent_courrier)
        response = self.client.get(reverse('courrier:colis_create'))
        self.assertEqual(response.status_code, 200)

    def test_agent_courrier_accede_a_la_liste_de_chargement(self):
        self.client.force_login(self.agent_courrier)
        response = self.client.get(reverse('courrier:chargement_liste'))
        self.assertEqual(response.status_code, 200)

    def test_agent_courrier_refuse_sur_le_garage(self):
        self.client.force_login(self.agent_courrier)
        response = self.client.get(reverse('vehicules:reparation_create'))
        self.assertEqual(response.status_code, 403)


class AccesColisParGareTests(TestCase):
    """
    Un colis n'appartient qu'à sa gare d'origine tant qu'il n'est pas chargé
    sur un voyage. La gare de destination ne le découvre qu'une fois en
    transit — jamais dans sa liste de colis, seulement via la recherche de
    retrait (RetraitColisView). Toute autre gare n'y a jamais accès.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.gare_tierce = _creer_gare(self.compagnie, 'Gare Man', 'MAN', 'Man')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

        self.agent_origine = Utilisateur.objects.create_user(
            username='agent_origine', password='pass123',
            nom_complet='Agent Origine', role='guichetier', gare=self.gare_origine,
        )
        self.agent_dest = Utilisateur.objects.create_user(
            username='agent_dest', password='pass123',
            nom_complet='Agent Destination', role='guichetier', gare=self.gare_dest,
        )
        self.agent_tiers = Utilisateur.objects.create_user(
            username='agent_tiers', password='pass123',
            nom_complet='Agent Tiers', role='guichetier', gare=self.gare_tierce,
        )

        self.colis = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
        )

    def _detail_url(self):
        return reverse('courrier:colis_detail', kwargs={'public_id': self.colis.public_id})

    # ── Liste ────────────────────────────────────────────────────────
    def test_liste_montre_le_colis_a_la_gare_origine(self):
        self.client.force_login(self.agent_origine)
        response = self.client.get(reverse('courrier:colis_list'))
        self.assertContains(response, self.colis.code_colis)

    def test_liste_ne_montre_pas_le_colis_a_la_gare_destination_avant_chargement(self):
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:colis_list'))
        self.assertNotContains(response, self.colis.code_colis)

    # ── Fiche détail ─────────────────────────────────────────────────
    def test_fiche_accessible_a_la_gare_origine(self):
        self.client.force_login(self.agent_origine)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)

    def test_fiche_refusee_a_la_gare_destination_avant_chargement(self):
        self.client.force_login(self.agent_dest)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 403)

    def test_fiche_refusee_a_une_gare_tierce(self):
        self.client.force_login(self.agent_tiers)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 403)

    def test_fiche_accessible_a_la_gare_destination_une_fois_en_transit(self):
        self.colis.statut = 'en_transit'
        self.colis.save(update_fields=['statut'])
        self.client.force_login(self.agent_dest)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)

    # ── Annulation (réservée au rôle super_admin, voir AnnulationColisReserveeSuperAdminTests) ──
    def test_annulation_refusee_a_la_gare_destination(self):
        self.client.force_login(self.agent_dest)
        response = self.client.post(reverse('courrier:colis_annuler', kwargs={'public_id': self.colis.public_id}))
        self.assertEqual(response.status_code, 403)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    def test_annulation_refusee_a_la_gare_origine_si_pas_super_admin(self):
        self.client.force_login(self.agent_origine)
        response = self.client.post(reverse('courrier:colis_annuler', kwargs={'public_id': self.colis.public_id}))
        self.assertEqual(response.status_code, 403)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    # ── Recherche de retrait (avant/après arrivée) ──────────────────
    def test_recherche_retrait_trouve_le_colis_en_transit(self):
        self.colis.statut = 'en_transit'
        self.colis.save(update_fields=['statut'])
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:retrait'), {'q': self.colis.code_colis})
        self.assertContains(response, self.colis.code_colis)
        self.assertContains(response, 'en transit')
        self.assertIsNone(response.context['form'])

    def test_recherche_retrait_ne_trouve_pas_le_colis_encore_enregistre(self):
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:retrait'), {'q': self.colis.code_colis})
        self.assertIsNone(response.context['colis'])


class CourrierDashboardScopeTests(TestCase):
    """
    Le tableau de bord Courrier doit être scopé par gare comme le reste du
    module : un utilisateur sans accès global (chef_gare, guichetier,
    agent_courrier) ne doit voir que les chiffres de sa propre gare, tandis
    que pdg/super_admin/manager (has_global_access) voient le cumul de
    toutes les gares.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_a = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_b = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

        self.chef_gare_a = Utilisateur.objects.create_user(
            username='chef_a', password='pass123',
            nom_complet='Chef Gare A', role='chef_gare', gare=self.gare_a,
        )
        self.guichetier_b = Utilisateur.objects.create_user(
            username='guichetier_b', password='pass123',
            nom_complet='Guichetier B', role='guichetier', gare=self.gare_b,
        )
        self.pdg = Utilisateur.objects.create_user(
            username='pdg_global', password='pass123',
            nom_complet='PDG', role='pdg',
        )

        # Un colis enregistré et payé aujourd'hui à la gare A.
        self.colis_a = Colis.objects.create(
            gare_origine=self.gare_a, gare_destination=self.gare_b,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            paye=True, date_paiement=timezone.now(),
        )

    def _dashboard(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('courrier:dashboard'))

    def test_chef_gare_ne_voit_que_les_colis_de_sa_gare(self):
        response = self._dashboard(self.chef_gare_a)
        self.assertEqual(response.context['colis_enregistres_today'], 1)
        self.assertEqual(response.context['montant_today'], 2500)

    def test_guichetier_dune_autre_gare_ne_voit_rien_de_ce_colis(self):
        response = self._dashboard(self.guichetier_b)
        self.assertEqual(response.context['colis_enregistres_today'], 0)
        self.assertEqual(response.context['montant_today'], 0)

    def test_pdg_voit_le_cumul_de_toutes_les_gares(self):
        response = self._dashboard(self.pdg)
        self.assertEqual(response.context['colis_enregistres_today'], 1)
        self.assertEqual(response.context['montant_today'], 2500)


class RetraitHistoriqueListViewTests(TestCase):
    """
    Sous-menu « Historique Retrait » : les colis retirés, les plus récents
    en premier, paginés par 20 (même pagination que ColisListView), et
    scopés par gare de destination — c'est elle qui effectue le retrait.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.gare_tierce = _creer_gare(self.compagnie, 'Gare Man', 'MAN', 'Man')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

        self.agent_dest = Utilisateur.objects.create_user(
            username='agent_dest', password='pass123',
            nom_complet='Agent Destination', role='guichetier', gare=self.gare_dest,
        )
        self.agent_tiers = Utilisateur.objects.create_user(
            username='agent_tiers', password='pass123',
            nom_complet='Agent Tiers', role='guichetier', gare=self.gare_tierce,
        )
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager Test', role='manager',
        )

        self.colis_retire = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
            statut='retire', retirant_nom='Koffi Mandataire', retirant_telephone='0700000099',
            date_retrait=timezone.now(),
        )
        self.colis_non_retire = Colis.objects.create(
            gare_origine=self.gare_origine, gare_destination=self.gare_dest,
            expediteur_nom='Autre Expéditeur', expediteur_telephone='0100000003',
            destinataire_nom='Autre Destinataire', destinataire_telephone='0100000004',
            type_colis=self.type_colis, montant=2500,
        )

    def test_liste_le_colis_retire_avec_le_retirant(self):
        self.client.force_login(self.agent_dest)
        response = self.client.get(reverse('courrier:retrait_historique'))
        self.assertContains(response, self.colis_retire.code_colis)
        self.assertContains(response, 'Koffi Mandataire')
        self.assertContains(response, '0700000099')
        self.assertNotContains(response, self.colis_non_retire.code_colis)

    def test_gare_tierce_ne_voit_pas_lhistorique_dune_autre_gare(self):
        self.client.force_login(self.agent_tiers)
        response = self.client.get(reverse('courrier:retrait_historique'))
        self.assertNotContains(response, self.colis_retire.code_colis)

    def test_acces_global_voit_toutes_les_gares(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:retrait_historique'))
        self.assertContains(response, self.colis_retire.code_colis)

    def test_pagination_par_20(self):
        for i in range(25):
            Colis.objects.create(
                gare_origine=self.gare_origine, gare_destination=self.gare_dest,
                expediteur_nom=f'Expéditeur {i}', expediteur_telephone=f'01000005{i:02d}',
                destinataire_nom=f'Destinataire {i}', destinataire_telephone=f'01000006{i:02d}',
                type_colis=self.type_colis, montant=2500,
                statut='retire', retirant_nom=f'Retirant {i}', retirant_telephone=f'01000007{i:02d}',
                date_retrait=timezone.now(),
            )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:retrait_historique'))
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['colis_liste']), 20)
        self.assertEqual(response.context['page_obj'].paginator.count, 26)


class ChargementListeVoyagesDateTests(TestCase):
    """
    L'écran « Chargement colis — départs à venir » ne doit montrer que les
    départs du jour et à venir : un voyage déjà passé ne peut plus recevoir
    de colis (l'agent ne peut pas physiquement charger un véhicule qui est
    déjà parti).
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)
        self.ligne = Ligne.objects.create(
            nom='Abidjan - Bouaké', gare=self.gare,
            ville_depart='Abidjan', ville_arrivee='Bouaké', compagnie=self.compagnie,
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Jean Guichetier', role='guichetier', gare=self.gare,
        )

        today = timezone.now().date()
        self.voyage_passe = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne,
            date_depart=today - timedelta(days=200), heure_depart=time(8, 0), periode='matin',
        )
        self.voyage_aujourdhui = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne,
            date_depart=today, heure_depart=time(8, 0), periode='matin',
        )
        self.voyage_futur = Voyage.objects.create(
            gare=self.gare, ligne=self.ligne,
            date_depart=today + timedelta(days=5), heure_depart=time(8, 0), periode='matin',
        )
        self.colis = Colis.objects.create(
            gare_origine=self.gare, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
        )

    def test_voyage_passe_absent_de_la_liste(self):
        self.client.force_login(self.guichetier)
        response = self.client.get(reverse('courrier:chargement_liste'))
        voyages = [info['voyage'] for info in response.context['voyages_info']]
        self.assertNotIn(self.voyage_passe, voyages)
        self.assertIn(self.voyage_aujourdhui, voyages)
        self.assertIn(self.voyage_futur, voyages)

    def test_chargement_refuse_sur_un_voyage_passe(self):
        self.client.force_login(self.guichetier)
        response = self.client.post(
            reverse('courrier:chargement_voyage', kwargs={'public_id': self.voyage_passe.public_id}),
            {'colis_id': [str(self.colis.public_id)]},
        )
        self.assertRedirects(response, reverse('courrier:chargement_voyage', kwargs={'public_id': self.voyage_passe.public_id}))
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    def test_chargement_autorise_sur_un_voyage_du_jour(self):
        self.client.force_login(self.guichetier)
        response = self.client.post(
            reverse('courrier:chargement_voyage', kwargs={'public_id': self.voyage_aujourdhui.public_id}),
            {'colis_id': [str(self.colis.public_id)]},
        )
        self.assertRedirects(response, reverse('courrier:chargement_voyage', kwargs={'public_id': self.voyage_aujourdhui.public_id}))
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'en_transit')


class AnnulationColisReserveeSuperAdminTests(TestCase):
    """
    L'annulation d'un colis n'est plus une action de guichet courant : seul
    le rôle super_admin (ou is_superuser) peut le faire, quelle que soit sa
    gare — ni la gare d'origine, ni pdg/manager (pourtant à accès global
    partout ailleurs dans le module) n'y ont accès. Le bouton lui-même est
    masqué côté template (colis_detail.html, via peut_annuler_colis) mais
    la vraie garde est ici, côté vue.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        self.gare_dest = _creer_gare(self.compagnie, 'Gare Bouaké', 'BKE', 'Bouaké')
        self.type_colis = TypeColis.objects.create(nom='Petit colis', tarif_indicatif=2500, compagnie=self.compagnie)

        self.super_admin = Utilisateur.objects.create_user(
            username='super_admin1', password='pass123',
            nom_complet='Super Admin', role='super_admin',
        )
        self.pdg = Utilisateur.objects.create_user(
            username='pdg1', password='pass123',
            nom_complet='PDG', role='pdg',
        )
        self.manager = Utilisateur.objects.create_user(
            username='manager1', password='pass123',
            nom_complet='Manager', role='manager',
        )
        self.guichetier = Utilisateur.objects.create_user(
            username='guichetier1', password='pass123',
            nom_complet='Guichetier', role='guichetier', gare=self.gare,
        )
        self.superuser_django = Utilisateur.objects.create_superuser(
            username='django_super', password='pass123',
            nom_complet='Superuser Django', role='guichetier', gare=self.gare,
        )

        self.colis = Colis.objects.create(
            gare_origine=self.gare, gare_destination=self.gare_dest,
            expediteur_nom='Jean Expéditeur', expediteur_telephone='0100000001',
            destinataire_nom='Awa Destinataire', destinataire_telephone='0100000002',
            type_colis=self.type_colis, montant=2500,
        )

    def _annuler(self, user):
        self.client.force_login(user)
        return self.client.post(reverse('courrier:colis_annuler', kwargs={'public_id': self.colis.public_id}))

    def test_super_admin_peut_annuler(self):
        response = self._annuler(self.super_admin)
        self.assertEqual(response.status_code, 302)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'annule')

    def test_is_superuser_django_peut_annuler(self):
        response = self._annuler(self.superuser_django)
        self.assertEqual(response.status_code, 302)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'annule')

    def test_pdg_ne_peut_pas_annuler(self):
        response = self._annuler(self.pdg)
        self.assertEqual(response.status_code, 403)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    def test_manager_ne_peut_pas_annuler(self):
        response = self._annuler(self.manager)
        self.assertEqual(response.status_code, 403)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    def test_guichetier_ne_peut_pas_annuler(self):
        response = self._annuler(self.guichetier)
        self.assertEqual(response.status_code, 403)
        self.colis.refresh_from_db()
        self.assertEqual(self.colis.statut, 'enregistre')

    def test_bouton_annuler_absent_pour_un_manager(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('courrier:colis_detail', kwargs={'public_id': self.colis.public_id}))
        self.assertNotContains(response, 'Annuler le colis')

    def test_bouton_annuler_visible_pour_un_super_admin(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse('courrier:colis_detail', kwargs={'public_id': self.colis.public_id}))
        self.assertContains(response, 'Annuler le colis')


class GaresPourVoyageAccentTests(TestCase):
    """
    Ligne et Gare sont deux formulaires de saisie indépendants — rien ne
    garantit que 'ville_arrivee' d'une ligne et 'ville' d'une gare soient
    orthographiés à l'identique (accents notamment). _gares_pour_voyage doit
    reconnaître 'BOUAKÉ' et 'BOUAKE' comme la même ville, sinon l'écran de
    chargement affiche « Sans gare compagnie » et masque le bouton Charger
    alors que la gare existe bel et bien.
    """

    def setUp(self):
        self.compagnie = Compagnie.objects.create(nom='Ma Compagnie', nom_pdg='M. PDG')
        self.gare_origine = _creer_gare(self.compagnie, 'Gare Abidjan', 'ABJ', 'Abidjan')
        # Gare enregistrée sans accent...
        self.gare_bouake = _creer_gare(self.compagnie, 'Gare Bouake', 'BKE', 'BOUAKE')
        self.ligne = Ligne.objects.create(
            nom='Abidjan - Bouaké', gare=self.gare_origine,
            # ...alors que la ligne, elle, a été saisie avec l'accent.
            ville_depart='Abidjan', ville_arrivee='BOUAKÉ', compagnie=self.compagnie,
        )
        self.voyage = Voyage.objects.create(
            gare=self.gare_origine, ligne=self.ligne,
            date_depart=date(2026, 9, 1), heure_depart=time(7, 30), periode='matin',
        )

    def test_gare_reconnue_malgre_la_difference_daccent(self):
        gares = _gares_pour_voyage(self.voyage)
        self.assertIn(self.gare_bouake, gares)

    def test_ecran_chargement_propose_le_bouton_charger(self):
        guichetier = Utilisateur.objects.create_user(
            username='guichetier_abj', password='pass123',
            nom_complet='Guichetier Abidjan', role='guichetier', gare=self.gare_origine,
        )
        self.client.force_login(guichetier)
        response = self.client.get(reverse('courrier:chargement_liste'))
        self.assertContains(response, 'Charger')
        self.assertNotContains(response, 'Sans gare compagnie')
