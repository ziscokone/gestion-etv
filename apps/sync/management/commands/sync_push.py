"""
Commande à exécuter sur un POSTE GARE hors-ligne (jamais sur le serveur central).
Envoie les nouveautés locales (Voyages/Billets/Clients/Dépenses) vers le serveur
central si une connexion est disponible, sinon s'arrête silencieusement.

Prévu pour être lancé périodiquement par le Planificateur de tâches Windows
(voir DEPLOIEMENT_GARE_HORS_LIGNE.md). La même logique est utilisée par le bouton
"Synchroniser maintenant" de l'écran de statut (apps.sync.client).
"""
from django.core.management.base import BaseCommand

from apps.sync import client


class Command(BaseCommand):
    help = "Envoie vers le serveur central les nouveautés de cette gare, si une connexion est disponible."

    def handle(self, *args, **options):
        resultat = client.executer_push()

        if not resultat['ok']:
            self.stderr.write(resultat['message'])
            return

        self.stdout.write(self.style.SUCCESS(resultat['message']))
        for erreur in resultat.get('erreurs', []):
            self.stdout.write(f"  - {erreur['type']} {erreur['public_id']} : {erreur['message']}")
