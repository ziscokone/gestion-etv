from django.core.management.base import BaseCommand
from apps.comptabilite.models import TypeDepense
from apps.compagnie.models import Compagnie


class Command(BaseCommand):
    help = 'Initialise les types de dépenses par défaut pour toutes les compagnies'

    def handle(self, *args, **options):
        """Crée les 5 types de dépenses par défaut."""

        # Types de dépenses à créer
        types_defaut = [
            {
                'code': 'carburant',
                'nom': 'Carburant',
                'description_obligatoire': False,
                'ordre': 1
            },
            {
                'code': 'frais_chauffeur',
                'nom': 'Frais Chauffeur',
                'description_obligatoire': False,
                'ordre': 2
            },
            {
                'code': 'frais_route',
                'nom': 'Frais de Route',
                'description_obligatoire': False,
                'ordre': 3
            },
            {
                'code': 'ration',
                'nom': 'Ration',
                'description_obligatoire': False,
                'ordre': 4
            },
            {
                'code': 'reparation',
                'nom': 'Réparation',
                'description_obligatoire': True,  # Description obligatoire pour "Réparation"
                'ordre': 5
            },
            {
                'code': 'divers',
                'nom': 'Divers',
                'description_obligatoire': True,  # Description obligatoire pour "Divers"
                'ordre': 6
            },
        ]

        # Récupérer toutes les compagnies
        compagnies = Compagnie.objects.all()

        if not compagnies.exists():
            self.stdout.write(
                self.style.WARNING('Aucune compagnie trouvée. Créez d\'abord une compagnie.')
            )
            return

        total_created = 0
        total_existing = 0

        for compagnie in compagnies:
            self.stdout.write(f'\nTraitement de la compagnie: {compagnie.nom}')

            for type_data in types_defaut:
                type_depense, created = TypeDepense.objects.get_or_create(
                    compagnie=compagnie,
                    code=type_data['code'],
                    defaults={
                        'nom': type_data['nom'],
                        'description_obligatoire': type_data['description_obligatoire'],
                        'ordre': type_data['ordre'],
                        'actif': True
                    }
                )

                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Type créé: {type_depense.nom}')
                    )
                else:
                    total_existing += 1
                    self.stdout.write(
                        self.style.WARNING(f'  - Type existant: {type_depense.nom}')
                    )

        # Résumé
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {total_created} type(s) de dépense créé(s)'
            )
        )
        if total_existing > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'- {total_existing} type(s) déjà existant(s)'
                )
            )
        self.stdout.write('='*60)
