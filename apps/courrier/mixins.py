"""
Mixin de permission propre au module Courrier.

Volontairement distinct de core.mixins.GestionRequiredMixin (partagé par le
garage/véhicules) : un « Agent Courrier » ne doit avoir accès qu'au courrier,
pas aux réparations véhicules ni aux autres modules de gestion. Ajouter ce
rôle à GestionRequiredMixin lui ouvrirait ces autres modules par la seule
vérification de rôle, indépendamment des modules réellement attribués
(Utilisateur.modules_autorises) — ce mixin évite ce débordement.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class CourrierAccessRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Accès aux écrans opérationnels du courrier (enregistrement, chargement,
    retrait, annulation) : accès global, chef de gare, guichetier, ou le
    rôle dédié Agent Courrier.
    """

    def test_func(self):
        user = self.request.user
        return (
            user.has_global_access
            or user.is_chef_gare
            or user.is_guichetier
            or user.is_agent_courrier
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Vous n'avez pas les droits nécessaires pour accéder à cette page.")
        return super().handle_no_permission()
