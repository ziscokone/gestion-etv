# Generated manually for adding moyen_paiement field

from django.db import migrations, models


def set_default_moyen_paiement(apps, schema_editor):
    """Met à jour tous les billets existants avec moyen_paiement='cash'"""
    Billet = apps.get_model('billets', 'Billet')
    Billet.objects.filter(moyen_paiement__isnull=True).update(moyen_paiement='cash')
    Billet.objects.filter(moyen_paiement='').update(moyen_paiement='cash')


def reverse_migration(apps, schema_editor):
    """Reverse migration - ne fait rien"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billets', '0003_billet_destination_alter_billet_montant'),
    ]

    operations = [
        migrations.AddField(
            model_name='billet',
            name='moyen_paiement',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('wave', 'Wave'),
                    ('orange_money', 'Orange Money'),
                    ('mtn_money', 'MTN Money'),
                    ('moov_money', 'Moov Money'),
                ],
                default='cash',
                max_length=20,
                verbose_name='Moyen de paiement',
            ),
        ),
        migrations.RunPython(set_default_moyen_paiement, reverse_migration),
    ]
