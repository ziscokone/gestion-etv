from django.db import migrations


def set_dashboard_url(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    Module.objects.filter(cle='courrier').update(url_name='courrier:dashboard')


def set_colis_list_url(apps, schema_editor):
    Module = apps.get_model('personnel', 'Module')
    Module.objects.filter(cle='courrier').update(url_name='courrier:colis_list')


class Migration(migrations.Migration):

    dependencies = [
        ('courrier', '0004_colis_date_reception_colis_guichetier_reception_and_more'),
    ]

    operations = [
        migrations.RunPython(set_dashboard_url, set_colis_list_url),
    ]
