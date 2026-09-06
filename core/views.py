from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def hub(request):
    from apps.personnel.models import Module
    user = request.user
    if user.is_superuser or user.role == 'super_admin':
        modules = Module.objects.filter(actif=True)
    else:
        modules = user.modules_autorises.filter(actif=True)
    return render(request, 'hub.html', {'modules': modules})
