from django.db import migrations

TYPES = [
    {'nom': 'Enveloppe / Document', 'tarif_indicatif': 1000, 'ordre': 1},
    {'nom': 'Petit colis', 'tarif_indicatif': 2500, 'ordre': 2},
    {'nom': 'Colis moyen', 'tarif_indicatif': 5000, 'ordre': 3},
    {'nom': 'Colis volumineux', 'tarif_indicatif': 8000, 'ordre': 4},
]


def creer_types(apps, schema_editor):
    Compagnie = apps.get_model('compagnie', 'Compagnie')
    TypeColis = apps.get_model('courrier', 'TypeColis')
    compagnie = Compagnie.objects.first()
    if not compagnie:
        return
    for data in TYPES:
        TypeColis.objects.get_or_create(compagnie=compagnie, nom=data['nom'], defaults=data)


def supprimer_types(apps, schema_editor):
    TypeColis = apps.get_model('courrier', 'TypeColis')
    TypeColis.objects.filter(nom__in=[t['nom'] for t in TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courrier', '0002_seed_module_courrier'),
    ]

    operations = [
        migrations.RunPython(creer_types, supprimer_types),
    ]
