"""
Logique métier de la synchronisation entre un poste gare hors-ligne et le serveur central.

Principes (voir DEPLOIEMENT_GARE_HORS_LIGNE.md pour le contexte complet) :
- Push (gare -> central) : Voyages, Billets, Clients, Dépenses. Idempotent via `public_id`
  (généré côté gare) : un ré-envoi du même enregistrement ne crée jamais de doublon.
  La gare authentifiée par le jeton ne peut jamais écrire pour une autre gare qu'elle-même.
- Pull (central -> gare) : données de référence en lecture seule côté gare (lignes, tarifs,
  programmes, véhicules, personnel de CETTE gare uniquement), mirroir par clé primaire car
  ces objets sont toujours créés côté central.
"""
import json
import logging

from django.core import serializers
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# PUSH : gare -> central
# --------------------------------------------------------------------------- #

def appliquer_push(gare, payload):
    """
    Applique un lot d'enregistrements envoyés par une gare.
    Chaque enregistrement est traité indépendamment (savepoint) : un enregistrement
    invalide n'empêche pas les autres d'être importés.

    Retourne (resume: dict, erreurs: list[dict]).
    """
    from apps.clients.models import Client
    from apps.voyages.models import Voyage
    from apps.billets.models import Billet
    from apps.comptabilite.models import Depense

    resume = {'clients': 0, 'voyages': 0, 'billets': 0, 'depenses': 0}
    erreurs = []

    def _tenter(type_nom, public_id, fonction):
        try:
            with transaction.atomic():
                fonction()
            resume[type_nom] += 1
        except Exception as exc:  # noqa: BLE001 — on isole chaque enregistrement volontairement
            logger.warning("Sync push — %s %s rejeté : %s", type_nom, public_id, exc)
            erreurs.append({'type': type_nom, 'public_id': public_id, 'message': str(exc)})

    # 1. Clients (aucune dépendance)
    for data in payload.get('clients', []):
        _tenter('clients', data.get('public_id'), lambda d=data: _upsert_client(d))

    # 2. Voyages (dépend de : gare authentifiée, référence data déjà mirrorée)
    for data in payload.get('voyages', []):
        _tenter('voyages', data.get('public_id'), lambda d=data: _upsert_voyage(d, gare))

    # 3. Billets (dépend des voyages/clients ci-dessus, déjà en base à ce stade)
    for data in payload.get('billets', []):
        _tenter('billets', data.get('public_id'), lambda d=data: _upsert_billet(d, gare))

    # 4. Dépenses (dépend des voyages ci-dessus)
    for data in payload.get('depenses', []):
        _tenter('depenses', data.get('public_id'), lambda d=data: _upsert_depense(d, gare))

    return resume, erreurs


def _upsert_client(data):
    """
    Upsert d'un client par identité (public_id), puis par téléphone en secours —
    un même client (même numéro, unique dans le modèle) peut être créé indépendamment
    sur deux gares avant leur première synchronisation. Si le contact existe déjà,
    son nom est mis à jour s'il diffère (une gare qui complète/corrige le nom d'un
    client déjà connu ne doit jamais créer de doublon, et sa correction doit se
    propager aux autres gares au prochain pull) — utilisé à la fois pour le push
    (gare -> central) et le pull (central -> gare).
    """
    from apps.clients.models import Client

    client = Client.objects.filter(public_id=data['public_id']).first()
    if client is None:
        client = Client.objects.filter(telephone=data['telephone']).first()

    if client is None:
        return Client.objects.create(
            public_id=data['public_id'],
            telephone=data['telephone'],
            nom_complet=data['nom_complet'],
            synced_at=timezone.now(),
        )

    nouveau_nom = data.get('nom_complet')
    if nouveau_nom and client.nom_complet != nouveau_nom:
        client.nom_complet = nouveau_nom
        client.save(update_fields=['nom_complet', 'date_modification'])

    return client


