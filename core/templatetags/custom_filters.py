from django import template

register = template.Library()


@register.filter(name='format_montant')
def format_montant(value):
    """
    Formate un nombre avec des séparateurs de milliers (espace).
    Exemple: 1234567 -> 1 234 567
    """
    try:
        # Convertir en float puis en int pour supprimer les décimales
        value = int(float(value))
        # Formater avec des espaces comme séparateurs de milliers
        return "{:,}".format(value).replace(',', ' ')
    except (ValueError, TypeError):
        return value


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Récupère une valeur dans un dictionnaire à partir d'une clé.
    Utilisé dans les templates pour accéder à des clés dynamiques.
    Exemple: {{ mon_dict|get_item:ma_cle }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0
