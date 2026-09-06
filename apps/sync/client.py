"""
Logique côté POSTE GARE pour dialoguer avec le serveur central (apps.sync).
Utilisée à la fois par les management commands (sync_push/sync_pull, appelées par
le Planificateur de tâches Windows) et par l'écran de statut (bouton "Synchroniser
maintenant"), pour ne jamais dupliquer cette logique.
"""
import json
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _config():
    central_url = (getattr(settings, 'SYNC_CENTRAL_URL', '') or '').rstrip('/')
    token = getattr(settings, 'SYNC_TOKEN', '') or ''
    return central_url, token


def est_configure():
    """True si ce poste est configuré comme poste gare hors-ligne (a un jeton central)."""
    central_url, token = _config()
    return bool(central_url and token)


def _journaliser_local(direction, statut, nb, detail=''):
    """Enregistre localement (sur CE poste) le résultat d'une tentative de synchro."""
    from apps.gares.models import Gare
    from apps.sync.models import SyncLog

    gare_locale = Gare.objects.first()
    if gare_locale is None:
        return  # rien à journaliser avant que la gare elle-même n'ait été importée
    SyncLog.objects.create(gare=gare_locale, direction=direction, statut=statut,
                            nb_enregistrements=nb, detail=detail)


def executer_push():
    """
    Envoie vers le central les nouveautés locales (Voyages/Billets/Clients/Dépenses).
    Retourne {'ok': bool, 'message': str, 'resume': dict, 'erreurs': list}.
    """
    import requests

    resultat = {'ok': False, 'message': '', 'resume': {}, 'erreurs': []}
    central_url, token = _config()
    if not central_url or not token:
        resultat['message'] = "Synchronisation non configurée sur ce poste (SYNC_CENTRAL_URL / SYNC_TOKEN manquants)."
        return resultat

    payload = _construire_payload_push()
    total = sum(len(v) for v in payload.values())
    if total == 0:
        resultat.update(ok=True, message="Rien à envoyer, tout est déjà synchronisé.")
        return resultat

    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.post(f'{central_url}/api/sync/push/', json=payload, headers=headers, timeout=60)
    except requests.exceptions.RequestException:
        resultat['message'] = "Pas de connexion au serveur central."
        return resultat

    if resp.status_code != 200:
        resultat['message'] = f"Le serveur a refusé l'envoi (HTTP {resp.status_code})."
        _journaliser_local('push', 'erreur', 0, resultat['message'])
        return resultat

    corps = resp.json()
    erreurs = corps.get('erreurs', [])
    resume = corps.get('resume', {})
    _marquer_synchronise(payload, erreurs)

    nb_envoyes = sum(resume.values())
    resultat.update(
        ok=True,
        resume=resume,
        erreurs=erreurs,
        message=f"{nb_envoyes} enregistrement(s) envoyé(s)." + (
            f" {len(erreurs)} rejeté(s)." if erreurs else ""
        ),
    )
    _journaliser_local(
        'push', 'ok' if not erreurs else 'partiel', nb_envoyes,
        json.dumps(erreurs, ensure_ascii=False) if erreurs else ''
    )
    return resultat


def executer_pull():
    """
    Récupère depuis le central les données de référence à jour pour cette gare.
    Retourne {'ok': bool, 'message': str, 'nb': int}.
    """
    import requests
    from apps.sync import services

    resultat = {'ok': False, 'message': '', 'nb': 0}
    central_url, token = _config()
    if not central_url or not token:
        resultat['message'] = "Synchronisation non configurée sur ce poste (SYNC_CENTRAL_URL / SYNC_TOKEN manquants)."
        return resultat

    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(f'{central_url}/api/sync/pull/', headers=headers, timeout=30)
    except requests.exceptions.RequestException:
        resultat['message'] = "Pas de connexion au serveur central."
        return resultat

    if resp.status_code != 200:
        resultat['message'] = f"Échec de la récupération (HTTP {resp.status_code})."
        _journaliser_local('pull', 'erreur', 0, resultat['message'])
        return resultat

    corps = resp.json()
    total = services.appliquer_pull(corps.get('donnees', {}))
    resultat.update(ok=True, nb=total, message=f"{total} donnée(s) de référence mise(s) à jour.")
    _journaliser_local('pull', 'ok', total)
    return resultat


def _construire_payload_push():
    from apps.clients.models import Client
    from apps.voyages.models import Voyage
    from apps.billets.models import Billet
    from apps.comptabilite.models import Depense

    clients = Client.objects.filter(synced_at__isnull=True)
    voyages = Voyage.objects.filter(synced_at__isnull=True)
    billets = Billet.objects.filter(synced_at__isnull=True).select_related('voyage', 'client')
    depenses = Depense.objects.filter(synced_at__isnull=True).select_related('voyage')

    return {
        'clients': [
            {'public_id': str(c.public_id), 'telephone': c.telephone, 'nom_complet': c.nom_complet}
            for c in clients
        ],
        'voyages': [
            {
                'public_id': str(v.public_id),
                'numero_depart': v.numero_depart,
                'ligne_id': v.ligne_id,
                'date_depart': v.date_depart.isoformat(),
                'heure_depart': v.heure_depart.isoformat(),
                'periode': v.periode,
                'vehicule_id': v.vehicule_id,
                'chauffeur_id': v.chauffeur_id,
                'convoyeur_id': v.convoyeur_id,
                'recette_bagages': str(v.recette_bagages),
                'statut': v.statut,
                'programme_id': v.programme_id,
                'cree_automatiquement': v.cree_automatiquement,
                'notes': v.notes,
            }
            for v in voyages
        ],
        'billets': [
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
        ],
        'depenses': [
            {
                'public_id': str(d.public_id),
                'voyage_public_id': str(d.voyage.public_id),
                'type_depense_id': d.type_depense_id,
                'montant': str(d.montant),
                'description': d.description,
                'guichetier_id': d.guichetier_id,
            }
            for d in depenses
        ],
    }


def _marquer_synchronise(payload, erreurs):
    """Marque comme synchronisé tout ce qui a été envoyé, sauf ce que le serveur a rejeté."""
    from apps.clients.models import Client
    from apps.voyages.models import Voyage
    from apps.billets.models import Billet
    from apps.comptabilite.models import Depense

    echoues = {e['public_id'] for e in erreurs}
    now = timezone.now()

    for modele, enregistrements in [
        (Client, payload['clients']),
        (Voyage, payload['voyages']),
        (Billet, payload['billets']),
        (Depense, payload['depenses']),
    ]:
        ids_ok = [r['public_id'] for r in enregistrements if r['public_id'] not in echoues]
        if ids_ok:
            modele.objects.filter(public_id__in=ids_ok).update(synced_at=now)


def compter_en_attente():
    """Nombre d'enregistrements locaux pas encore envoyés au central, par type."""
    from apps.clients.models import Client
    from apps.voyages.models import Voyage
    from apps.billets.models import Billet
    from apps.comptabilite.models import Depense

    return {
        'clients': Client.objects.filter(synced_at__isnull=True).count(),
        'voyages': Voyage.objects.filter(synced_at__isnull=True).count(),
        'billets': Billet.objects.filter(synced_at__isnull=True).count(),
        'depenses': Depense.objects.filter(synced_at__isnull=True).count(),
    }
