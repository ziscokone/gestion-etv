import django.db.models.deletion
from django.db import migrations, models


def migrer_vers_lignes(apps, schema_editor):
    """
    Pour chaque ReparationVehicule existante, crée une LigneIntervention
    en copiant les champs qui y migrent.
    """
    ReparationVehicule = apps.get_model('vehicules', 'ReparationVehicule')
    LigneIntervention = apps.get_model('vehicules', 'LigneIntervention')

    for rep in ReparationVehicule.objects.all():
        LigneIntervention.objects.create(
            reparation=rep,
            ordre=1,
            type_reparation=rep.type_reparation,
            description=rep.description or '',
            montant=rep.montant,
            kilometrage=rep.kilometrage,
            pieces_remplacees=rep.pieces_remplacees or '',
            huile_utilisee=rep.huile_utilisee or '',
            intervalle_km=rep.intervalle_vidange,
            creee_depuis_guichet=rep.creee_depuis_guichet,
            voyage_source=rep.voyage_source,
        )


def rollback_lignes(apps, schema_editor):
    """Rollback : supprime toutes les lignes créées."""
    LigneIntervention = apps.get_model('vehicules', 'LigneIntervention')
    LigneIntervention.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0006_vidange_kilometrage'),
        ('voyages', '0001_initial'),
    ]

    operations = [
        # ── 1. Nouveau champ sur TypeReparation ──────────────────────────
        migrations.AddField(
            model_name='typereparation',
            name='intervalle_km_defaut',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Intervalle km (défaut)',
                help_text='Si renseigné, ce type sera suivi par kilométrage'
            ),
        ),

        # ── 2. Notes sur ReparationVehicule ──────────────────────────────
        migrations.AddField(
            model_name='reparationvehicule',
            name='notes',
            field=models.TextField(
                blank=True,
                verbose_name='Notes générales',
                help_text='Observations globales sur cette entrée au garage'
            ),
        ),

        # ── 3. Nouveau modèle LigneIntervention ──────────────────────────
        migrations.CreateModel(
            name='LigneIntervention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(default=1, verbose_name='Ordre')),
                ('description', models.TextField(verbose_name='Description')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Montant (FCFA)')),
                ('kilometrage', models.PositiveIntegerField(blank=True, null=True, verbose_name='Kilométrage au compteur')),
                ('pieces_remplacees', models.TextField(blank=True, verbose_name='Pièces remplacées')),
                ('huile_utilisee', models.CharField(blank=True, max_length=200, verbose_name='Huile utilisée')),
                ('intervalle_km', models.PositiveIntegerField(blank=True, null=True, verbose_name='Intervalle km')),
                ('creee_depuis_guichet', models.BooleanField(default=False, verbose_name='Créée depuis le guichet')),
                ('reparation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='vehicules.reparationvehicule', verbose_name='Réparation')),
                ('type_reparation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes', to='vehicules.typereparation', verbose_name="Type d'intervention")),
                ('voyage_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lignes_reparation', to='voyages.voyage', verbose_name='Voyage source')),
            ],
            options={
                'verbose_name': "Ligne d'intervention",
                'verbose_name_plural': "Lignes d'intervention",
                'ordering': ['reparation', 'ordre'],
            },
        ),

        # ── 4. Data migration : copie vers LigneIntervention ─────────────
        migrations.RunPython(migrer_vers_lignes, rollback_lignes),

        # ── 5. Suppression des anciens champs de ReparationVehicule ──────
        migrations.RemoveField(model_name='reparationvehicule', name='type_reparation'),
        migrations.RemoveField(model_name='reparationvehicule', name='description'),
        migrations.RemoveField(model_name='reparationvehicule', name='montant'),
        migrations.RemoveField(model_name='reparationvehicule', name='kilometrage'),
        migrations.RemoveField(model_name='reparationvehicule', name='pieces_remplacees'),
        migrations.RemoveField(model_name='reparationvehicule', name='huile_utilisee'),
        migrations.RemoveField(model_name='reparationvehicule', name='intervalle_vidange'),
        migrations.RemoveField(model_name='reparationvehicule', name='creee_depuis_guichet'),
        migrations.RemoveField(model_name='reparationvehicule', name='voyage_source'),
    ]
