import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.gares.models import Gare, GareSyncToken
from apps.sync.models import SyncLog
from apps.sync import client as sync_client
from apps.sync import services

logger = logging.getLogger(__name__)


def _authentifier(request):
    """Retourne la Gare associée au jeton Bearer fourni, ou None."""
    entete = request.headers.get('Authorization', '')
    if not entete.startswith('Bearer '):
        return None
    return GareSyncToken.verifier(entete[len('Bearer '):].strip())


def _reponse_non_autorise():
    return JsonResponse({'ok': False, 'erreur': 'Jeton de synchronisation invalide ou manquant.'}, status=401)


@csrf_exempt
@require_GET
@ratelimit(key='header:authorization', rate='60/m', method='GET', block=True)
def ping(request):
    """Vérifie la joignabilité du serveur et la validité du jeton (utilisé avant push/pull)."""
    gare = _authentifier(request)
    if gare is None:
        return _reponse_non_autorise()
    return JsonResponse({'ok': True, 'gare': gare.code})


@csrf_exempt
@require_POST
@ratelimit(key='header:authorization', rate='20/m', method='POST', block=True)
def push(request):
    """Reçoit les nouveautés (Voyages/Billets/Clients/Dépenses) d'une gare hors-ligne."""
    gare = _authentifier(request)
    if gare is None:
        return _reponse_non_autorise()

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'erreur': 'Corps de requête JSON invalide.'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'ok': False, 'erreur': 'Le corps doit être un objet JSON.'}, status=400)

    try:
        resume, erreurs = services.appliquer_push(gare, payload)
    except Exception:
        logger.exception("Sync push — échec inattendu pour la gare %s", gare.code)
        SyncLog.objects.create(
            gare=gare, direction='push', statut='erreur',
            detail="Erreur inattendue côté serveur, voir les logs."
        )
        return JsonResponse({'ok': False, 'erreur': 'Erreur inattendue côté serveur.'}, status=500)

    SyncLog.objects.create(
        gare=gare,
        direction='push',
        statut='ok' if not erreurs else 'partiel',
        nb_enregistrements=sum(resume.values()),
        detail=json.dumps(erreurs, ensure_ascii=False) if erreurs else '',
    )

    return JsonResponse({'ok': True, 'resume': resume, 'erreurs': erreurs})


@csrf_exempt
@require_GET
@ratelimit(key='header:authorization', rate='20/m', method='GET', block=True)
def pull(request):
    """Renvoie les données de référence à jour pour la gare authentifiée."""
    gare = _authentifier(request)
    if gare is None:
        return _reponse_non_autorise()

    try:
        data = services.construire_pull(gare)
    except Exception:
        logger.exception("Sync pull — échec inattendu pour la gare %s", gare.code)
        SyncLog.objects.create(
            gare=gare, direction='pull', statut='erreur',
            detail="Erreur inattendue côté serveur, voir les logs."
        )
        return JsonResponse({'ok': False, 'erreur': 'Erreur inattendue côté serveur.'}, status=500)

    nb = sum(len(v) for v in data.values())
    SyncLog.objects.create(gare=gare, direction='pull', statut='ok', nb_enregistrements=nb)

    return JsonResponse({'ok': True, 'donnees': data})


# --------------------------------------------------------------------------- #
# Écran de statut — visible par tous les rôles (guichetier, chef_gare, manager,
# super_admin, PDG). Deux affichages selon le poste :
#  - poste gare hors-ligne (SYNC_CENTRAL_URL/SYNC_TOKEN configurés) : statut de
#    CE poste + bouton "Synchroniser maintenant" ;
#  - serveur central : tableau de bord en lecture seule de l'état de chaque gare.
# --------------------------------------------------------------------------- #

@login_required
def statut(request):
    contexte = {'est_gare_locale': sync_client.est_configure()}

    if contexte['est_gare_locale']:
        contexte['gare'] = Gare.objects.first()
        contexte['en_attente'] = sync_client.compter_en_attente()
        contexte['dernier_push'] = SyncLog.objects.filter(direction='push').order_by('-date_creation').first()
        contexte['dernier_pull'] = SyncLog.objects.filter(direction='pull').order_by('-date_creation').first()
    else:
        if request.user.has_global_access:
            gares = Gare.objects.filter(active=True)
        elif request.user.gare_id:
            gares = Gare.objects.filter(pk=request.user.gare_id)
        else:
            gares = Gare.objects.none()

        contexte['lignes'] = [
            {
                'gare': gare,
                'dernier_push': SyncLog.objects.filter(gare=gare, direction='push').order_by('-date_creation').first(),
                'dernier_pull': SyncLog.objects.filter(gare=gare, direction='pull').order_by('-date_creation').first(),
            }
            for gare in gares
        ]

    return render(request, 'sync/statut.html', contexte)


@login_required
@require_POST
def declencher(request):
    """Bouton "Synchroniser maintenant" — n'a de sens que sur un poste gare hors-ligne."""
    if not sync_client.est_configure():
        messages.error(request, "La synchronisation n'est pas configurée sur ce poste.")
        return redirect('sync:statut')

    resultat_pull = sync_client.executer_pull()
    resultat_push = sync_client.executer_push()

    if not resultat_pull['ok'] and not resultat_push['ok']:
        messages.error(request, f"Synchronisation impossible : {resultat_push['message']}")
    else:
        if resultat_pull['ok']:
            messages.success(request, f"Données de référence : {resultat_pull['message']}")
        if resultat_push['ok']:
            messages.success(request, f"Envoi des ventes : {resultat_push['message']}")
        for erreur in resultat_push.get('erreurs', []):
            messages.warning(request, f"Rejeté — {erreur['type']} : {erreur['message']}")

    return redirect('sync:statut')
