# Generated manually for making destination field optional

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programmes', '0002_programmedepart_numero_depart'),
    ]

    operations = [
        migrations.AlterField(
            model_name='programmedepart',
            name='destination',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='programmes',
                to='destinations.destination',
                verbose_name='Destination',
            ),
        ),
    ]
