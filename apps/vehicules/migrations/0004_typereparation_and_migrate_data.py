from django.db import migrations, models
import django.db.models.deletion


def create_initial_types(apps, schema_editor):
    """Crée les types de réparation initiaux."""
    TypeReparation = apps.get_model('vehicules', 'TypeReparation')

    types_initiaux = [
        ('Mécanique', 'Réparations mécaniques (moteur, transmission, freins, etc.)'),
        ('Carrosserie', 'Réparations de carrosserie (tôlerie, peinture, etc.)'),
        ('Électrique', 'Réparations électriques (batterie, alternateur, éclairage, etc.)'),
        ('Pneumatiques', 'Changement et réparation de pneus'),
        ('Révision', 'Révisions périodiques et entretien courant'),
        ('Autre', 'Autres types de réparations'),
    ]

    for nom, description in types_initiaux:
        TypeReparation.objects.get_or_create(
            nom=nom,
            defaults={'description': description, 'actif': True}
        )


def migrate_type_reparation_data(apps, schema_editor):
    """Migre les anciennes valeurs vers les nouvelles FK."""
    ReparationVehicule = apps.get_model('vehicules', 'ReparationVehicule')
    TypeReparation = apps.get_model('vehicules', 'TypeReparation')

    # Mapping des anciens codes vers les nouveaux noms
    mapping = {
        'mecanique': 'Mécanique',
        'carrosserie': 'Carrosserie',
        'electrique': 'Électrique',
        'pneumatiques': 'Pneumatiques',
        'revision': 'Révision',
        'autre': 'Autre',
    }

    for reparation in ReparationVehicule.objects.all():
        if reparation.type_reparation_old:
            nom_type = mapping.get(reparation.type_reparation_old, 'Autre')
            type_obj = TypeReparation.objects.filter(nom=nom_type).first()
            if type_obj:
                reparation.type_reparation_new = type_obj
                reparation.save()


def reverse_migrate_type_reparation_data(apps, schema_editor):
    """Reverse migration - restaure les anciennes valeurs."""
    ReparationVehicule = apps.get_model('vehicules', 'ReparationVehicule')

    # Mapping inverse
    mapping = {
        'Mécanique': 'mecanique',
        'Carrosserie': 'carrosserie',
        'Électrique': 'electrique',
        'Pneumatiques': 'pneumatiques',
        'Révision': 'revision',
        'Autre': 'autre',
    }

    for reparation in ReparationVehicule.objects.all():
        if reparation.type_reparation_new:
            code = mapping.get(reparation.type_reparation_new.nom, 'autre')
            reparation.type_reparation_old = code
            reparation.save()


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0003_remove_reparationvehicule_facture'),
    ]

    operations = [
        # 1. Créer le modèle TypeReparation
        migrations.CreateModel(
            name='TypeReparation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, unique=True, verbose_name='Nom')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Type de réparation',
                'verbose_name_plural': 'Types de réparation',
                'ordering': ['nom'],
            },
        ),

        # 2. Créer les types initiaux
        migrations.RunPython(create_initial_types, migrations.RunPython.noop),

        # 3. Renommer l'ancien champ
        migrations.RenameField(
            model_name='reparationvehicule',
            old_name='type_reparation',
            new_name='type_reparation_old',
        ),

        # 4. Ajouter le nouveau champ FK (nullable temporairement)
        migrations.AddField(
            model_name='reparationvehicule',
            name='type_reparation_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='reparations_new',
                to='vehicules.typereparation',
                verbose_name='Type de réparation'
            ),
        ),

        # 5. Migrer les données
        migrations.RunPython(migrate_type_reparation_data, reverse_migrate_type_reparation_data),

        # 6. Supprimer l'ancien champ
        migrations.RemoveField(
            model_name='reparationvehicule',
            name='type_reparation_old',
        ),

        # 7. Renommer le nouveau champ
        migrations.RenameField(
            model_name='reparationvehicule',
            old_name='type_reparation_new',
            new_name='type_reparation',
        ),

        # 8. Rendre le champ non-nullable et corriger le related_name
        migrations.AlterField(
            model_name='reparationvehicule',
            name='type_reparation',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='reparations',
                to='vehicules.typereparation',
                verbose_name='Type de réparation'
            ),
        ),
    ]
