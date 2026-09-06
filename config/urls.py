import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import hub

ADMIN_URL = os.environ.get('ADMIN_URL', 'otci-admin-panel/')

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path('hub/', hub, name='hub'),
    path('', include('apps.guichet.urls')),
    path('clients/', include('apps.clients.urls')),
    path('personnel/', include('apps.personnel.urls')),
    path('comptabilite/', include('apps.comptabilite.urls')),
    path('gares/', include('apps.gares.urls')),
    path('lignes/', include('apps.lignes.urls')),
    path('destinations/', include('apps.destinations.urls')),
    path('vehicules/', include('apps.vehicules.urls')),
    path('programmes/', include('apps.programmes.urls')),
    path('voyages/', include('apps.voyages.urls')),
    path('compagnie/', include('apps.compagnie.urls')),
    path('api/sync/', include('apps.sync.urls')),
    path('courrier/', include('apps.courrier.urls')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
