"""
Impression thermique ESC/POS directe (remplace QZ Tray / window.print()).

Le poste guichet fait tourner à la fois le navigateur et le serveur Django
(waitress) sur la même machine Windows, avec l'imprimante thermique branchée
en USB sur ce même poste. On peut donc imprimer directement depuis Python, en
envoyant les octets ESC/POS bruts au driver Windows déjà installé pour cette
imprimante (backend Win32Raw de python-escpos) — pas de boîte de dialogue,
pas de remplacement de driver USB, et ESC/POS étant un standard partagé par
Epson et Xprinter, un seul code fonctionne pour les deux marques.

IMPRIMANTE_BACKEND permet de tester sans imprimante physique (voir settings) :
- 'dummy' : aucune sortie physique, sert aux tests automatisés
- 'file'  : écrit les octets ESC/POS bruts dans un fichier, pour inspection
  manuelle du format sans imprimante (xxd/hexdump)
- 'win32raw' : impression réelle sur le poste guichet (par défaut)
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class ErreurImpression(Exception):
    """Erreur d'impression thermique. Le message est déjà destiné à l'utilisateur final."""


class ImprimanteNonConfiguree(ErreurImpression):
    pass


class ImprimanteIntrouvable(ErreurImpression):
    pass


class ErreurMaterielleImpression(ErreurImpression):
    pass


def _config_imprimante():
    """Nom et largeur configurés pour ce poste (menu "Configuration Imprimante
    Ticket", champs sur Gare) — pas de valeur configurée si aucune gare locale."""
    from apps.gares.models import Gare
    gare = Gare.objects.first()
    nom = gare.imprimante_nom if gare else ''
    largeur = gare.imprimante_largeur_caracteres if gare else 48
    return nom, largeur


def get_imprimante():
    """Retourne une instance escpos.printer.* prête à imprimer, ou lève ErreurImpression."""
    backend = settings.IMPRIMANTE_BACKEND

    if backend == 'dummy':
        from escpos.printer import Dummy
        return Dummy()

    if backend == 'file':
        if not settings.IMPRIMANTE_FICHIER_SORTIE:
            raise ImprimanteNonConfiguree(
                "IMPRIMANTE_FICHIER_SORTIE n'est pas configuré sur ce poste."
            )
        from escpos.exceptions import DeviceNotFoundError
        from escpos.printer import File
        imprimante = File(settings.IMPRIMANTE_FICHIER_SORTIE)
        try:
            imprimante.open()
        except DeviceNotFoundError as exc:
            raise ImprimanteIntrouvable(
                f"Impossible d'écrire le fichier de sortie : {exc}"
            ) from exc
        return imprimante

    if backend == 'win32raw':
        nom, _ = _config_imprimante()
        if not nom:
            raise ImprimanteNonConfiguree(
                "Imprimante non configurée sur ce poste. Configurez-la depuis "
                "le menu \"Configuration Imprimante Ticket\"."
            )
        from escpos.exceptions import DeviceNotFoundError
        from escpos.printer import Win32Raw
        imprimante = Win32Raw(nom)
        try:
            imprimante.open()
        except DeviceNotFoundError as exc:
            raise ImprimanteIntrouvable(
                "Imprimante introuvable. Vérifiez qu'elle est bien branchée et sous tension."
            ) from exc
        return imprimante

    raise ImprimanteNonConfiguree(f"Backend d'impression inconnu : {backend!r}")


def imprimer_billets(billets_info, duplicata=False, imprimante=None, largeur=None):
    """
    Imprime un lot de billets (1 ou plusieurs, ex. vente en plage de sièges).

    billets_info : liste de dicts issus de Billet.get_info_impression(), dans
    l'ordre où ils doivent sortir de l'imprimante. Un p.cut() est effectué
    après chaque billet : N billets vendus = N tickets physiques séparés.

    `imprimante` et `largeur` permettent d'injecter des valeurs déjà connues
    (tests) ; laissés à None en usage normal, où l'imprimante et la largeur
    du poste sont déterminées via get_imprimante()/_config_imprimante().
    """
    imprimante = imprimante or get_imprimante()
    if largeur is None:
        _, largeur = _config_imprimante()
    try:
        imprimante.charcode('CP858')
        for info in billets_info:
            _imprimer_un_billet(imprimante, info, duplicata, largeur)
            imprimante.cut()
    except ErreurImpression:
        raise
    except Exception as exc:
        logger.exception("Échec impression thermique")
        raise ErreurMaterielleImpression(
            "Erreur d'impression (papier ou connexion). Vérifiez l'imprimante et réessayez."
        ) from exc
    finally:
        imprimante.close()


# Caractères typographiques usuels absents du codepage CP858 (voir imprimer_billets) :
# sans ce nettoyage ils ressortent en "?" sur le ticket (ex: la flèche de Ligne.__str__
# donnant "DANANE ? ABIDJAN" au lieu de "DANANE → ABIDJAN").
_TRANSLITTERATIONS = str.maketrans({
    '→': '-', '←': '-', '–': '-', '—': '-',
    '’': "'", '‘': "'", '“': '"', '”': '"', '…': '...',
})


def _texte_imprimable(valeur):
    """Rend une chaîne sûre pour l'impression en CP858 (voir _TRANSLITTERATIONS ;
    tout caractère restant non représentable dans ce jeu est remplacé par '?')."""
    valeur = str(valeur).translate(_TRANSLITTERATIONS)
    return valeur.encode('cp858', errors='replace').decode('cp858')


def _ligne(etiquette, valeur, largeur):
    """Une ligne étiquette/valeur : étiquette à gauche, valeur à droite, largeur fixe."""
    valeur = _texte_imprimable(valeur)
    espace = largeur - len(etiquette) - len(valeur)
    if espace < 1:
        return f"{etiquette}: {valeur}\n"
    return f"{etiquette}{' ' * espace}{valeur}\n"


def _montant_affiche(montant):
    formate = f"{int(montant):,}".replace(',', ' ')
    return f"{formate} FCFA"


def _imprimer_un_billet(p, info, duplicata, largeur):
    # font explicite ici : p.set() n'envoie que ce qui est précisé (voir python-escpos),
    # donc sans ce rappel un billet précédent laissé en font 'b' (message_bas_ticket
    # ci-dessous) contaminerait le début de CE billet.
    p.set(align='center', bold=True, width=2, height=2, font='a')
    p.textln(_texte_imprimable(info['compagnie_nom'] or ''))

    p.set(align='center', bold=False, width=1, height=1)
    if info['gare_adresse']:
        p.textln(_texte_imprimable(info['gare_adresse']))
    if info['gare_telephone']:
        p.textln(_texte_imprimable(info['gare_telephone']))
    p.textln('-' * largeur)

    if duplicata:
        p.set(align='center', bold=True, invert=True)
        p.textln('*** DUPLICATA ***')
        p.set(align='center', bold=False, invert=False)
        p.textln('-' * largeur)

    p.set(align='left', bold=False)
    p.textln('')
    p.line_spacing(36)  # légèrement plus aéré que le pas par défaut (~30/180") pour ce bloc
    p.text(_ligne('N Ticket', info['numero'], largeur))
    p.text(_ligne('N Depart', info['numero_depart'], largeur))
    p.text(_ligne('Client', info['client_nom'], largeur))
    p.set(bold=True)
    p.text(_ligne('Siege', info['numero_siege'], largeur))
    p.set(bold=False)
    p.text(_ligne('Ligne', info['ligne'], largeur))
    p.text(_ligne('Destination', info['destination'], largeur))
    p.text(_ligne('Date', info['date_depart'], largeur))
    p.set(bold=True)
    p.text(_ligne('Heure', info['heure_depart'], largeur))
    p.set(bold=False)
    p.line_spacing()  # retour au pas par défaut pour la suite du ticket
    p.textln('')

    est_gratuit = info['statut'] in ('gratuit', 'gratuit_en_attente')
    if est_gratuit:
        p.set(align='center', bold=True, invert=True)
        p.textln('GRATUIT')
        p.set(align='left', bold=False, invert=False)
    else:
        p.set(bold=True)
        p.text(_ligne('Montant', _montant_affiche(info['montant']), largeur))
        p.set(bold=False)
        p.text(_ligne('Paiement', info['moyen_paiement_display'], largeur))

    # Souche détachable : uniquement si le billet est effectivement payé
    # (règle unifiée entre vente normale et duplicata).
    souche = info['utiliser_souche'] and info['statut'] == 'paye'

    if not souche and info['message_bas_ticket']:
        p.set(align='left', bold=False, font='b')
        p.textln('')
        p.textln(_texte_imprimable(info['message_bas_ticket']))

    if souche:
        if info['message_bas_ticket']:
            p.set(align='left', bold=False, font='b')
            p.textln('')
            p.textln(_texte_imprimable(info['message_bas_ticket']))

        p.textln('')
        p.textln('-' * largeur)
        p.set(align='center', bold=True, font='a')
        p.textln('COUPER ICI')
        p.textln('SOUCHE')
        p.set(align='left', bold=False)
        p.text(_ligne('N Depart', info['numero_depart'], largeur))
        p.set(bold=True)
        p.text(_ligne('Siege', info['numero_siege'], largeur))
        p.set(bold=False)
        p.text(_ligne('Ligne', info['ligne'], largeur))
        p.text(_ligne('Date', info['date_depart'], largeur))
        p.set(bold=True)
        p.text(_ligne('Heure', info['heure_depart'], largeur))
        p.set(bold=False)
