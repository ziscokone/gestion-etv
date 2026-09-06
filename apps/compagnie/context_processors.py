from .models import Compagnie


def compagnie_context(request):
    """
    Context processor pour rendre les informations de la compagnie
    disponibles dans tous les templates.
    """
    return {
        'compagnie': Compagnie.get_instance()
    }