def _upsert_voyage(data, gare):
    """
    Upsert d'un voyage par public_id. Contrairement à un simple get_or_create, les champs
    qui évoluent après la création (statut — ex: passage à "termine" —, véhicule/chauffeur/
    convoyeur réassignés, recette bagages, notes) sont mis à jour à chaque ré-envoi, pas
    seulement figés à la première synchronisation.
    """
    from apps.voyages.models import Voyage

    voyage = Voyage.objects.filter(public_id=data['public_id']).first()

    if voyage is None:
        voyage = Voyage.objects.create(
            public_id=data['public_id'],
            numero_depart=data['numero_depart'],
            gare=gare,  # jamais celle du payload : la gare authentifiée fait foi
            ligne_id=data['ligne_id'],
            date_depart=data['date_depart'],
            heure_depart=data['heure_depart'],
            periode=data['periode'],
            vehicule_id=data.get('vehicule_id'),
            chauffeur_id=data.get('chauffeur_id'),
            convoyeur_id=data.get('convoyeur_id'),
            recette_bagages=data.get('recette_bagages') or 0,
            statut=data.get('statut', 'programme'),
            programme_id=data.get('programme_id'),
            cree_automatiquement=data.get('cree_automatiquement', False),
            notes=data.get('notes', ''),
            synced_at=timezone.now(),
        )
    else:
        if voyage.gare_id != gare.id:
            # Un voyage avec ce public_id existe déjà mais appartient à une autre gare :
            # signale une tentative d'usurpation ou une incohérence, on refuse.
            raise IntegrityError(f"Le voyage {data['public_id']} appartient à une autre gare.")

        voyage.vehicule_id = data.get('vehicule_id')
        voyage.chauffeur_id = data.get('chauffeur_id')
        voyage.convoyeur_id = data.get('convoyeur_id')
        voyage.recette_bagages = data.get('recette_bagages') or 0
        voyage.statut = data.get('statut', voyage.statut)
        voyage.notes = data.get('notes', voyage.notes)
        voyage.save(update_fields=[
            'vehicule', 'chauffeur', 'convoyeur', 'recette_bagages',
            'statut', 'notes', 'date_modification',
        ])

    return voyage


def _upsert_billet(data, gare):
    """
    Upsert d'un billet par public_id. Comme pour le voyage, les champs qui évoluent après
    la création (statut — ex: réservé -> payé —, moyen de paiement, date de paiement) sont
    mis à jour à chaque ré-envoi, pas seulement figés à la première synchronisation.
    Utilisé à la fois pour le push (gare -> central) et pour redescendre au poste gare les
    billets vendus ailleurs sur ses propres voyages (pull), afin de réduire la fenêtre de
    risque de survente entre deux synchronisations.
    """
    from apps.voyages.models import Voyage
    from apps.clients.models import Client
    from apps.billets.models import Billet

    voyage = Voyage.objects.filter(public_id=data['voyage_public_id'], gare=gare).first()
    if voyage is None:
        raise ValueError(f"Voyage {data['voyage_public_id']} introuvable pour ce billet.")

    client = None
    if data.get('client_public_id'):
        client = Client.objects.filter(public_id=data['client_public_id']).first()

    billet = Billet.objects.filter(public_id=data['public_id']).first()

    if billet is None:
        billet = Billet.objects.create(
            public_id=data['public_id'],
            numero=data['numero'],
            voyage=voyage,
            destination_id=data.get('destination_id'),
            client=client,
            client_nom=data['client_nom'],
            client_telephone=data['client_telephone'],
            numero_siege=data.get('numero_siege'),
            montant=data['montant'],
            statut=data.get('statut', 'reserve'),
            moyen_paiement=data.get('moyen_paiement', 'cash'),
            guichetier_id=data.get('guichetier_id'),
            date_paiement=data.get('date_paiement'),
            synced_at=timezone.now(),
        )
    else:
        if billet.voyage.gare_id != gare.id:
            raise IntegrityError(f"Le billet {data['public_id']} appartient à une autre gare.")

        billet.statut = data.get('statut', billet.statut)
        billet.moyen_paiement = data.get('moyen_paiement', billet.moyen_paiement)
        billet.date_paiement = data.get('date_paiement')
        billet.client = client
        billet.save(update_fields=[
            'statut', 'moyen_paiement', 'date_paiement', 'client', 'date_modification',
        ])

    return billet


