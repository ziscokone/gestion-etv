from django.db import migrations

MODULE_DATA = {
    'cle': 'courrier',
    'nom': 'Gestion du Courrier',
    'description': 'Expédition et retrait de colis entre gares',
    'icone': 'bi-box-seam-fill',
    'url_name': 'courrier:colis_list',
    'ordre': 6,
}


def insert_module(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    Module.objects.get_or_create(cle=MODULE_DATA['cle'], defaults=MODULE_DATA)


def remove_module(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    Module.objects.filter(cle=MODULE_DATA['cle']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courrier', '0001_initial'),
        ('personnel', '0005_populate_modules'),
    ]

    operations = [
        migrations.RunPython(insert_module, remove_module),
    ]
