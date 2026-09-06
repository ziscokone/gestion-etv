import django.db.models.deletion
from django.db import migrations, models


TYPES_DEFAUT = [
    "CNI (Carte Nationale d'Identité)",
    'Permis de conduire',
    'Certificat médical',
    'Casier judiciaire',
    'Contrat de travail',
    'Autre',
]

CORRESPONDANCE = {
    'cni':                "CNI (Carte Nationale d'Identité)",
    'permis':             "Permis de conduire",
    'certificat_medical': "Certificat médical",
    'casier_judiciaire':  "Casier judiciaire",
    'contrat':            "Contrat de travail",
    'autre':              "Autre",
}


def creer_types_et_migrer(apps, schema_editor):
    TypeDocumentChauffeur = apps.get_model('personnel', 'TypeDocumentChauffeur')
    DocumentChauffeur = apps.get_model('personnel', 'DocumentChauffeur')

    for nom in TYPES_DEFAUT:
        TypeDocumentChauffeur.objects.get_or_create(nom=nom)

    for doc in DocumentChauffeur.objects.all():
        ancien_code = doc.type_document_legacy
        nom_type = CORRESPONDANCE.get(ancien_code, 'Autre')
        type_obj, _ = TypeDocumentChauffeur.objects.get_or_create(nom=nom_type)
        doc.type_document_new = type_obj
        doc.save(update_fields=['type_document_new'])


def rollback(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('personnel', '0006_add_document_chauffeur'),
    ]

    operations = [
        # 1. Créer le modèle TypeDocumentChauffeur
        migrations.CreateModel(
            name='TypeDocumentChauffeur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, unique=True, verbose_name='Nom')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Type de document chauffeur',
                'verbose_name_plural': 'Types de documents chauffeur',
                'ordering': ['nom'],
            },
        ),

        # 2. Neutraliser l'ordering AVANT de toucher au champ (évite FieldError)
        migrations.AlterModelOptions(
            name='documentchauffeur',
            options={'ordering': ['-date_ajout'], 'verbose_name': 'Document chauffeur'},
        ),

        # 3. Renommer l'ancien CharField pour pouvoir lire les valeurs
        migrations.RenameField(
            model_name='documentchauffeur',
            old_name='type_document',
            new_name='type_document_legacy',
        ),

        # 4. Ajouter le nouveau FK nullable temporairement
        migrations.AddField(
            model_name='documentchauffeur',
            name='type_document_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='personnel.typedocumentchauffeur',
                verbose_name='Type de document',
            ),
        ),

        # 5. Créer les types par défaut et migrer les données existantes
        migrations.RunPython(creer_types_et_migrer, rollback),

        # 6. Supprimer l'ancien champ
        migrations.RemoveField(
            model_name='documentchauffeur',
            name='type_document_legacy',
        ),

        # 7. Renommer le FK en type_document
        migrations.RenameField(
            model_name='documentchauffeur',
            old_name='type_document_new',
            new_name='type_document',
        ),

        # 8. Rendre le FK non-nullable
        migrations.AlterField(
            model_name='documentchauffeur',
            name='type_document',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='personnel.typedocumentchauffeur',
                verbose_name='Type de document',
            ),
        ),

        # 9. Restaurer l'ordering final
        migrations.AlterModelOptions(
            name='documentchauffeur',
            options={'ordering': ['type_document__nom', '-date_ajout'], 'verbose_name': 'Document chauffeur'},
        ),
    ]
