from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


TYPES_DEFAUT = [
    ('Carte grise', False),
    ('Assurance', True),
    ('Visite technique', True),
    ('Licence de transport', True),
    ('Patente', True),
    ('Carte de stationnement', False),
    ('Autre', False),
]


def creer_types_defaut(apps, schema_editor):
    TypeDocumentVehicule = apps.get_model('vehicules', 'TypeDocumentVehicule')
    for nom, a_date_expiration in TYPES_DEFAUT:
        TypeDocumentVehicule.objects.get_or_create(
            nom=nom, defaults={'a_date_expiration': a_date_expiration}
        )


def supprimer_types_defaut(apps, schema_editor):
    TypeDocumentVehicule = apps.get_model('vehicules', 'TypeDocumentVehicule')
    TypeDocumentVehicule.objects.filter(nom__in=[nom for nom, _ in TYPES_DEFAUT]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0010_creditpiecegarage_versementcredit'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TypeDocumentVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, unique=True, verbose_name='Nom')),
                ('a_date_expiration', models.BooleanField(default=False, help_text="Si coché, le champ date d'expiration sera demandé/affiché lors de l'ajout d'un document de ce type.", verbose_name="Date d'expiration requise")),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Type de document véhicule',
                'verbose_name_plural': 'Types de documents véhicule',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='DocumentVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(blank=True, max_length=200, verbose_name='Nom du document')),
                ('fichier', models.FileField(upload_to='vehicules/documents/', verbose_name='Fichier')),
                ('date_expiration', models.DateField(blank=True, null=True, verbose_name="Date d'expiration")),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
                ('ajoute_par', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documents_vehicules_ajoutes', to=settings.AUTH_USER_MODEL)),
                ('type_document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='documents', to='vehicules.typedocumentvehicule', verbose_name='Type de document')),
                ('vehicule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='vehicules.vehicule')),
            ],
            options={
                'verbose_name': 'Document véhicule',
                'verbose_name_plural': 'Documents véhicule',
                'ordering': ['type_document__nom', '-date_ajout'],
            },
        ),
        migrations.RunPython(creer_types_defaut, supprimer_types_defaut),
    ]
