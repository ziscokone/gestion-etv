from django.db import migrations, models


def migrer_is_vidange_vers_necessite_km(apps, schema_editor):
    """Les types déjà marqués is_vidange=True → necessite_kilometrage=True."""
    TypeReparation = apps.get_model('vehicules', 'TypeReparation')
    TypeReparation.objects.filter(is_vidange=True).update(necessite_kilometrage=True)


class Migration(migrations.Migration):

    dependencies = [
        ('vehicules', '0007_ligneintervention'),
    ]

    operations = [
        migrations.AddField(
            model_name='typereparation',
            name='necessite_kilometrage',
            field=models.BooleanField(
                default=False,
                verbose_name='Nécessite saisie kilométrage',
                help_text="Cocher si ce type d'intervention nécessite de saisir le km au compteur"
            ),
        ),
        migrations.RunPython(
            migrer_is_vidange_vers_necessite_km,
            migrations.RunPython.noop
        ),
    ]
