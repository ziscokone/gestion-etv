from django.db import migrations

MODULES = [
    {'cle': 'voyages',   'nom': 'Gestion des Voyages',   'description': 'Billets, réservations et tableau de bord', 'icone': 'bi-bus-front-fill',        'url_name': 'guichet:dashboard',          'ordre': 1},
    {'cle': 'trajets',   'nom': 'Gestion des Trajets',   'description': 'Lignes, destinations et grilles tarifaires', 'icone': 'bi-signpost-split-fill', 'url_name': 'lignes:ligne_list',          'ordre': 2},
    {'cle': 'personnel', 'nom': 'Gestion du Personnel',  'description': 'Utilisateurs, chauffeurs et convoyeurs',    'icone': 'bi-people-fill',           'url_name': 'personnel:utilisateur_list', 'ordre': 3},
    {'cle': 'parc',      'nom': 'Parc Automobile',       'description': 'Flotte de véhicules et suivi technique',   'icone': 'bi-truck-front-fill',       'url_name': 'vehicules:vehicule_list',    'ordre': 4},
    {'cle': 'garage',    'nom': 'Gestion du Garage',     'description': 'Réparations et maintenance des véhicules', 'icone': 'bi-tools',                  'url_name': 'vehicules:reparation_list',  'ordre': 5},
]


def insert_modules(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    for data in MODULES:
        Module.objects.get_or_create(cle=data['cle'], defaults=data)


def remove_modules(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    Module.objects.filter(cle__in=[m['cle'] for m in MODULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('personnel', '0004_add_module_and_m2m_acces'),
    ]

    operations = [
        migrations.RunPython(insert_modules, remove_modules),
    ]