def _upsert_depense(data, gare):
    from apps.voyages.models import Voyage
    from apps.comptabilite.models import Depense

    voyage = Voyage.objects.filter(public_id=data['voyage_public_id'], gare=gare).first()
    if voyage is None:
        raise ValueError(f"Voyage {data['voyage_public_id']} introuvable pour cette dépense.")

    depense, created = Depense.objects.get_or_create(
        public_id=data['public_id'],
        defaults={
            'voyage': voyage,
            'type_depense_id': data['type_depense_id'],
            'montant': data['montant'],
            'description': data.get('description', ''),
            'guichetier_id': data.get('guichetier_id'),
            'synced_at': timezone.now(),
        }
    )
    if depense.voyage.gare_id != gare.id:
        raise IntegrityError(f"La dépense {data['public_id']} appartient à une autre gare.")
    return depense


# --------------------------------------------------------------------------- #
# PULL : central -> gare (données de référence, lecture seule côté gare)
# --------------------------------------------------------------------------- #

# Ordre important : chaque modèle ne doit être importé qu'après ceux dont il dépend
# par clé étrangère (voir la note de conception dans le guide de déploiement).
PULL_ORDRE = [
    'compagnie', 'modules', 'gares', 'lignes', 'destinations',
    'modeles_vehicule', 'vehicules', 'types_depense',
    'utilisateurs', 'chauffeurs', 'convoyeurs', 'programmes',
]


def construire_pull(gare):
    """Construit le dump JSON des données de référence visibles par cette gare."""
    from apps.compagnie.models import Compagnie
    from apps.personnel.models import Module, Utilisateur, Chauffeur, Convoyeur
    from apps.lignes.models import Ligne
    from apps.destinations.models import Destination
    from apps.vehicules.models import ModeleVehicule, Vehicule
    from apps.comptabilite.models import TypeDepense
    from apps.programmes.models import ProgrammeDepart
    from apps.gares.models import Gare
    from apps.clients.models import Client

    compagnie = gare.compagnie

    def _dump(queryset):
        return json.loads(serializers.serialize('json', queryset))

    return {
        'compagnie': _dump(Compagnie.objects.filter(pk=compagnie.pk)),
        'modules': _dump(Module.objects.all()),
        'gares': _dump(Gare.objects.filter(pk=gare.pk)),
        'lignes': _dump(Ligne.objects.filter(gare=gare)),
        'destinations': _dump(Destination.objects.filter(gare=gare)),
        'modeles_vehicule': _dump(ModeleVehicule.objects.all()),
        'vehicules': _dump(Vehicule.objects.filter(compagnie=compagnie)),
        'types_depense': _dump(TypeDepense.objects.filter(compagnie=compagnie)),
        # Volontairement limité au personnel DE CETTE gare : un poste hors-ligne compromis
        # ne doit jamais exposer les identifiants (hash de mot de passe compris) du
        # personnel à accès global (PDG, managers...) d'une autre gare.
        'utilisateurs': _dump(Utilisateur.objects.filter(gare=gare)),
        'chauffeurs': _dump(Chauffeur.objects.filter(compagnie=compagnie, actif=True)),
        'convoyeurs': _dump(Convoyeur.objects.filter(compagnie=compagnie, actif=True)),
        'programmes': _dump(ProgrammeDepart.objects.filter(gare=gare)),
        # Les clients sont une ressource globale (pas de champ gare sur le modèle) :
        # toutes les gares doivent voir la liste complète, pas seulement leurs propres
        # ventes. Réconciliés via _upsert_client (par public_id puis téléphone) plutôt
        # que mirorés par PK brute, car un client peut être créé indépendamment sur
        # plusieurs gares antérieure à leur première synchronisation.
        'clients': _dump(Client.objects.all()),
        # Billets déjà vendus sur les voyages de CETTE gare, y compris ceux vendus
        # directement au central (ex: par un manager connecté) pendant que la gare est
        # hors-ligne. Redescendus pour que l'occupation des sièges vue localement reste
        # à jour et réduire la fenêtre de risque de survente entre deux synchronisations.
        # Format dédié (public_id en clé étrangère, pas la PK brute) car Billet/Voyage se
        # réconcilient par identité, pas par mirroring de PK — voir _upsert_billet.
        'billets': _dump_billets_pour_gare(gare),
    }


