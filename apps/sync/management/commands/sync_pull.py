"""
Commande à exécuter sur un POSTE GARE hors-ligne (jamais sur le serveur central).
Récupère depuis le serveur central les données de référence à jour pour cette gare
si une connexion est disponible, sinon s'arrête silencieusement.

La même logique est utilisée par le bouton "Synchroniser maintenant" de l'écran
de statut (apps.sync.client).
"""
from django.core.management.base import BaseCommand

from apps.sync import client


class Command(BaseCommand):
    help = "Récupère depuis le serveur central les données de référence à jour pour cette gare."

    def handle(self, *args, **options):
        resultat = client.executer_pull()

        if not resultat['ok']:
            self.stderr.write(resultat['message'])
            return

        self.stdout.write(self.style.SUCCESS(resultat['message']))
