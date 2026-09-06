from django.core.management.base import BaseCommand, CommandError

from apps.gares.models import Gare, GareSyncToken


class Command(BaseCommand):
    help = (
        "Génère (ou régénère) le jeton de synchronisation d'une gare, à exécuter sur le "
        "serveur CENTRAL. Le jeton en clair n'est affiché qu'une seule fois : à copier "
        "immédiatement dans le SYNC_TOKEN du fichier .env du poste gare concerné."
    )

    def add_arguments(self, parser):
        parser.add_argument('code_gare', help="Code de la gare (ex: CKY)")

    def handle(self, *args, **options):
        code = options['code_gare']
        try:
            gare = Gare.objects.get(code=code)
        except Gare.DoesNotExist:
            raise CommandError(f"Aucune gare avec le code '{code}'.")

        token = GareSyncToken.generer_pour(gare)

        self.stdout.write(self.style.SUCCESS(f"Jeton généré pour {gare.nom} ({gare.code}) :"))
        self.stdout.write("")
        self.stdout.write(token)
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "Ce jeton ne sera plus jamais affiché. Copiez-le maintenant dans le fichier "
            ".env du poste gare (variable SYNC_TOKEN). Toute génération ultérieure pour "
            "cette même gare invalidera ce jeton."
        ))