def _dump_billets_pour_gare(gare):
    from apps.billets.models import Billet

    billets = Billet.objects.filter(voyage__gare=gare).select_related('voyage', 'client')
    return [
        {
            'public_id': str(b.public_id),
            'numero': b.numero,
            'voyage_public_id': str(b.voyage.public_id),
            'destination_id': b.destination_id,
            'client_public_id': str(b.client.public_id) if b.client_id else None,
            'client_nom': b.client_nom,
            'client_telephone': b.client_telephone,
            'numero_siege': b.numero_siege,
            'montant': str(b.montant),
            'statut': b.statut,
            'moyen_paiement': b.moyen_paiement,
            'guichetier_id': b.guichetier_id,
            'date_paiement': b.date_paiement.isoformat() if b.date_paiement else None,
        }
        for b in billets
    ]


def appliquer_pull(data):
    """
    Importe côté gare le dump produit par construire_pull. Idempotent (mirroir par PK
    pour les modèles de PULL_ORDRE, réconciliation par identité pour les clients et les
    billets — voir _upsert_client / _upsert_billet).

    Chaque enregistrement est appliqué dans SA PROPRE transaction (comme dans
    appliquer_push), et non dans une transaction globale : sur SQLite, les clés
    étrangères sont DEFERRABLE INITIALLY DEFERRED (vérifiées au COMMIT, pas à
    l'écriture). Un `try/except` par enregistrement à l'intérieur d'une transaction
    unique ne protège donc de rien — l'erreur ne remonte qu'au COMMIT final et fait
    alors échouer tout le pull, y compris les enregistrements valides déjà traités.
    Isoler chaque enregistrement dans son propre COMMIT est indispensable pour qu'un
    enregistrement invalide (ex: billet vendu par un compte à accès global, jamais
    synchronisé côté gare — voir construire_pull) ne bloque pas les autres.
    """
    from apps.gares.models import Gare

    total = 0

    for item in data.get('clients', []):
        try:
            with transaction.atomic():
                _upsert_client(item['fields'])
            total += 1
        except Exception:  # noqa: BLE001 — un client invalide ne doit pas bloquer le reste du pull
            logger.warning("Sync pull — client %s ignoré : échec de réconciliation", item.get('pk'))

    for cle in PULL_ORDRE:
        objets = list(serializers.deserialize('json', json.dumps(data.get(cle, []))))
        for obj in objets:
            try:
                with transaction.atomic():
                    obj.save()
                total += 1
            except Exception:  # noqa: BLE001 — un enregistrement invalide ne doit pas bloquer le reste du pull
                logger.warning("Sync pull — %s %s ignoré : échec d'application", cle, obj.object.pk)

    billets = data.get('billets', [])
    if billets:
        gare_locale = Gare.objects.first()
        for item in billets:
            try:
                with transaction.atomic():
                    _upsert_billet(item, gare_locale)
                total += 1
            except Exception:  # noqa: BLE001 — un billet invalide ne doit pas bloquer le reste du pull
                logger.warning("Sync pull — billet %s ignoré : échec de réconciliation", item.get('public_id'))
    return total
