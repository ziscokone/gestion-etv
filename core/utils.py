"""
Utilitaires partagés entre plusieurs apps.
"""
from django.core.paginator import Paginator
from django.shortcuts import render


def render_paginated_partial(request, queryset, template_name, list_context_name='object_list',
                              extra_context=None, page_size=20, total_context_name=None):
    """
    Pagine `queryset`, rend `template_name` avec le même contexte qu'une
    ListView paginée classique (`list_context_name` = équivalent de
    `context_object_name`, `page_obj`, `is_paginated`), et pose l'en-tête
    `X-Nb-Total` avec le total avant pagination — utilisé par les vues de
    filtrage en direct (recherche automatique) pour éviter de dupliquer ce
    petit patron dans chaque app.

    `total_context_name` : si le partial affiche lui-même un total quelque
    part (ex: "12 destinations"), passer le nom de variable attendu (ex:
    'total_count') pour qu'il soit exposé sans requête COUNT supplémentaire
    (réutilise paginator.count).
    """
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = dict(extra_context or {})
    context[list_context_name] = page_obj.object_list
    context['page_obj'] = page_obj
    context['is_paginated'] = page_obj.has_other_pages()
    if total_context_name:
        context[total_context_name] = paginator.count

    response = render(request, template_name, context)
    response['X-Nb-Total'] = str(paginator.count)
    return response
